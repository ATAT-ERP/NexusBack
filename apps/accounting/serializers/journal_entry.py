from rest_framework import serializers

from apps.accounting.enums import EntryOrigin, EntryStatus
from apps.accounting.models import JournalEntry, JournalLine


class JournalLineSerializer(serializers.ModelSerializer):
    """
    Serializa los movimientos de un asiento con los datos de su cuenta.

    @version 1.0
    @author Antonio
    """

    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = (
            "id",
            "account",
            "account_code",
            "account_name",
            "description",
            "debit",
            "credit",
        )


class JournalEntrySerializer(serializers.ModelSerializer):
    """
    Serializa los datos de un asiento del historial contable.

    @version 1.0
    @author Antonio
    """

    class Meta:
        model = JournalEntry
        fields = (
            "id",
            "number",
            "accounting_date",
            "description",
            "status",
            "source_type",
            "source_id",
            "currency",
            "created_by",
            "reversal_of",
            "metadata",
            "created_at",
            "updated_at",
        )


class JournalEntryDetailSerializer(JournalEntrySerializer):
    """
    Agrega los movimientos al detalle de un asiento.

    @version 1.0
    @author Antonio
    """

    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta(JournalEntrySerializer.Meta):
        fields = JournalEntrySerializer.Meta.fields + ("lines",)


class DateRangeQuerySerializer(serializers.Serializer):
    """
    Valida el rango de fechas contables de las consultas.

    @version 1.0
    @author Antonio
    """

    accounting_date_from = serializers.DateField(required=False)
    accounting_date_to = serializers.DateField(required=False)


class JournalEntryListQuerySerializer(DateRangeQuerySerializer):
    """
    Valida los filtros del historial de asientos.

    @version 1.0
    @author Antonio
    """

    status = serializers.ChoiceField(choices=EntryStatus.choices, required=False)
    source_type = serializers.ChoiceField(choices=EntryOrigin.choices, required=False)


class GeneralLedgerRowSerializer(serializers.Serializer):
    """
    Serializa un movimiento del Libro Mayor con su saldo acumulado.

    @version 1.0
    @author Antonio
    """

    accounting_date = serializers.DateField()
    entry_number = serializers.IntegerField()
    description = serializers.CharField()
    debit = serializers.DecimalField(max_digits=18, decimal_places=2)
    credit = serializers.DecimalField(max_digits=18, decimal_places=2)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2)


class TrialBalanceRowSerializer(serializers.Serializer):
    """
    Serializa el agregado por cuenta de Sumas y Saldos.

    @version 1.0
    @author Antonio
    """

    account = serializers.IntegerField(source="account_id")
    code = serializers.CharField(source="account__code")
    name = serializers.CharField(source="account__name")
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_credit = serializers.DecimalField(max_digits=18, decimal_places=2)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2)
