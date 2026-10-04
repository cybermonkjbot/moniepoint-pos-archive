frappe.k3ls_product_stock = async function (frm) {
    if (frm.is_new() || !frappe.user.has_role("System Manager")) return;
    const tab = frm.layout.tabs.find(tab => tab.df.fieldname === "inventory_section");
    if (!tab || !frm.doc.is_stock_item) return;
    if (!tab.k3ls_stock_refresh) {
        tab.k3ls_stock_refresh = true;
        tab.tab_link.find(".nav-link").on("click.k3ls-stock", () => {
            frm.k3ls_stock_key = null;
            frappe.k3ls_product_stock(frm);
        });
    }
    frm.k3ls_stock_panel ||= $("<section class='form-section k3ls-product-stock-panel'><div class='frappe-control'></div></section>").prependTo(tab.wrapper);
    const panel = frm.k3ls_stock_panel, content = panel.find(".frappe-control");
    panel.removeClass("empty-section").toggle(!frm.k3ls_more_fields);
    if (frm.k3ls_more_fields) return;
    tab.df.hidden = 0;
    tab.refresh();
    const key = `${frm.doc.name}:${frm.doc.modified}`;
    if (frm.k3ls_stock_key === key) return;
    frm.k3ls_stock_key = key;
    panel.attr("aria-busy", "true");
    frappe.k3ls_loading(content, "Loading stock");
    try {
        const {message: data} = await frappe.call({method: "moniepoint_pos.products.stock", type: "GET", args: {item: frm.doc.name}});
        if (frm.k3ls_stock_key !== key) return;
        content.empty();
        const card = $("<div class='k3ls-price-card'></div>").appendTo(content);
        $("<span></span>").text(__("In stock")).appendTo(card);
        $("<strong></strong>").text(__("{0} pieces", [format_number(data.quantity)])).appendTo(card);
        const actions = $("<div class='k3ls-product-actions'></div>").appendTo(content);
        $("<button type='button' class='btn btn-default'></button>").text(__("Restock"))
            .on("click", () => {if (frappe.boot.k3ls_operations_ready) {frappe.k3ls_workflow_add("intake", {products: [{item: data.item, quantity: 1}]}); return;} frappe.new_doc("Purchase Invoice", frappe.boot.k3ls_purchase_defaults || {}, invoice => {
                const row = frappe.model.add_child(invoice, "Purchase Invoice Item", "items");
                row.item_code = data.item;
                row.qty = 1;
            });}).appendTo(actions);
        if (data.can_adjust) $("<button type='button' class='btn btn-primary'></button>").text(__("Correct count"))
            .on("click", () => adjust(data)).appendTo(actions);
        if (frappe.model.can_create("Item")) $("<button type='button' class='btn btn-default'></button>").text(__("Add configuration"))
            .on("click", () => configuration(data)).appendTo(actions);
        if (data.serial_tracked) $("<p class='text-muted'></p>").text(__("This product keeps individual serial numbers. Add stock through Restock.")).appendTo(content);
    } catch (error) {
        if (frm.k3ls_stock_key !== key) return;
        frm.k3ls_stock_key = null;
        content.empty().append($("<p role='alert'></p>").text(__("Stock could not load.")));
        $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
            .on("click", () => frappe.k3ls_product_stock(frm)).appendTo(content);
    } finally {if (frm.k3ls_stock_key === key || frm.k3ls_stock_key === null) panel.attr("aria-busy", "false");}

    function saved() {
        if (!frm.is_dirty()) return true;
        frappe.msgprint(__("Save product details first."));
        return false;
    }

    function adjust(data) {
        if (!saved()) return;
        if (data.pending_sales) {frappe.msgprint(__("Close the till before correcting this product's stock count.")); return;}
        const dialog = new frappe.ui.Dialog({title: __("Correct stock count"), fields: [
            {fieldname: "quantity", fieldtype: "Int", label: __("Pieces in stock"), reqd: 1, default: data.quantity},
            {fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}],
            primary_action_label: __("Save count"), primary_action: async values => {
                if (!Number.isInteger(Number(values.quantity)) || Number(values.quantity) < 0) {
                    frappe.msgprint(__("Enter a whole number of pieces, zero or more.")); return;
                }
                const button = dialog.get_primary_btn();
                button.prop("disabled", true);
                try {
                    await frappe.call({method: "moniepoint_pos.products.set_stock", type: "POST",
                        args: {...values, item: data.item, modified: data.modified, stock_token: data.stock_token}});
                    dialog.hide();
                    frm.k3ls_stock_key = null;
                    await frm.reload_doc();
                } catch (error) {button.prop("disabled", false);}
            }});
        dialog.show();
    }

    function configuration(data) {
        if (!saved()) return;
        const dialog = new frappe.ui.Dialog({title: __("Add configuration"), fields: [
            {fieldname: "model", fieldtype: "Data", label: __("Model"), reqd: 1, default: frm.doc.custom_k3ls_model},
            {fieldname: "specifications", fieldtype: "Small Text", label: __("Specifications"), reqd: 1, default: frm.doc.custom_k3ls_configuration},
            {fieldname: "mode", fieldtype: "Data", label: __("Mode"), default: frm.doc.custom_k3ls_mode},
            {fieldname: "colour", fieldtype: "Data", label: __("Colour"), default: frm.doc.custom_k3ls_colour}],
            primary_action_label: __("Add product"), primary_action: async values => {
                const button = dialog.get_primary_btn();
                button.prop("disabled", true);
                try {
                    const {message} = await frappe.call({method: "moniepoint_pos.products.add_configuration", type: "POST",
                        args: {...values, item: data.item, modified: data.modified}});
                    dialog.hide();
                    frappe.set_route("Form", "Item", message.item);
                } catch (error) {button.prop("disabled", false);}
            }});
        dialog.show();
    }
};
