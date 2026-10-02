frappe.ui.form.on("K3LS Repair", {
    refresh(frm) {
        if (!frm.is_new() && frappe.user.has_role("System Manager")) {
            frm.add_custom_button(__(frm.doc.sales_invoice ? "Open invoice" : "Create invoice"), () => {
                if (frm.doc.sales_invoice) {
                    frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
                    return;
                }
                frappe.confirm(__("Create a draft invoice for this repair?"), () => {
                    frm.call("create_invoice").then(({ message }) => {
                        if (message) frappe.set_route("Form", "Sales Invoice", message);
                    });
                });
            });
        }
    },
});
