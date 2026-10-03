frappe.pages["shop-accounts"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Accounts"), single_column: true});
    const content = $("<div class='k3ls-accounts'></div>").appendTo(page.main);
    const escape = frappe.utils.escape_html;
    let loading = false;
    wrapper.refresh = async () => {
        if (loading) return;
        loading = true;
        content.attr("aria-busy", "true");
        frappe.k3ls_loading(content, "Loading accounts");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.accounts.overview", type: "GET"});
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
                const link = $("<button type='button' class='k3ls-account-row'></button>")
                    .on("click", () => show_transactions(account));
                link.html(`<span class="k3ls-account-icon" aria-hidden="true">${account.label === "Moniepoint" ? '<img class="k3ls-payment-mark" alt="" src="/assets/moniepoint_pos/images/moniepoint-mark.svg">' : frappe.utils.icon("wallet", "md")}</span>
                    <span class="k3ls-account-name"><strong>${escape(account.label)}</strong></span>
                    <span class="k3ls-account-balance">${escape(balance)}</span>
                    <span aria-hidden="true">${frappe.utils.icon("chevron-right", "sm")}</span>`).appendTo(rows);
            }
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
        const dialog = new frappe.ui.Dialog({title: account.label, size: "large",
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
