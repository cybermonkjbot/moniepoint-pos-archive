// Keep previously opened staff links usable without a second account directory.
frappe.pages["shop-staff"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({parent: wrapper, title: __("Users"), single_column: true});
};
frappe.pages["shop-staff"].on_page_show = function () {frappe.set_route("List", "User", "List");};
