app_name = "moniepoint_pos"
app_title = "Moniepoint POS"
app_publisher = "Joshua"
app_description = "Moniepoint terminal payment requests for ERPNext"
app_email = "developer@localhost.invalid"
app_license = "MIT"
required_apps = ["erpnext"]

page_js = {"point-of-sale": "public/js/k3ls_pos.js"}
app_include_js = ["/assets/moniepoint_pos/js/k3ls_shop_ui.js?v=20261003-4"]
app_include_css = ["/assets/moniepoint_pos/css/k3ls_shop_ui.css?v=20261003-5"]
boot_session = "moniepoint_pos.shop_ui.boot_session"
doctype_list_js = {doctype: "public/js/k3ls_list.js" for doctype in (
    "Supplier", "Customer", "Item", "K3LS Repair", "Purchase Invoice", "Payment Entry", "POS Invoice", "Sales Invoice", "POS Profile", "Moniepoint Terminal", "Moniepoint Transaction"
)}
doc_events = {"POS Invoice": {"before_submit": "moniepoint_pos.shop_setup.validate_sale"}}
