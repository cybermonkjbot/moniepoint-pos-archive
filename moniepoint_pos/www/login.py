"""Shop branding around Frappe's existing authentication page."""

from frappe import _
from frappe.www.login import get_context as frappe_login_context

from moniepoint_pos.shop_ui import enabled

no_cache = True
sitemap = 0


def get_context(context):
    frappe_login_context(context)
    context.k3ls_login = bool(enabled())
    if context.k3ls_login:
        context.title = _("Sign in") + " | K3LS"
        context.body_class = (context.get("body_class") or "") + " k3ls-login-page"
        context.logo = "/assets/moniepoint_pos/images/k3ls-loading-logo.png"
        context.login_label = _("Username")
        context.login_name_placeholder = _("Username")
        context.disable_signup = 1
        context.disable_user_pass_login = 0
        context.social_login = False
        context.login_with_email_link = False
        context.ldap_settings = None
    return context
