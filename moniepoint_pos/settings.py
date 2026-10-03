"""Moniepoint administration. These methods never contact the payment provider."""
import frappe
from frappe.utils import cint

COMPANY = "K3LS LIMITED"
REQUEST_STATES = ("Created", "Accepted", "Unknown", "Rejected")
PROVIDER_STATES = ("PENDING", "PROCESSED", "COMPLETED", "CANCELLED", "SUCCESSFUL", "FAILED", "REJECTED", "EXPIRED")
TERMINAL_FIELDS = ("terminal_serial", "company", "pos_profile", "mode_of_payment", "payment_method", "enabled")


def operator():
    frappe.only_for("System Manager")
    frappe.get_single("Moniepoint Settings").check_permission("read")


@frappe.whitelist(methods=["GET"])
def overview(request_state=None, provider_state=None, start=0):
    operator()
    terminals = frappe.get_list("Moniepoint Terminal", filters={"company": COMPANY},
        fields=["name", "modified", *TERMINAL_FIELDS], order_by="terminal_serial asc", limit_page_length=0)
    for terminal in terminals:
        terminal.has_requests = bool(frappe.get_list("Moniepoint Transaction", filters={"terminal": terminal.name},
            fields=["name"], limit_page_length=1))
    filters = {"terminal": ["in", [terminal.name for terminal in terminals]]}
    counts = frappe.get_list("Moniepoint Transaction", filters=filters,
        fields=["state", {"COUNT": "name", "as": "count"}], group_by="state", order_by=None, limit_page_length=10)
    if request_state:
        if request_state not in REQUEST_STATES:
            frappe.throw("Choose a valid request status.")
        filters["state"] = request_state
    if provider_state:
        if provider_state not in PROVIDER_STATES:
            frappe.throw("Choose a valid Moniepoint status.")
        filters["processing_status"] = provider_state
    start = max(0, cint(start))
    transactions = frappe.get_list("Moniepoint Transaction", filters=filters,
        fields=["name", "invoice", "terminal", "merchant_reference", "request_amount", "amount_units",
            "state", "processing_status", "actual_amount", "last_checked", "creation"],
        order_by="creation desc", limit_start=start, limit_page_length=51)
    return {"terminals": terminals, "transactions": transactions[:50], "has_more": len(transactions) > 50,
        "counts": {row.state: row.count for row in counts},
        "can_create": frappe.has_permission("Moniepoint Terminal", "create"),
        "can_write": frappe.has_permission("Moniepoint Terminal", "write")}


@frappe.whitelist(methods=["POST"])
def save_terminal(values, name=None, modified=None):
    operator()
    values = frappe.parse_json(values)
    if not isinstance(values, dict) or set(values) - set(TERMINAL_FIELDS):
        frappe.throw("Invalid terminal details.")
    if name:
        doc = frappe.get_doc("Moniepoint Terminal", name, for_update=True)
        doc.check_permission("write")
        if doc.company != COMPANY:
            frappe.throw("This terminal belongs to another company.")
        if not modified or str(doc.modified) != str(modified):
            frappe.throw("This terminal changed. Close this window and reload before editing.")
        if frappe.db.exists("Moniepoint Transaction", {"terminal": doc.name}):
            for field in TERMINAL_FIELDS:
                if field != "enabled" and values.get(field, doc.get(field)) != doc.get(field):
                    frappe.throw("A terminal with payment requests cannot be remapped. Add a new terminal instead.")
    else:
        frappe.has_permission("Moniepoint Terminal", "create", throw=True)
        doc = frappe.new_doc("Moniepoint Terminal")
    doc.update(values)
    doc.company = COMPANY
    doc.enabled = cint(doc.enabled)
    doc.terminal_serial = (doc.terminal_serial or "").strip()
    if not doc.terminal_serial:
        frappe.throw("Add the terminal serial number.")
    if doc.payment_method not in ("CARD_PURCHASE", "POS_TRANSFER", "ANY"):
        frappe.throw("Choose a valid payment type.")
    profile = frappe.get_doc("POS Profile", doc.pos_profile)
    profile.check_permission("read")
    if profile.company != COMPANY or profile.disabled:
        frappe.throw("Choose an active K3LS till.")
    payment = frappe.get_doc("Mode of Payment", doc.mode_of_payment)
    payment.check_permission("read")
    if profile.name == "K3LS Shop" and payment.name != "Moniepoint MFB":
        frappe.throw("Use Moniepoint for terminal payments. Cash is recorded separately.")
    if not payment.enabled or not any(row.mode_of_payment == payment.name for row in profile.payments):
        frappe.throw("Choose a payment method available on this till.")
    doc.save()
    return {"name": doc.name}
