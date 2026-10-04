app_name = "moniepoint_pos"
app_title = "Moniepoint POS"
app_publisher = "Joshua"
app_description = "Moniepoint terminal payment requests for ERPNext"
app_email = "developer@localhost.invalid"
app_license = "MIT"
required_apps = ["erpnext"]

page_js = {"point-of-sale": "public/js/k3ls_pos.js", "permission-manager": "public/js/k3ls_permissions.js"}
app_include_js = ["/assets/moniepoint_pos/js/k3ls_prices.js?v=20261004-11", "/assets/moniepoint_pos/js/k3ls_products.js?v=20261004-11", "/assets/moniepoint_pos/js/k3ls_workflows.js?v=20261004-11", "/assets/moniepoint_pos/js/k3ls_shop_ui.js?v=20261004-11", "/assets/moniepoint_pos/js/k3ls_security.js?v=20261004-7"]
app_include_css = ["/assets/moniepoint_pos/css/k3ls_shop_ui.css?v=20261004-11"]
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
doc_events = {
    "Item": {"validate": "moniepoint_pos.products.validate_product"},
    "POS Invoice": {"before_submit": ["moniepoint_pos.products.lock_sale_stock", "moniepoint_pos.ops_sales.validate_sale",
        "moniepoint_pos.shop_setup.validate_sale", "moniepoint_pos.ops_money.validate_checkout", "moniepoint_pos.ops_sales.snapshot_owner_return", "moniepoint_pos.pricing.snapshot_sale_costs"],
        "on_submit": ["moniepoint_pos.ops_money.owner_sale", "moniepoint_pos.ops_sales.update_units"], "before_cancel": ["moniepoint_pos.ops_money.guard_invoice_cancel", "moniepoint_pos.ops_money.cancel_owner_sale", "moniepoint_pos.ops_sales.remember_units"], "on_cancel": "moniepoint_pos.ops_sales.update_units"},
    "Sales Invoice": {"before_validate": "moniepoint_pos.ops_sales.prepare_return_credit", "before_submit": ["moniepoint_pos.products.lock_sale_stock",
        "moniepoint_pos.ops_sales.validate_sale", "moniepoint_pos.ops_sales.snapshot_owner_return", "moniepoint_pos.pricing.snapshot_sale_costs"],
        "on_submit": ["moniepoint_pos.ops_money.owner_sale", "moniepoint_pos.ops_sales.update_units"], "before_cancel": ["moniepoint_pos.ops_money.guard_invoice_cancel", "moniepoint_pos.ops_money.cancel_owner_sale", "moniepoint_pos.ops_sales.remember_units"], "on_cancel": "moniepoint_pos.ops_sales.update_units"},
    "Payment Entry": {"before_submit": "moniepoint_pos.ops_money.guard_payment_submit", "before_cancel": "moniepoint_pos.ops_money.guard_payment_cancel"},
    "Journal Entry": {"before_cancel": "moniepoint_pos.ops_money.guard_payment_cancel"},
}
from moniepoint_pos.operations_schema import SCHEMAS
permission_query_conditions = {name: "moniepoint_pos.operations.query_conditions" for name, definition in SCHEMAS.items()
    if definition["staff"] and not definition["child"] and name != "K3LS Stock Unit"}
has_permission = {name: "moniepoint_pos.operations.has_permission" for name, definition in SCHEMAS.items() if not definition["child"]}
permission_query_conditions["K3LS Stock Movement"] = "moniepoint_pos.operations.movement_query_conditions"
for name, definition in SCHEMAS.items():
    if not definition["child"]:
        doc_events[name] = {"validate": "moniepoint_pos.operations.validate", "on_update": "moniepoint_pos.operations.history",
            "on_trash": "moniepoint_pos.operations.no_delete"}
