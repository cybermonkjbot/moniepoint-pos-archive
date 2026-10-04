frappe.pages["shop-accounts"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Overview"), single_column: true});
    const overview = $("<div class='k3ls-overview'></div>").appendTo(page.main);
    const profit_section = $("<section class='k3ls-overview-section' aria-labelledby='k3ls-overview-profit'></section>").appendTo(overview);
    const profit_header = $("<div class='k3ls-overview-heading'></div>").appendTo(profit_section);
    $("<h2 id='k3ls-overview-profit'></h2>").text(__("Profit")).appendTo(profit_header);
    const dates = $("<button type='button' class='btn btn-default'></button>").text(__("Dates")).appendTo(profit_header);
    const profit = $("<div></div>").appendTo(profit_section);
    const charts_section = $("<section class='k3ls-overview-section'></section>").attr("aria-label", __("Product performance")).appendTo(overview);
    const charts = $("<div class='k3ls-overview-charts'></div>").appendTo(charts_section);
    const accounts_section = $("<section class='k3ls-overview-section' aria-labelledby='k3ls-overview-accounts'></section>").appendTo(overview);
    $("<h2 id='k3ls-overview-accounts'></h2>").text(__("Accounts")).appendTo(accounts_section);
    const content = $("<div></div>").appendTo(accounts_section);
    const escape = frappe.utils.escape_html;
    let range = {}, profit_request = 0, accounts_request = 0;
    let chart_instances = [];
    const clear_charts = () => {
        for (const chart of chart_instances) chart.destroy();
        chart_instances = [];
        charts.empty();
    };
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
        clear_charts();
        frappe.k3ls_loading(profit, "Loading profit");
        frappe.k3ls_loading(charts, "Loading charts");
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
            render_charts(data);
        } catch (error) {
            if (current !== profit_request) return;
            clear_charts();
            profit.empty().append($("<p role='alert'></p>").text(__("Profit could not load.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry")).on("click", refresh_profit).appendTo(profit);
        } finally {if (current === profit_request) {profit.attr("aria-busy", "false"); charts.attr("aria-busy", "false");}}
    };
    dates.on("click", () => {
        const dialog = new frappe.ui.Dialog({title: __("Dates"), fields: [
            {fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: range.from_date},
            {fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: range.to_date}],
            primary_action_label: __("Apply dates"), primary_action: values => {range = values; dialog.hide(); refresh_profit();}});
        dialog.show();
    });
    wrapper.refresh = () => Promise.all([refresh_profit(), refresh_accounts()]);
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());

    function render_charts(data) {
        clear_charts();
        const trend = data.charts.trend;
        const crosses_year = data.from_date.slice(0, 4) !== data.to_date.slice(0, 4);
        const labels = trend.map(point => frappe.datetime.str_to_obj(point.from_date).toLocaleDateString((frappe.boot.lang || "en").replace(/_/g, "-"),
            {day: "numeric", month: "short", ...(crosses_year ? {year: "2-digit"} : {})}));
        const exact_dates = trend.map(point => point.from_date === point.to_date
            ? frappe.datetime.str_to_user(point.from_date)
            : `${frappe.datetime.str_to_user(point.from_date)} to ${frappe.datetime.str_to_user(point.to_date)}`);
        const grouping = {day: "Daily product sales", week: "Weekly product sales", month: "Monthly product sales"}[data.charts.grouping];
        const card = (title, subtitle) => {
            const section = $("<section class='k3ls-overview-chart-card'></section>").attr("aria-label", __(title)).appendTo(charts);
            $("<h2></h2>").text(__(title)).appendTo(section);
            $("<p class='text-muted'></p>").text(subtitle).appendTo(section);
            return section;
        };
        const figures = (parent, title, rows, headings) => {
            const details = $("<details class='k3ls-chart-figures'></details>").appendTo(parent);
            $("<summary></summary>").text(__("View figures")).appendTo(details);
            const table = $("<div class='k3ls-account-transactions'><table class='table'><caption class='sr-only'></caption><thead><tr></tr></thead><tbody></tbody></table></div>").appendTo(details);
            table.find("caption").text(__(title));
            for (const heading of headings) $("<th scope='col'></th>").text(__(heading)).appendTo(table.find("thead tr"));
            for (const values of rows) {
                const row = $("<tr></tr>").appendTo(table.find("tbody"));
                for (const value of values) $("<td></td>").text(value).appendTo(row);
            }
        };
        const axis_chart = (parent, title, values, colour, type) => {
            const plot = $("<div class='k3ls-overview-plot' aria-hidden='true'></div>").appendTo(parent);
            chart_instances.push(new frappe.Chart(plot[0], {type, height: 240, animate: false, disableEntryAnimation: true,
                colors: [colour], showLegend: false, data: {labels, datasets: [{name: __(title), values}]},
                lineOptions: {hideDots: trend.length > 15, regionFill: 1},
                axisOptions: {xIsSeries: true, shortenYAxisNumbers: true},
                tooltipOptions: {formatTooltipX: label => escape(exact_dates[labels.indexOf(label)] || label),
                    formatTooltipY: value => format_currency(value, data.currency)}}));
            figures(parent, title, trend.map((point, index) => [exact_dates[index], format_currency(values[index], data.currency)]), ["Date", title]);
        };
        if (!data.charts.has_sales) {
            const empty = card("Sales and profit", "").addClass("k3ls-overview-best-sellers");
            empty.find("p").remove();
            $("<p class='k3ls-chart-empty' role='status'></p>").text(__("No product sales in this period.")).appendTo(empty);
            return;
        }
        const sales = card("Sales over time", `${__(grouping)} · ${data.currency}`);
        axis_chart(sales, "Sales", trend.map(point => point.sales), "#84b5ff", "line");
        const margin = card("Profit over time", `${__("After product costs and repairs")} · ${data.currency}`);
        if (data.charts.missing_cost_lines) {
            $("<p class='k3ls-chart-unavailable' role='status'></p>").text(__("Some sales have no saved cost, so profit is unavailable.")).appendTo(margin);
            figures(margin, "Profit", trend.map((point, index) => [exact_dates[index], point.profit == null ? __("Cost not recorded") : format_currency(point.profit, data.currency)]), ["Date", "Profit"]);
        } else {
            axis_chart(margin, "Profit", trend.map(point => point.profit), "#a9ccff", "bar");
        }
        const sellers = card("Best sellers", __("Pieces sold, after returns"));
        sellers.addClass("k3ls-overview-best-sellers");
        const best = data.charts.best_sellers;
        if (!best.length) $("<p class='k3ls-chart-unavailable' role='status'></p>").text(__("No products sold in this period.")).appendTo(sellers);
        else {
            const list = $("<ol class='k3ls-best-sellers'></ol>").appendTo(sellers);
            const maximum = Math.max(...best.map(product => product.pieces));
            for (const product of best) {
                const row = $("<li></li>").appendTo(list);
                const link = $("<a class='k3ls-best-seller'></a>").attr("href", `/desk/item/${encodeURIComponent(product.item)}?sidebar=K3LS%20Owner`).appendTo(row);
                $("<span class='k3ls-best-seller-name'></span>").text(product.label).appendTo(link);
                $("<strong></strong>").text(__("{0} pieces", [product.pieces])).appendTo(link);
                $("<span class='k3ls-best-seller-track' aria-hidden='true'><span></span></span>").find("span").css("width", `${product.pieces / maximum * 100}%`).end().appendTo(link);
            }
        }
    }

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
