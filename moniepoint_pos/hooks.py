app_name = "moniepoint_pos"
app_title = "Moniepoint POS"
app_publisher = "Joshua"
app_description = "Moniepoint terminal payment requests for ERPNext"
app_email = "developer@localhost.invalid"
app_license = "MIT"
required_apps = ["erpnext"]

page_js = {"point-of-sale": "public/js/k3ls_pos.js", "permission-manager": "public/js/k3ls_permissions.js"}
app_include_js = ["/assets/moniepoint_pos/js/k3ls_prices.js?v=20261003-47", "/assets/moniepoint_pos/js/k3ls_shop_ui.js?v=20261004-4", "/assets/moniepoint_pos/js/k3ls_security.js?v=20261004-2"]
app_include_css = ["/assets/moniepoint_pos/css/k3ls_shop_ui.css?v=20261004-6"]
boot_session = "moniepoint_pos.shop_ui.boot_session"
update_website_context = "moniepoint_pos.branding.website_context"
before_login = "moniepoint_pos.security.before_login"
before_request = ["moniepoint_pos.security.before_request"]
extend_doctype_class = {"User": ["moniepoint_pos.user_security.ShopUserSecurity"]}
override_whitelisted_methods = {
    "frappe.core.doctype.user.user.reset_password": "moniepoint_pos.security.email_reset_disabled",
    "frappe.core.doctype.user.user.update_password": "moniepoint_pos.security.password_update",
    "frappe.www.login.send_login_link": "moniepoint_pos.security.email_reset_disabled",
}
doctype_list_js = {doctype: "public/js/k3ls_list.js" for doctype in (
    "Supplier", "Customer", "Item", "K3LS Repair", "Purchase Invoice", "Payment Entry", "POS Invoice", "Sales Invoice", "POS Profile", "Moniepoint Terminal", "Moniepoint Transaction", "User"
)}
doc_events = {"POS Invoice": {"before_submit": "moniepoint_pos.shop_setup.validate_sale"}}
