from apps.billing.views.credit_note import (
    CreditNoteDetailView,
    CreditNoteIssueView,
    CreditNoteListCreateView,
)
from apps.billing.views.credit_note_invoice import (
    CreditNoteInvoiceDetailView,
    CreditNoteInvoiceListCreateView,
)
from apps.billing.views.credit_note_item import (
    CreditNoteItemDetailView,
    CreditNoteItemListCreateView,
)
from apps.billing.views.fiscal_profile import FiscalProfileView
from apps.billing.views.invoice import (
    InvoiceDetailView,
    InvoiceIssueView,
    InvoiceListCreateView,
)
from apps.billing.views.invoice_item import (
    InvoiceItemDetailView,
    InvoiceItemListCreateView,
)
from apps.billing.views.point_of_sale import (
    PointOfSaleActivateView,
    PointOfSaleDeactivateView,
    PointOfSaleDetailView,
    PointOfSaleListCreateView,
)

__all__ = (
    "CreditNoteDetailView",
    "CreditNoteInvoiceDetailView",
    "CreditNoteInvoiceListCreateView",
    "CreditNoteIssueView",
    "CreditNoteItemDetailView",
    "CreditNoteItemListCreateView",
    "CreditNoteListCreateView",
    "FiscalProfileView",
    "InvoiceDetailView",
    "InvoiceIssueView",
    "InvoiceItemDetailView",
    "InvoiceItemListCreateView",
    "InvoiceListCreateView",
    "PointOfSaleActivateView",
    "PointOfSaleDeactivateView",
    "PointOfSaleDetailView",
    "PointOfSaleListCreateView",
)