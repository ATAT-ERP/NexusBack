from django.db import transaction

from apps.billing.models import FiscalProfile, InvoiceSequence, PointOfSale


def assign_point_of_sale_number(fiscal_profile):
    """
    Asigna atómicamente el siguiente número disponible de punto de
    venta dentro del perfil fiscal indicado, bloqueando el perfil
    fiscal padre para evitar colisiones en peticiones simultáneas,
    incluida la creación del primer punto de venta.
    @version 1.0
    @author Thiago
    """
    with transaction.atomic():
        FiscalProfile.objects.select_for_update().get(pk=fiscal_profile.pk)

        last_point_of_sale = (
            PointOfSale.objects.filter(fiscal_profile=fiscal_profile)
            .order_by("-number")
            .first()
        )
        next_number = last_point_of_sale.number + 1 if last_point_of_sale else 1
        return PointOfSale.objects.create(
            fiscal_profile=fiscal_profile,
            number=next_number,
        )


def next_invoice_number(point_of_sale, invoice_type):
    """
    Obtiene atómicamente el siguiente número correlativo de un tipo
    de comprobante para un punto de venta. La secuencia se crea la
    primera vez que se necesita, comenzando en 1 (00000001).
    @version 1.0
    @author Thiago
    """
    with transaction.atomic():
        sequence, _ = InvoiceSequence.objects.select_for_update().get_or_create(
            point_of_sale=point_of_sale,
            invoice_type=invoice_type,
            defaults={"last_number": 0},
        )
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
        return sequence.last_number