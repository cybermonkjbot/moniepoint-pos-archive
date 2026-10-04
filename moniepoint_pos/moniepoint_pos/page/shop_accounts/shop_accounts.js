frappe.pages["shop-accounts"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Overview"), single_column: true});
    const overview = $("<div class='k3ls-overview'></div>").appendTo(page.main);
    const profit_section = $("<section class='k3ls-overview-section' aria-labelledby='k3ls-overview-profit'></section>").appendTo(overview);
    const profit_header = $("<div class='k3ls-overview-heading'></div>").appendTo(profit_section);
    $("<h2 id='k3ls-overview-profit'></h2>").text(__("Profit")).appendTo(profit_header);
    const dates = $("<button type='button' class='btn btn-default'></button>").text(__("Dates")).appendTo(profit_header);
    const profit = $("<div></div>").appendTo(profit_section);
    const accounts_section = $("<section class='k3ls-overview-section' aria-labelledby='k3ls-overview-accounts'></section>").appendTo(overview);
    $("<h2 id='k3ls-overview-accounts'></h2>").text(__("Accounts")).appendTo(accounts_section);
    const content = $("<div></div>").appendTo(accounts_section);
    const escape = frappe.utils.escape_html;
    let range = {}, profit_request = 0, accounts_request = 0;
    const refresh_accounts = async () => {
        const current = ++accounts_request;
        content.attr("aria-busy", "true");
        frappe.k3ls_loading(content, "Loading accounts");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.accounts.overview", type: "GET"});
            if (current !== accounts_request) return;
            content.empty();
            if (!data.accounts.length) {
                $("<p></p>").text(__("No cash or bank accounts are set up.")).appendTo(content);
                return;
            }
            const rows = $("<div class='k3ls-account-list'></div>").appendTo(content);
            for (const account of data.accounts) {
                const balance = !data.can_read_balances ? __("Balance unavailable")
                    : !account.has_transactions ? __("No transactions yet")
                    : format_currency(account.balance, account.account_currency);
                const link = $(data.can_read_balances ? "<button type='button' class='k3ls-account-row'></button>" : "<div class='k3ls-account-row k3ls-account-summary'></div>");
                if (data.can_read_balances) link.on("click", () => show_transactions(account));
                link.html(`<span class="k3ls-account-icon" aria-hidden="true">${account.icon ? `<img class="k3ls-bank-mark" alt="" src="/assets/moniepoint_pos/images/${escape(account.icon)}">` : frappe.utils.icon("wallet", "md")}</span>
                    <span class="k3ls-account-name"><strong>${escape(account.label)}</strong>${account.number ? `<span class="k3ls-bank-number">${escape(account.number)}</span><span class="k3ls-bank-holder">${escape(account.holder || "")}</span>` : ""}</span>
                    <span class="k3ls-account-balance">${escape(balance)}</span>
                    ${data.can_read_balances ? `<span aria-hidden="true">${frappe.utils.icon("chevron-right", "sm")}</span>` : ""}`).appendTo(rows);
            }
        } catch (error) {
            if (current !== accounts_request) return;
            content.empty().append($("<p role='alert'></p>").text(__("Accounts could not load.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                .on("click", refresh_accounts).appendTo(content);
        } finally {
            if (current === accounts_request) content.attr("aria-busy", "false");
        }
    };
    const refresh_profit = async () => {
        const current = ++profit_request;
        frappe.k3ls_loading(profit, "Loading profit");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.pricing.profit", type: "GET", args: range});
            if (current !== profit_request) return;
            range = {from_date: data.from_date, to_date: data.to_date};
            profit.empty();
            $("<p class='text-muted'></p>").text(`${frappe.datetime.str_to_user(data.from_date)} to ${frappe.datetime.str_to_user(data.to_date)}`).appendTo(profit);
            const cards = $("<div class='k3ls-price-cards'></div>").appendTo(profit);
            const products = data.product_sales;
            for (const [label, value] of [["Product sales", products.income], ["Product costs", products.costs], ["Product profit", products.profit]]) {
                const card = $("<div class='k3ls-price-card'></div>").appendTo(cards);
                $("<span></span>").text(__(label)).appendTo(card);
                $("<strong></strong>").text(value === null ? __(products.has_sales ? "Cost not recorded" : "No sales yet") : format_currency(value, data.currency)).appendTo(card);
            }
            $("<p class='text-muted'></p>").text(__("Product costs include purchase, delivery and repairs. Other shop expenses are separate.")).appendTo(profit);
            if (products.missing_cost_lines) $("<p role='status'></p>").text(__("{0} sale lines have no saved cost. Their profit is unavailable.", [products.missing_cost_lines])).appendTo(profit);
            if (products.repair_cost) $("<p></p>").text(`${__("Repair costs included")}: ${format_currency(products.repair_cost, data.currency)}`).appendTo(profit);
            if (data.repairs?.count) $("<p></p>").text(`${__("Customer repair margin")} · ${format_currency(data.repairs.margin, data.currency)}`).appendTo(profit);
            $("<p></p>").text(`${__("Accounting profit")}: ${data.profit == null ? __("No records yet") : format_currency(data.profit, data.currency)}`).appendTo(profit);
            if (data.unclosed_sales) $("<p role='status'></p>").text(__("Close the till to include these sales in accounting profit.")).appendTo(profit);
            $("<button type='button' class='btn btn-default'></button>").text(__("Accounting breakdown"))
                .on("click", () => {frappe.route_options = {company: "K3LS LIMITED", filter_based_on: "Date Range",
                    period_start_date: data.from_date, period_end_date: data.to_date, periodicity: "Monthly"};
                    frappe.set_route("query-report", "Profit and Loss Statement");}).appendTo(profit);
        } catch (error) {
            if (current !== profit_request) return;
            profit.empty().append($("<p role='alert'></p>").text(__("Profit could not load.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry")).on("click", refresh_profit).appendTo(profit);
        } finally {if (current === profit_request) profit.attr("aria-busy", "false");}
    };
    dates.on("click", () => {
        const dialog = new frappe.ui.Dialog({title: __("Dates"), fields: [
            {fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: range.from_date},
            {fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: range.to_date}],
            primary_action_label: __("Show profit"), primary_action: values => {range = values; dialog.hide(); refresh_profit();}});
        dialog.show();
    });
    wrapper.refresh = () => Promise.all([refresh_profit(), refresh_accounts()]);
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());

    async function show_transactions(account) {
        const dialog = new frappe.ui.Dialog({title: account.label, size: "large",
            fields: [{fieldtype: "HTML", fieldname: "transactions"}]});
        const body = dialog.fields_dict.transactions.$wrapper;
        if (account.number) $("<p></p>").text(`${account.holder} · ${account.number}`).appendTo(body);
        const records = $("<div></div>").appendTo(body);
        records.text(__("Loading transactions"));
        dialog.show();
        try {
            const {message: rows} = await frappe.call({method: "moniepoint_pos.accounts.transactions",
                type: "GET", args: {account: account.name}});
            records.empty();
            if (!rows.length) {
                records.text(__("No transactions yet."));
                return;
            }
            const table = $("<div class='k3ls-account-transactions'><table class='table'><thead><tr></tr></thead><tbody></tbody></table></div>").appendTo(records);
            for (const label of ["Date", "Details", "Money in", "Money out"]) {
                $("<th scope='col'></th>").text(__(label)).appendTo(table.find("thead tr"));
            }
            for (const row of rows) {
                const tr = $("<tr></tr>").appendTo(table.find("tbody"));
                $("<td></td>").text(frappe.datetime.str_to_user(row.posting_date)).appendTo(tr);
                $("<td></td>").text(row.remarks || row.voucher_no).appendTo(tr);
                $("<td></td>").text(row.debit_in_account_currency ? format_currency(row.debit_in_account_currency, account.account_currency) : "").appendTo(tr);
                $("<td></td>").text(row.credit_in_account_currency ? format_currency(row.credit_in_account_currency, account.account_currency) : "").appendTo(tr);
            }
            $("<p class='text-muted'></p>").text(__("Latest 50 transactions")).appendTo(records);
        } catch (error) {
            records.text(__("Transactions could not load. Close this window and try again."));
        }
    }
};
