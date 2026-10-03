"""K3LS operational configuration. No stock, cash or payments are posted."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.modules.import_file import import_file
from frappe.permissions import add_permission


COMPANY = "K3LS LIMITED"
PROFILE = "K3LS Shop"


def configure():
    frappe.only_for("System Manager")
    from moniepoint_pos.client_setup import configure as configure_masters
    configure_masters()
    if not frappe.db.exists("Role", "K3LS Repair Staff"):
        frappe.get_doc({"doctype": "Role", "role_name": "K3LS Repair Staff", "desk_access": 1}).insert()
    import_file("Moniepoint POS", "DocType", "K3LS Repair", force=True)
    configure_fields()
    configure_receipt()
    configure_pos()
    sidebar = frappe.get_doc("Workspace Sidebar", PROFILE)
    for row in sidebar.items:
        if row.label == "Repairs":
            row.link_type = "Page" if frappe.db.exists("Page", "shop-repairs") else "DocType"
            row.link_to = "shop-repairs" if row.link_type == "Page" else "K3LS Repair"
    sidebar.save()
    from moniepoint_pos.shop_ui import configure as configure_ui
    configure_ui()
    frappe.clear_cache()
    frappe.db.commit()
    return {"pos_profile": PROFILE, "repair_register": "K3LS Repair", "receipt": "K3LS Receipt",
        "invoice_type": "POS Invoice", "opening_shift_created": False,
        "opening_stock_posted": False, "bank_balances_posted": False}


def configure_fields():
    item_fields = [
        {"fieldname": "custom_k3ls_device", "fieldtype": "Section Break", "label": "K3LS device details", "insert_after": "description"},
        {"fieldname": "custom_k3ls_model", "fieldtype": "Data", "label": "Model"},
        {"fieldname": "custom_k3ls_serial", "fieldtype": "Data", "label": "Serial / IMEI"},
        {"fieldname": "custom_k3ls_configuration", "fieldtype": "Small Text", "label": "Configuration"},
        {"fieldname": "custom_k3ls_colour", "fieldtype": "Data", "label": "Colour"},
        {"fieldname": "custom_k3ls_ownership", "fieldtype": "Select", "label": "Stock ownership", "options": "\nK3LS Owned\nSister Owned\nThird-party Owner"},
        {"fieldname": "custom_k3ls_owner", "fieldtype": "Link", "label": "Owner / source", "options": "Supplier"},
        {"fieldname": "custom_k3ls_arrival_condition", "fieldtype": "Small Text", "label": "Arrival faults / condition"},
        {"fieldname": "custom_k3ls_final_condition", "fieldtype": "Small Text", "label": "Final verified condition"},
        {"fieldname": "custom_k3ls_acquisition", "fieldtype": "Section Break", "label": "Acquisition details", "permlevel": 1},
        {"fieldname": "custom_k3ls_acquired_on", "fieldtype": "Date", "label": "Acquired", "permlevel": 1},
        {"fieldname": "custom_k3ls_acquisition_type", "fieldtype": "Select", "label": "Acquisition type", "options": "\nSupplier Purchase\nSwap / Trade-in\nThird-party Custody", "permlevel": 1},
        {"fieldname": "custom_k3ls_purchase_cost", "fieldtype": "Currency", "label": "Recorded purchase cost", "options": "NGN", "permlevel": 1},
        {"fieldname": "custom_k3ls_landing_cost", "fieldtype": "Currency", "label": "Recorded landing cost", "options": "NGN", "permlevel": 1},
    ]
    previous = "custom_k3ls_device"
    for field in item_fields[1:]:
        field["insert_after"] = previous
        previous = field["fieldname"]
    sale_fields = [
        {"fieldname": "custom_k3ls_condition", "label": "Condition and faults by Item ID", "fieldtype": "Small Text"},
        {"fieldname": "custom_k3ls_tested", "label": "Testing at sale", "fieldtype": "Select", "options": "\nFully tested\nPartially tested\nNot tested"},
        {"fieldname": "custom_k3ls_acknowledged", "label": "Customer acknowledged condition", "fieldtype": "Check"},
        {"fieldname": "custom_k3ls_disclosure_ref", "label": "Condition disclosure / receipt reference", "fieldtype": "Data"},
    ]
    for index, field in enumerate(sale_fields):
        field["insert_after"] = sale_fields[index - 1]["fieldname"] if index else "customer"
        field["no_copy"] = 1
    create_custom_fields({
        "Item": item_fields,
        "POS Invoice": sale_fields,
        "Sales Invoice": [{"fieldname": "custom_k3ls_repair", "label": "Repair", "fieldtype": "Link",
            "options": "K3LS Repair", "insert_after": "customer", "read_only": 1, "no_copy": 1}],
    })
    if not frappe.db.exists("Custom DocPerm", {"parent": "Item", "role": "System Manager", "permlevel": 1}):
        permission_name = add_permission("Item", "System Manager", permlevel=1)
        permission = frappe.get_doc("Custom DocPerm", permission_name)
        permission.write = 1
        permission.save()
    from moniepoint_pos.stock_details import apply_workbook_details
    apply_workbook_details()


def configure_receipt():
    html = frappe.read_file(frappe.get_app_path("moniepoint_pos", "templates", "k3ls_receipt.html"))
    if not frappe.db.exists("Print Format", "K3LS Receipt"):
        frappe.get_doc({"doctype": "Print Format", "name": "K3LS Receipt", "doc_type": "POS Invoice",
            "standard": "No", "custom_format": 1, "print_format_type": "Jinja", "html": html,
            "font_size": 11, "margin_top": 4, "margin_bottom": 4, "margin_left": 4, "margin_right": 4}).insert()


def configure_pos():
    profile = frappe.get_doc("POS Profile", PROFILE)
    profile.update({"action_on_new_invoice": "Always Ask", "validate_stock_on_save": 1,
        "account_for_change_amount": f"Cash - {frappe.get_cached_value('Company', COMPANY, 'abbr')}",
        "set_grand_total_to_default_mop": 0, "disable_rounded_total": 1,
        "hide_images": 1, "auto_add_item_to_cart": 1, "print_format": "K3LS Receipt",
        "allow_rate_change": 0, "allow_discount_change": 0, "write_off_limit": 0})
    if not profile.item_groups:
        for group in ("Laptop", "Accessories"):
            profile.append("item_groups", {"item_group": group})
    if not any(row.user == "Administrator" for row in profile.applicable_for_users):
        profile.append("applicable_for_users", {"user": "Administrator", "default": 1})
    profile.save()
    settings = frappe.get_single("POS Settings")
    if settings.invoice_type != "POS Invoice" and frappe.db.count("Sales Invoice"):
        frappe.throw("Review existing Sales Invoices before changing the POS invoice type.")
    settings.invoice_type = "POS Invoice"
    existing = {row.fieldname for row in settings.invoice_fields}
    for name in ("custom_k3ls_condition", "custom_k3ls_tested", "custom_k3ls_acknowledged", "custom_k3ls_disclosure_ref"):
        if name not in existing:
            df = frappe.get_meta("POS Invoice").get_field(name)
            settings.append("invoice_fields", {"fieldname": name, "label": df.label,
                "fieldtype": df.fieldtype, "options": df.options, "reqd": 1})
    settings.save()
    options = frappe.get_meta("POS Invoice").get_field("naming_series").options.split("\n")
    if "K3LS-INV-.#####" not in options:
        options.append("K3LS-INV-.#####")
        make_property_setter("POS Invoice", "naming_series", "options", "\n".join(options), "Text")
    make_property_setter("POS Invoice", "naming_series", "default", "K3LS-INV-.#####", "Text")


@frappe.whitelist(methods=["GET"])
def opening_defaults():
    if not frappe.db.exists("POS Profile", PROFILE):
        return None
    profile = frappe.get_doc("POS Profile", PROFILE)
    if not profile.has_permission("read") or profile.disabled:
        return None
    users = {row.user for row in profile.applicable_for_users}
    if users and frappe.session.user not in users and frappe.session.user != "Administrator":
        return None
    return {"profile": PROFILE, "company": profile.company,
        "payments": [row.mode_of_payment for row in profile.payments], "cash_method": "Cash"}


def validate_sale(doc, method=None):
    if doc.pos_profile != PROFILE or doc.company != COMPANY or doc.is_return:
        return
    if not doc.custom_k3ls_condition or not doc.custom_k3ls_tested or not doc.custom_k3ls_acknowledged or not doc.custom_k3ls_disclosure_ref:
        frappe.throw("Add the condition, testing result and condition reference. Confirm the customer accepts the condition.")
    for row in doc.items:
        if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
            frappe.throw("Use Repairs for repair work. The POS is for products.")
        ownership = frappe.get_cached_value("Item", row.item_code, "custom_k3ls_ownership")
        if ownership in ("Sister Owned", "Third-party Owner"):
            frappe.throw("This product belongs to someone else. Owner payouts must be set up before it can be sold.")
    from frappe.utils import flt, getdate, today
    total = flt(doc.rounded_total) or flt(doc.grand_total)
    if flt(total - flt(doc.paid_amount), doc.precision("grand_total")) > 0:
        if not doc.customer or doc.customer == "K3LS Walk-in Customer" or not doc.contact_mobile:
            frappe.throw("For part payments, choose the customer and add their phone number.")
        if not doc.due_date or getdate(doc.due_date) < getdate(today()):
            frappe.throw("Choose when the remaining payment is due, today or later.")
