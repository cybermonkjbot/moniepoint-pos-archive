frappe.pages["shop-accounts"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Accounts"), single_column: true});
    const content = $("<div class='k3ls-accounts'></div>").appendTo(page.main);
    const escape = frappe.utils.escape_html;
    page.add_menu_item(__("Accounting details"), () => frappe.set_route("Tree", "Account"));
    let loading = false;
    wrapper.refresh = async () => {
        if (loading) return;
        loading = true;
        content.attr("aria-busy", "true");
        content.empty().append($("<p class='text-muted'></p>").text(__("Loading accounts…")));
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.accounts.overview", type: "GET"});
            content.empty();
            $("<h2></h2>").text(__("Cash and bank accounts")).appendTo(content);
            $("<p class='text-muted k3ls-accounts-date'></p>")
                .text(__("Recorded balances as of {0}", [frappe.datetime.str_to_user(data.as_of)]))
                .appendTo(content);
            if (!data.accounts.length) {
                $("<p></p>").text(__("No cash or bank accounts are set up.")).appendTo(content);
                return;
            }
            const rows = $("<div class='k3ls-account-list'></div>").appendTo(content);
            for (const account of data.accounts) {
                const balance = !data.can_read_balances ? __("Balance unavailable")
                    : !account.has_transactions ? __("No transactions yet")
                    : format_currency(account.balance, account.account_currency);
                const link = $("<button type='button' class='k3ls-account-row'></button>")
                    .on("click", () => show_transactions(account));
                link.html(`<span class="k3ls-account-icon">${frappe.utils.icon(account.account_type === "Cash" ? "wallet" : "landmark", "md")}</span>
                    <span class="k3ls-account-name"><strong>${escape(account.account_name)}</strong><span class="text-muted">${escape(account.account_type === "Cash" ? __("Cash") : __("Bank"))}</span></span>
                    <span class="k3ls-account-balance">${escape(balance)}</span>
                    <span aria-hidden="true">${frappe.utils.icon("chevron-right", "sm")}</span>`).appendTo(rows);
            }
            $("<p class='text-muted k3ls-accounts-updated'></p>")
                .text(__("Updated {0}", [frappe.datetime.str_to_user(data.updated_at.slice(0, 10)) + " " + data.updated_at.slice(11, 16)]))
                .appendTo(content);
        } catch (error) {
            content.empty().append($("<p></p>").text(__("Accounts could not load. Try again.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                .on("click", () => wrapper.refresh()).appendTo(content);
        } finally {
            content.attr("aria-busy", "false");
            loading = false;
        }
    };
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());

    async function show_transactions(account) {
        const dialog = new frappe.ui.Dialog({title: account.account_name, size: "large",
            fields: [{fieldtype: "HTML", fieldname: "transactions"}]});
        const body = dialog.fields_dict.transactions.$wrapper;
        body.text(__("Loading transactions…"));
        dialog.show();
        try {
            const {message: rows} = await frappe.call({method: "moniepoint_pos.accounts.transactions",
                type: "GET", args: {account: account.name}});
            body.empty();
            if (!rows.length) {
                body.text(__("No transactions yet."));
                return;
            }
            const table = $("<div class='k3ls-account-transactions'><table class='table'><thead><tr></tr></thead><tbody></tbody></table></div>").appendTo(body);
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
            $("<p class='text-muted'></p>").text(__("Latest 50 transactions")).appendTo(body);
        } catch (error) {
            body.text(__("Transactions could not load. Close this window and try again."));
        }
    }
};
