"""Compatibility setup for previously opened staff links."""
import frappe


def configure():
    frappe.only_for("System Manager")
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-staff", force=True)
    from moniepoint_pos.navigation import simplify_links
    simplify_links()
    return {"page": "shop-staff", "target": "User", "accounts_changed": False}
