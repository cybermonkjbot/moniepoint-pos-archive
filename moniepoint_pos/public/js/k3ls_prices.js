frappe.k3ls_product_prices = async function (frm) {
    const control = frm.fields_dict.prices_html;
    if (!control || frm.is_new() || !frappe.user.has_role("System Manager")) return;
    const tab = frm.layout.tabs.find(tab => tab.df.fieldname === "pricing_tab");
    if (!tab) return;
    if (!frm.k3ls_price_panel) frm.k3ls_price_panel = $("<section class='form-section k3ls-product-prices'></section>").appendTo(tab.wrapper);
    const panel = frm.k3ls_price_panel;
    // Layout.refresh_sections counts visible .frappe-control children. Keep the
    // custom price content registered as a visible control instead of an empty section.
    if (!frm.k3ls_price_content) frm.k3ls_price_content = $("<div class='frappe-control'></div>").appendTo(panel);
    const content = frm.k3ls_price_content;
    panel.removeClass("empty-section");
    panel.toggle(!frm.k3ls_more_fields);
    control.$wrapper.closest(".form-section").find(".column-label").toggle(Boolean(frm.k3ls_more_fields));
    frm.toggle_display("prices_html", Boolean(frm.k3ls_more_fields));
    if (frm.k3ls_more_fields) return;
    if (tab) {tab.df.hidden = 0; tab.refresh();}
    if (erpnext.item?.render_item_prices && !erpnext.item.k3ls_prices_wrapped) {
        const original = erpnext.item.render_item_prices;
        erpnext.item.render_item_prices = function (form) {
            if (frappe.boot.k3ls_shop_ui && frappe.user.has_role("System Manager") && !form.k3ls_more_fields) {
                return frappe.k3ls_product_prices(form);
            }
            return original.call(this, form);
        };
        erpnext.item.k3ls_prices_wrapped = true;
    }
    const key = `${frm.doc.name}:${frm.doc.modified}`;
    if (frm.k3ls_prices_key === key) return;
    frm.k3ls_prices_key = key;
    const item = frm.doc.name;
    frappe.k3ls_loading(content, "Loading prices");
    panel.attr("aria-busy", "true");
    try {
        const {message: data} = await frappe.call({method: "moniepoint_pos.pricing.prices", type: "GET", args: {item}});
        if (item !== frm.doc.name || key !== frm.k3ls_prices_key) return;
        render(data);
    } catch (error) {
        frm.k3ls_prices_key = null;
        content.empty().append($("<p></p>").text(__("Prices could not load. Try again.")));
        $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
            .on("click", () => frappe.k3ls_product_prices(frm)).appendTo(content);
    } finally {panel.attr("aria-busy", "false");}

    function render(data) {
        content.empty();
        const cards = $("<div class='k3ls-price-cards'></div>").appendTo(content);
        for (const [label, value] of [["Cost price", data.cost_price], ["Selling price", data.selling_price], ["Expected profit", data.expected_profit]]) {
            const card = $("<div class='k3ls-price-card'></div>").appendTo(cards);
            $("<span></span>").text(__(label)).appendTo(card);
            $("<strong></strong>").text(value === null ? __("Not recorded") : format_currency(value, data.currency)).appendTo(card);
        }
        for (const [label, value] of [["Delivery cost", data.delivery_cost], ["Repair cost", data.repair_cost], ["Total cost", data.total_cost]]) {
            if (value != null) $("<p class='text-muted'></p>").text(`${__(label)}: ${format_currency(value, data.currency)}`).appendTo(content);
        }
        $("<p class='text-muted'></p>").text(__("Per piece. Profit subtracts purchase, delivery and repair costs, before other shop expenses.")).appendTo(content);
        if (data.can_edit) $("<button type='button' class='btn btn-primary'></button>").text(__("Edit prices"))
            .on("click", () => edit(data)).appendTo(content);
        if (data.devices?.length) {
            $("<h3></h3>").text(__("Individual devices")).appendTo(content);
            for (const device of data.devices) {
                const row = $("<section class='k3ls-price-card'></section>").appendTo(content);
                $("<strong></strong>").text(device.serial).appendTo(row);
                $("<p></p>").text(`${__("Total cost")} · ${device.total_cost == null ? __("Not recorded") : format_currency(device.total_cost, data.currency)}`).appendTo(row);
                $("<p></p>").text(`${__("Expected profit")} · ${device.profit == null ? __("Not recorded") : format_currency(device.profit, data.currency)}`).appendTo(row);
                $("<button type='button' class='btn btn-default'></button>").text(__("Open device")).on("click", () => frappe.k3ls_workflow_route("units", device.name)).appendTo(row);
            }
        }
    }

    function edit(data) {
        if (frm.is_dirty()) {frappe.msgprint(__("Save the product details before editing prices.")); return;}
        const dialog = new frappe.ui.Dialog({title: __("Prices"), fields: [
            {fieldname: "cost_price", fieldtype: "Currency", label: __("Cost price"), options: "NGN", reqd: 1, default: data.cost_price},
            {fieldname: "delivery_cost", fieldtype: "Currency", label: __("Delivery cost"), options: "NGN", default: data.delivery_cost},
            {fieldname: "repair_cost", fieldtype: "Currency", label: __("Repair cost"), options: "NGN", default: data.repair_cost},
            {fieldname: "selling_price_value", fieldtype: "Currency", label: __("Selling price"), options: "NGN", reqd: 1, default: data.selling_price}],
            primary_action_label: __("Save prices"), primary_action: async values => {
                const button = dialog.get_primary_btn();
                button.prop("disabled", true);
                try {
                    await frappe.call({method: "moniepoint_pos.pricing.save_prices", type: "POST", args: {
                        ...values, delivery_cost: values.delivery_cost || 0, repair_cost: values.repair_cost || 0, item: data.item, modified: data.modified,
                        price_name: data.price_name, price_modified: data.price_modified}});
                    dialog.hide();
                    frm.k3ls_prices_key = null;
                    await frm.reload_doc();
                } catch (error) {button.prop("disabled", false);}
            }});
        dialog.show();
    }
};
