frappe.pages["shop-profit"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Overview"), single_column: true});
    frappe.k3ls_loading(page.main, "Loading overview");
};
// Keep saved links working without a second read-only destination.
frappe.pages["shop-profit"].on_page_show = function () {frappe.set_route("shop-accounts");};
