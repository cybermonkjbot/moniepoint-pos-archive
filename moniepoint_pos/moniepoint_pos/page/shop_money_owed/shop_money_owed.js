frappe.pages["shop-money-owed"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Money owed"), single_column: true});
    const content = $("<div class='k3ls-money-owed'></div>").appendTo(page.main);
    const escape = frappe.utils.escape_html;
    let request = 0;
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());
    page.add_menu_item(__("Detailed report"), () => frappe.set_route("query-report", "Accounts Receivable", {company: "K3LS LIMITED"}));
    wrapper.refresh = async () => {
        const token = ++request;
        content.attr("aria-busy", "true");
        frappe.k3ls_loading(content, "Loading balances");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.receivables.overview", type: "GET"});
            if (token !== request) return;
            content.empty();
            const totals = {};
            for (const customer of data.customers) totals[customer.currency] = (totals[customer.currency] || 0) + customer.owed;
            const head = $("<div class='k3ls-owed-heading'></div>").appendTo(content);
            $("<h2></h2>").text(__("Unpaid customer balances")).appendTo(head);
            for (const [currency, total] of Object.entries(totals)) $("<strong class='k3ls-owed-total'></strong>")
                .text(format_currency(total, currency)).appendTo(head);
            $("<p class='text-muted'></p>").text(__("As of {0}", [frappe.datetime.str_to_user(data.as_of)])).appendTo(head);
            if (!data.customers.length) {
                const empty = $("<div class='k3ls-shop-empty'></div>").appendTo(content);
                $("<span aria-hidden='true'></span>").html(frappe.utils.icon("wallet", "lg")).appendTo(empty);
                $("<h2></h2>").text(__("No money owed")).appendTo(empty);
                $("<p class='text-muted'></p>").text(__("No confirmed customer invoices have an unpaid balance.")).appendTo(empty);
                return;
            }
            const list = $("<div class='k3ls-owed-list'></div>").appendTo(content);
            const search_input = $("<input type='search' class='form-control' placeholder='Search customers' aria-label='Search customers'>")
                .on("input", function () {
                    const term = this.value.toLowerCase().trim();
                    list.find(".k3ls-owed-row").each(function () {$(this).toggle($(this).text().toLowerCase().includes(term));});
                });
            frappe.k3ls_search_field(search_input).insertBefore(list);
            for (const customer of data.customers) {
                const row = $("<button type='button' class='k3ls-owed-row'></button>").appendTo(list)
                    .on("click", () => show_customer(customer.customer, customer.customer_name));
                row.html(`<span class="k3ls-account-icon" aria-hidden="true">${frappe.utils.icon("user", "md")}</span>
                    <span class="k3ls-owed-name"><strong>${escape(customer.customer_name || customer.customer)}</strong><span>${escape(__("{0} unpaid invoices", [customer.invoices]))}</span></span>
                    <span class="k3ls-owed-due">${escape(customer.overdue ? __("Overdue") : customer.first_due ? __("Pay by {0}", [frappe.datetime.str_to_user(customer.first_due)]) : __("No due date"))}</span>
                    <strong class="k3ls-owed-amount">${escape(format_currency(customer.owed, customer.currency))}</strong>
                    <span aria-hidden="true">${frappe.utils.icon("chevron-right", "sm")}</span>`);
            }
        } catch (error) {
            if (token !== request) return;
            content.empty().append($("<p></p>").text(__("Unpaid balances could not load.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                .on("click", () => wrapper.refresh()).appendTo(content);
        } finally {if (token === request) content.attr("aria-busy", "false");}
    };
    wrapper.show_customer = show_customer;

    async function show_customer(customer, title) {
        const dialog = new frappe.ui.Dialog({title: title || customer, size: "large", fields: [{fieldname: "invoices", fieldtype: "HTML"}]});
        const body = dialog.fields_dict.invoices.$wrapper;
        body.text(__("Loading unpaid invoices…")); dialog.show();
        try {
            const {message: rows} = await frappe.call({method: "moniepoint_pos.receivables.invoices", type: "GET", args: {customer}});
            body.empty();
            if (!rows.length) {body.text(__("No unpaid invoices.")); return;}
            const phones = [...new Set(rows.map(row => row.contact_mobile).filter(Boolean))];
            if (phones.length) $("<p></p>").text(phones.join(" · ")).appendTo(body);
            for (const row of rows) {
                const card = $("<div class='k3ls-owed-invoice'></div>").appendTo(body);
                $("<strong></strong>").text(`${__(row.kind)} · ${row.name}`).appendTo(card);
                $("<span></span>").text(__("Left to pay {0}", [format_currency(row.outstanding_amount, row.currency)])).appendTo(card);
                $("<small class='text-muted'></small>").text(row.due_date ? __("Pay by {0}", [frappe.datetime.str_to_user(row.due_date)]) : __("No due date")).appendTo(card);
                const actions = $("<div></div>").appendTo(card);
                $("<button type='button' class='btn btn-default'></button>").text(__("Open invoice"))
                    .on("click", () => {dialog.hide(); frappe.set_route("Form", row.doctype, row.name);}).appendTo(actions);
                $("<button type='button' class='btn btn-primary'></button>").text(__("Take payment"))
                    .on("click", () => {dialog.hide(); take_payment(row);}).appendTo(actions);
            }
        } catch (error) {body.text(__("Invoices could not load. Close and try again."));}
    }

    async function take_payment(row) {
        const {message: options} = await frappe.call({method: "moniepoint_pos.receivables.payment_options", type: "GET",
            args: {doctype: row.doctype, name: row.name}});
        if (!options.can_collect) {
            frappe.msgprint(__("The till has closed. Reopen Money owed to find the combined invoice."));
            wrapper.refresh();
            return;
        }
        const dialog = new frappe.ui.Dialog({title: __("Take payment"), fields: [
            {fieldname: "balance", fieldtype: "HTML", options: `<p>${escape(__("Left to pay {0}", [format_currency(options.amount, options.currency)]))}</p>`},
            {fieldname: "mode", label: __("Payment method"), fieldtype: "Select", options: options.methods.join("\n"), reqd: 1},
            {fieldname: "amount", label: __("Amount received"), fieldtype: "Currency", options: options.currency, default: options.amount, reqd: 1},
            {fieldname: "note", fieldtype: "HTML", options: `<p class="text-muted">${escape(row.doctype === "POS Invoice"
                ? __("Record money already received. This does not charge a terminal.") : __("Review and confirm the payment on the next screen."))}</p>`}
        ], primary_action_label: __(row.doctype === "POS Invoice" ? "Record payment" : "Review payment"),
            primary_action: async ({amount, mode}) => {
                if (flt(amount) <= 0 || flt(amount) > flt(options.amount)) {
                    frappe.msgprint(__("Enter an amount above 0, no more than the unpaid balance.")); return;
                }
                dialog.disable_primary_action();
                try {
                    const {message: result} = await frappe.call({method: "moniepoint_pos.receivables.prepare_payment", type: "POST",
                        args: {doctype: row.doctype, name: row.name, amount, mode, modified: options.modified,
                            expected_outstanding: options.amount}});
                    dialog.hide();
                    if (result.payment) {
                        const docs = frappe.model.sync(result.payment);
                        frappe.set_route("Form", "Payment Entry", docs[0].name);
                    } else {wrapper.refresh(); frappe.show_alert(__("Payment recorded"));}
                } finally {dialog.enable_primary_action();}
            }});
        dialog.show();
    }
};
frappe.pages["shop-money-owed"].on_page_show = wrapper => {
    wrapper.refresh?.();
    const customer = frappe.get_route()[1];
    if (customer) wrapper.show_customer?.(customer);
};
