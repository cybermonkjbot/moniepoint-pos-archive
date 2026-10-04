(() => {
    const ready = () => Boolean(frappe.boot?.k3ls_operations_ready);
    const route = (kind, name) => frappe.set_route("shop-operations", kind, ...(name ? [name] : []));
    frappe.k3ls_workflow_add = async (kind, defaults = {}) => {
        if (frappe.get_route()[0] === "shop-operations" && frappe.get_route()[1] === kind) {
            const page = frappe.k3ls_operations_page;
            if (page?.add_record) return page.add_record(kind, null, defaults);
        }
        // The page-show handler owns initialization and consumes one pending draft.
        frappe.k3ls_pending_workflow = {kind, defaults};
        await route(kind);
    };
    frappe.k3ls_workflow_route = route;
    frappe.ui.form.on("Item", {refresh(frm) {
        if (!ready() || frm.is_new()) return;
        frm.add_custom_button(__("Receive stock"), () => frappe.k3ls_workflow_add("intake", {products: [{item: frm.doc.name, quantity: 1}], ownership: frm.doc.custom_k3ls_ownership || "K3LS Owned"}));
        frm.add_custom_button(__("Check condition"), () => frappe.k3ls_workflow_add("inspection", {item: frm.doc.name, serials: frm.doc.custom_k3ls_serial}));
        frm.add_custom_button(__("Stock history"), () => route("inventory", frm.doc.name));
    }});
    frappe.ui.form.on("Supplier", {refresh(frm) {
        if (!ready() || frm.is_new() || !frappe.user.has_role("System Manager")) return;
        frm.add_custom_button(__("Receive stock"), () => frappe.k3ls_workflow_add("intake", {supplier: frm.doc.name}));
        frm.add_custom_button(__("Money we owe"), () => route("payables"));
    }});
    for (const type of ["POS Invoice", "Sales Invoice"]) frappe.ui.form.on(type, {refresh(frm) {
        if (!ready() || frm.is_new()) return;
        if (frm.doc.docstatus === 0 && !frm.doc.is_return) frm.add_custom_button(__("Ask for credit approval"), async () => {
            await frm.save();
            await frappe.call({method: "moniepoint_pos.operations.save", type: "POST", args: {kind: "requests", request_key: window.crypto.randomUUID(),
                values: {request_type: "Credit sale", title: `Credit sale ${frm.doc.name}`, related_doctype: type, related_name: frm.doc.name,
                    reason: `${frm.doc.customer} · ${format_currency(frm.doc.outstanding_amount || frm.doc.grand_total - frm.doc.paid_amount, "NGN")}`}}});
            route("requests");
        });
        if (frm.doc.docstatus === 1) {
            if (!frm.doc.is_return) frm.add_custom_button(__("Return or exchange"), () => frappe.k3ls_workflow_add("returns", {invoice_type: type, invoice: frm.doc.name}));
            if (frappe.user.has_role("System Manager") && frm.doc.outstanding_amount > 0) frm.add_custom_button(__("Plan payments"), () => frappe.k3ls_workflow_add("plans", {reference_type: type, reference_name: frm.doc.name}));
        }
    }});
})();
