"""Old password links lead to code recovery or the signed-in password dialog."""

import frappe
from frappe.www.update_password import get_context as core_context
from moniepoint_pos.shop_ui import enabled

no_cache = True


def get_context(context):
    if enabled():
        from urllib.parse import quote
        frappe.local.flags.redirect_location = "/login#forgot" if frappe.session.user == "Guest" else "/desk/user/" + quote(frappe.session.user, safe="") + "#settings_tab"
        raise frappe.Redirect
    return core_context(context)
