from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Prefetch, Sum
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError as APIValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounting.enums import EntryStatus
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import (
    publish_journal_entry,
    reverse_journal_entry,
)
from apps.accounting.serializers.account import (
    AccountListQuerySerializer,
    AccountSerializer,
)
from apps.accounting.serializers.journal_entry import (
    DateRangeQuerySerializer,
    GeneralLedgerRowSerializer,
    JournalEntryDetailSerializer,
    JournalEntryListQuerySerializer,
    JournalEntrySerializer,
    TrialBalanceRowSerializer,
)
from apps.company.models import Company, CompanyMember
from apps.users.authentication import SupabaseBearerAuthentication

LINES_PREFETCH = Prefetch(
    "lines",
    queryset=JournalLine.objects.select_related("account").order_by("pk"),
)


def apply_date_range(queryset, filters):
    """
    Acota los asientos del historial al rango de fechas contables consultado.

    @version 1.0
    @author Agustin
    """
    if "accounting_date_from" in filters:
        queryset = queryset.filter(accounting_date__gte=filters["accounting_date_from"])
    if "accounting_date_to" in filters:
        queryset = queryset.filter(accounting_date__lte=filters["accounting_date_to"])
    return queryset


class CompanyAccessMixin:
    """
    Limita la consulta a la Company de la URL y sus miembros.

    @version 1.0
    @author Agustin
    """

    authentication_classes = (SupabaseBearerAuthentication,)
    permission_classes = (IsAuthenticated,)

    def handle_exception(self, error):
        """
        Devuelve sólo el identificador de los errores funcionales de Accounting.

        @version 1.0
        @author Agustin
        """
        if isinstance(error, APIValidationError):
            codes = error.get_codes()
            error_codes = codes.get("code", []) if isinstance(codes, dict) else codes
            for code in (
                "NEX-ACC-001",
                "NEX-ACC-002",
                "NEX-ACC-003",
                "NEX-ACC-004",
            ):
                if isinstance(error_codes, list) and code in error_codes:
                    return Response({"code": code}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(error)

    def get_company(self):
        """
        Obtiene la Company solicitada y exige membership del usuario.

        @version 1.0
        @author Agustin
        """
        company = get_object_or_404(Company, pk=self.kwargs["company_id"])
        if not CompanyMember.objects.filter(
            user=self.request.user,
            company=company,
        ).exists():
            raise PermissionDenied()
        return company


class AccountAccessMixin(CompanyAccessMixin):
    """
    Limita el plan de cuentas a la Company de la URL y sus miembros.

    @version 1.0
    @author Agustin
    """

    serializer_class = AccountSerializer

    def handle_exception(self, error):
        """
        Traduce sólo la colisión de unicidad de Account a su error funcional.

        @version 1.0
        @author Agustin
        """
        if isinstance(error, IntegrityError):
            cause = error.__cause__
            constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
            duplicate = constraint == "unique_account_company_code" or (
                connection.vendor == "sqlite"
                and str(cause) == (
                    "UNIQUE constraint failed: accounting_accounts.company_id, "
                    "accounting_accounts.code"
                )
            )
            if not duplicate:
                return super().handle_exception(error)
            error = APIValidationError(
                "El código de cuenta ya existe en la Company.",
                code="NEX-ACC-001",
            )
        return super().handle_exception(error)

    def get_queryset(self):
        """
        Devuelve únicamente las cuentas de la Company autorizada.

        @version 1.0
        @author Agustin
        """
        return Account.objects.filter(company=self.get_company())


class JournalEntryHistoryMixin(CompanyAccessMixin):
    """
    Expone el historial contable válido de la Company autorizada.

    @version 1.0
    @author Antonio
    """

    def get_history_queryset(self):
        """
        Devuelve los asientos no borradores que integran el historial contable.

        @version 1.0
        @author Antonio
        """
        return JournalEntry.objects.filter(company=self.get_company()).exclude(
            status=EntryStatus.DRAFT
        )


class AccountListCreateView(AccountAccessMixin, generics.ListCreateAPIView):
    """
    Lista y crea cuentas dentro del plan de una Company.

    @version 1.0
    @author Agustin
    """

    def create(self, request, *args, **kwargs):
        """
        Verifica el acceso a la Company antes de validar el payload.

        @version 1.0
        @author Agustin
        """
        self.get_company()
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """
        Aplica los filtros válidos al plan de cuentas autorizado.

        @version 1.0
        @author Agustin
        """
        accounts = super().get_queryset()
        filters = AccountListQuerySerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        if "account_type" in filters.validated_data:
            accounts = accounts.filter(account_type=filters.validated_data["account_type"])
        if "is_active" in filters.validated_data:
            accounts = accounts.filter(is_active=filters.validated_data["is_active"])
        return accounts.order_by("code")

    def perform_create(self, serializer):
        """
        Crea la cuenta en una transacción que revierte posibles colisiones de código.

        @version 1.1
        @author Agustin
        """
        with transaction.atomic():
            serializer.save(company=self.get_company())


class AccountDetailView(AccountAccessMixin, generics.RetrieveUpdateAPIView):
    """
    Obtiene, actualiza o desactiva una cuenta sin eliminarla.

    @version 1.0
    @author Agustin
    """

    def perform_update(self, serializer):
        """
        Identifica la validación histórica del modelo para su respuesta HTTP.

        @version 1.1
        @author Agustin
        """
        try:
            serializer.save()
        except ValidationError as error:
            raise APIValidationError(error.messages, code="NEX-ACC-002") from error


class JournalEntryPublishView(CompanyAccessMixin, generics.GenericAPIView):
    """
    Publica un asiento borrador de una Company autorizada.

    @version 1.0
    @author Agustin
    """

    def post(self, request, company_id, pk):
        """
        Ejecuta la publicación y asigna un código a sus rechazos contables.

        @version 1.1
        @author Agustin
        """
        company = get_object_or_404(Company, pk=company_id)
        if not CompanyMember.objects.filter(user=request.user, company=company).exists():
            raise PermissionDenied()
        entry = get_object_or_404(JournalEntry, pk=pk, company=company)
        try:
            entry = publish_journal_entry(entry.pk)
        except ValidationError as error:
            raise APIValidationError(error.messages, code="NEX-ACC-003") from error
        return Response(
            {"id": entry.pk, "number": entry.number, "status": entry.status},
            status=status.HTTP_200_OK,
        )


class JournalEntryReverseView(CompanyAccessMixin, generics.GenericAPIView):
    """
    Revierte un asiento publicado de una Company autorizada.

    @version 1.0
    @author Agustin
    """

    def post(self, request, company_id, pk):
        """
        Ejecuta la reversión y asigna un código a sus rechazos contables.

        @version 1.1
        @author Agustin
        """
        company = get_object_or_404(Company, pk=company_id)
        if not CompanyMember.objects.filter(user=request.user, company=company).exists():
            raise PermissionDenied()
        entry = get_object_or_404(JournalEntry, pk=pk, company=company)
        try:
            reversal = reverse_journal_entry(entry.pk, user=request.user)
        except ValidationError as error:
            raise APIValidationError(error.messages, code="NEX-ACC-004") from error
        return Response(
            {"id": reversal.pk, "number": reversal.number, "status": reversal.status},
            status=status.HTTP_200_OK,
        )


class JournalEntryListView(JournalEntryHistoryMixin, generics.ListAPIView):
    """
    Lista cronológicamente los asientos del historial de una Company autorizada.

    @version 1.0
    @author Agustin
    """

    serializer_class = JournalEntrySerializer

    def get_queryset(self):
        """
        Aplica los filtros de fecha, estado y origen al historial contable.

        @version 1.0
        @author Agustin
        """
        entries = self.get_history_queryset()
        filters = JournalEntryListQuerySerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        entries = apply_date_range(entries, filters.validated_data)
        if "status" in filters.validated_data:
            entries = entries.filter(status=filters.validated_data["status"])
        if "source_type" in filters.validated_data:
            entries = entries.filter(source_type=filters.validated_data["source_type"])
        return entries.order_by("accounting_date", "number")


class JournalEntryDetailView(JournalEntryHistoryMixin, generics.RetrieveAPIView):
    """
    Devuelve el detalle completo de un asiento con sus movimientos.

    @version 1.0
    @author Agustin
    """

    serializer_class = JournalEntryDetailSerializer

    def get_queryset(self):
        """
        Devuelve el historial con los movimientos cargados en orden de registro.

        @version 1.0
        @author Agustin
        """
        return self.get_history_queryset().prefetch_related(LINES_PREFETCH)


class DailyJournalView(JournalEntryHistoryMixin, generics.ListAPIView):
    """
    Consulta cronológicamente los asientos del historial dentro de un rango.

    @version 1.0
    @author Agustin
    """

    serializer_class = JournalEntryDetailSerializer

    def get_queryset(self):
        """
        Devuelve el Libro Diario acotado al rango de fechas consultado.

        @version 1.0
        @author Agustin
        """
        entries = self.get_history_queryset()
        filters = DateRangeQuerySerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        entries = apply_date_range(entries, filters.validated_data)
        return entries.order_by("accounting_date", "number").prefetch_related(
            LINES_PREFETCH
        )


class GeneralLedgerView(JournalEntryHistoryMixin, generics.GenericAPIView):
    """
    Consulta el Libro Mayor de una cuenta de la Company autorizada.

    @version 1.0
    @author Agustin
    """

    serializer_class = GeneralLedgerRowSerializer

    def get(self, request, *args, **kwargs):
        """
        Devuelve los movimientos de la cuenta con su saldo acumulado.

        @version 1.0
        @author Agustin
        """
        account = get_object_or_404(
            Account, pk=self.kwargs["account_id"], company=self.get_company()
        )
        filters = DateRangeQuerySerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        history = self.get_history_queryset()
        entries = apply_date_range(history, filters.validated_data)
        lines = (
            JournalLine.objects.filter(account=account, journal_entry__in=entries)
            .select_related("journal_entry")
            .order_by("journal_entry__accounting_date", "journal_entry__number", "pk")
        )
        balance = self.get_opening_balance(account, history, filters.validated_data)
        rows = []
        for line in lines:
            balance += line.debit - line.credit
            rows.append(
                {
                    "accounting_date": line.journal_entry.accounting_date,
                    "entry_number": line.journal_entry.number,
                    "description": line.journal_entry.description,
                    "debit": line.debit,
                    "credit": line.credit,
                    "balance": balance,
                }
            )
        return Response(self.get_serializer(rows, many=True).data)

    def get_opening_balance(self, account, history, filters):
        """
        Calcula el saldo de la cuenta previo al inicio del rango consultado.

        Sin fecha inicial el rango cubre todo el historial y el saldo inicial es cero.

        @version 1.0
        @author Agustin
        """
        if "accounting_date_from" not in filters:
            return Decimal("0")
        prior_entries = history.filter(
            accounting_date__lt=filters["accounting_date_from"]
        )
        totals = JournalLine.objects.filter(
            account=account, journal_entry__in=prior_entries
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        debit = totals["debit"] or Decimal("0")
        credit = totals["credit"] or Decimal("0")
        return debit - credit


class TrialBalanceView(JournalEntryHistoryMixin, generics.ListAPIView):
    """
    Resume Debe, Haber y balance por cuenta dentro de un rango de fechas.

    @version 1.0
    @author Agustin
    """

    serializer_class = TrialBalanceRowSerializer

    def get_queryset(self):
        """
        Agrupa los movimientos del rango por cuenta sin persistir resultados.

        @version 1.0
        @author Agustin
        """
        entries = self.get_history_queryset()
        filters = DateRangeQuerySerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        entries = apply_date_range(entries, filters.validated_data)
        return (
            JournalLine.objects.filter(journal_entry__in=entries)
            .values("account_id", "account__code", "account__name")
            .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
            .annotate(balance=F("total_debit") - F("total_credit"))
            .order_by("account__code")
        )
