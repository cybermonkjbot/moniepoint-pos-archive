frappe.pages["shop-profit"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Profit"), single_column: true});
    const content = $("<div class='k3ls-profit'></div>").appendTo(page.main);
    let range = {}, request = 0;
    wrapper.refresh = async () => {
        const current = ++request;
        frappe.k3ls_loading(content, "Loading profit");
        content.attr("aria-busy", "true");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.pricing.profit", type: "GET", args: range});
            if (current !== request) return;
            content.empty();
            range = {from_date: data.from_date, to_date: data.to_date};
            $("<p class='text-muted'></p>").text(`${frappe.datetime.str_to_user(data.from_date)} to ${frappe.datetime.str_to_user(data.to_date)}`).appendTo(content);
            const cards = $("<div class='k3ls-price-cards'></div>").appendTo(content);
            for (const [label, value] of [["Income", data.income], ["Costs and expenses", data.expenses], ["Profit", data.profit]]) {
                const card = $("<div class='k3ls-price-card'></div>").appendTo(cards);
                $("<span></span>").text(__(label)).appendTo(card);
                $("<strong></strong>").text(value === null ? __("No records yet") : format_currency(value, data.currency)).appendTo(card);
            }
            $("<p class='text-muted'></p>").text(__("Based on posted sales, stock costs and expenses, not money collected.")).appendTo(content);
            if (data.unclosed_sales) $("<p role='status'></p>").text(__("Close the till to include its unposted sales.")).appendTo(content);
            $("<button type='button' class='btn btn-default'></button>").text(__("View breakdown"))
                .on("click", () => {frappe.route_options = {company: "K3LS LIMITED", filter_based_on: "Date Range",
                    period_start_date: data.from_date, period_end_date: data.to_date, periodicity: "Monthly"};
                    frappe.set_route("query-report", "Profit and Loss Statement");}).appendTo(content);
        } catch (error) {
            if (current !== request) return;
            content.empty().append($("<p></p>").text(__("Profit could not load. Try again.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry")).on("click", () => wrapper.refresh()).appendTo(content);
        } finally {if (current === request) content.attr("aria-busy", "false");}
    };
    page.set_primary_action(__("Dates"), () => {
        const dialog = new frappe.ui.Dialog({title: __("Dates"), fields: [
            {fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: range.from_date},
            {fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: range.to_date}],
            primary_action_label: __("Show profit"), primary_action: values => {range = values; dialog.hide(); wrapper.refresh();}});
        dialog.show();
    });
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());
};
