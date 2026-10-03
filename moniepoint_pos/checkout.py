"""Focused checkout configuration. Never changes invoices, shifts or balances."""
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.file_manager import save_file

COMPANY = "K3LS LIMITED"
PROFILE = "K3LS Shop"
PAYMENT_METHODS = ("Cash", "Moniepoint MFB", "FCMB", "UBA")


def configure():
    frappe.only_for("System Manager")
    profile = frappe.get_doc("POS Profile", PROFILE, for_update=True)
    profile.check_permission("write")
    if profile.company != COMPANY:
        frappe.throw("This checkout belongs to another company.")
    for method in PAYMENT_METHODS:
        payment = frappe.get_doc("Mode of Payment", method)
        if not payment.enabled or not any(row.company == COMPANY and row.default_account for row in payment.accounts):
            frappe.throw(f"Set up the {method} account before changing checkout.")
    backup_name = "k3ls-checkout-before-company-banks.json"
    if not frappe.db.exists("File", {"file_name": backup_name}):
        save_file(backup_name, frappe.as_json(profile.as_dict()), None, None, is_private=1)
    existing = {row.mode_of_payment: row for row in profile.payments}
    rows = []
    for method in PAYMENT_METHODS:
        row = existing.get(method) or profile.append("payments", {"mode_of_payment": method})
        row.default = int(method == "Cash")
        rows.append(row)
    profile.set("payments", rows)
    profile.update({"allow_partial_payment": 1, "update_stock": 1, "validate_stock_on_save": 1,
        "set_grand_total_to_default_mop": 0, "disable_rounded_total": 1,
        "allow_rate_change": 0, "allow_discount_change": 0, "write_off_limit": 0})
    profile.save()
    from moniepoint_pos.shop_ui import FORMS
    for field, label in FORMS["POS Profile"]["labels"].items():
        if frappe.get_meta("POS Profile").has_field(field):
            make_property_setter("POS Profile", field, "label", label, "Data")
    from moniepoint_pos.navigation import simplify_links
    simplify_links()
    frappe.clear_cache()
    frappe.db.commit()
    return {"profile": PROFILE, "payments": list(PAYMENT_METHODS), "default": "Cash",
        "partial_payments": True, "backup": backup_name, "financial_records_changed": False}
