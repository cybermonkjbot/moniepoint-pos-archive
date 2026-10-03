"""K3LS product catalogue. Keep ERPNext stock, prices and scan handling."""
import frappe
from frappe.utils import cint


@frappe.whitelist(methods=["GET"])
def products(start=0, page_length=40, search_term="", item_group=None, pos_profile="K3LS Shop"):
    from erpnext.selling.page.point_of_sale.point_of_sale import check_pos_profile_access, get_items

    check_pos_profile_access(pos_profile)
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    if profile.name != "K3LS Shop" or profile.company != "K3LS LIMITED" or profile.disabled:
        frappe.throw("Choose the K3LS shop.")
    users = {row.user for row in profile.applicable_for_users}
    if users and frappe.session.user not in users and frappe.session.user != "Administrator":
        frappe.throw("You cannot use this till.", frappe.PermissionError)
    result = get_items(max(cint(start), 0), min(max(cint(page_length), 1), 100),
        profile.selling_price_list, item_group, profile.name, search_term) or {}
    result["items"] = [item for item in result.get("items", []) if item.get("is_stock_item")]
    return result


def configure():
    frappe.only_for("System Manager")
    profile = frappe.get_doc("POS Profile", "K3LS Shop")
    profile.set("item_groups", [row for row in profile.item_groups
        if row.item_group not in ("Repair Services", "Dispatch Services")])
    if not profile.item_groups:
        for group in ("Laptop", "Accessories"):
            profile.append("item_groups", {"item_group": group})
    profile.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"catalogue": "physical products", "stock_posted": False}
