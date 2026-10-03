frappe.ui.form.on("Moniepoint Settings", {
    refresh(frm) {
        if (!frappe.boot.k3ls_shop_ui) return;
        if (!frm.k3ls_moniepoint_admin) setup_moniepoint_admin(frm);
        frm.k3ls_moniepoint_admin.reload();
    },
});

function setup_moniepoint_admin(frm) {
    const wrapper = frm.layout.wrapper;
    const escape = frappe.utils.escape_html;
    const tabs = $("<nav class='k3ls-moniepoint-tabs' aria-label='Moniepoint settings'></nav>");
    const warning = wrapper.children(".k3ls-admin-warning");
    if (warning.length) tabs.insertAfter(warning); else tabs.prependTo(wrapper);
    const terminals = $("<section class='k3ls-moniepoint-panel' aria-label='Terminals' hidden></section>").appendTo(wrapper);
    const payments = $("<section class='k3ls-moniepoint-panel' aria-label='Payment requests' hidden></section>").appendTo(wrapper);
    const state = {tab: "connection", request_state: "", provider_state: "", start: 0, token: 0, data: null};
    const controls = {};
    const connection_sections = () => wrapper.children(".form-page, .form-section");
    const select = tab => {
        state.tab = tab;
        for (const [name, button] of Object.entries(controls)) button.attr("aria-pressed", String(name === tab));
        connection_sections().toggle(tab === "connection");
        terminals.prop("hidden", tab !== "terminals");
        payments.prop("hidden", tab !== "payments");
        frm.page.btn_primary.toggleClass("hide", tab !== "connection");
    };
    for (const [name, label] of [["connection", "Connection"], ["terminals", "Terminals"], ["payments", "Payment requests"]]) {
        controls[name] = $("<button type='button'></button>").text(__(label)).appendTo(tabs).on("click", () => select(name));
    }
    const row = (parent, name, value) => {
        $("<dt></dt>").text(__(name)).appendTo(parent);
        $("<dd></dd>").text(value || __("Not reported")).appendTo(parent);
    };
    const amount = (value, units) => value == null ? __("Not reported")
        : units === "Kobo" ? format_currency(value / 100, "NGN")
        : units === "Naira" ? format_currency(value, "NGN") : `${value} ${units || ""}`.trim();
    const reload = async () => {
        const token = ++state.token;
        terminals.attr("aria-busy", "true"); payments.attr("aria-busy", "true");
        frappe.k3ls_loading(terminals, "Loading terminals");
        frappe.k3ls_loading(payments, "Loading payment requests");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.settings.overview", type: "GET",
                args: {request_state: state.request_state, provider_state: state.provider_state, start: state.start}});
            if (token !== state.token) return;
            state.data = data;
            render_terminals(); render_payments(); select(state.tab);
        } catch (error) {
            if (token !== state.token) return;
            for (const panel of [terminals, payments]) {
                panel.empty().append($("<p role='alert'></p>").text(__("Moniepoint records could not load.")));
                $("<button type='button' class='btn btn-default'></button>").text(__("Retry")).on("click", reload).appendTo(panel);
            }
        } finally {
            if (token === state.token) {terminals.attr("aria-busy", "false"); payments.attr("aria-busy", "false");}
        }
    };
    const render_terminals = () => {
        terminals.empty();
        const header = $("<div class='k3ls-moniepoint-toolbar'></div>").appendTo(terminals);
        $("<h2></h2>").text(__("Terminals")).appendTo(header);
        if (state.data.can_create) $("<button type='button' class='btn btn-primary'></button>").text(__("Add terminal"))
            .on("click", () => edit_terminal()).appendTo(header);
        if (!state.data.terminals.length) $("<p class='text-muted'></p>").text(__("No terminals connected yet.")).appendTo(terminals);
        const list = $("<div class='k3ls-moniepoint-records'></div>").appendTo(terminals);
        for (const terminal of state.data.terminals) {
            const button = $("<button type='button' class='k3ls-moniepoint-record'></button>").appendTo(list).on("click", () => edit_terminal(terminal));
            const details = $("<span></span>").appendTo(button);
            $("<strong></strong>").text(terminal.terminal_serial).appendTo(details);
            $("<small></small>").text(`${terminal.pos_profile} · ${terminal.mode_of_payment}`).appendTo(details);
            $("<span class='k3ls-moniepoint-status'></span>").text(__(terminal.enabled ? "Active" : "Off")).appendTo(button);
        }
    };
    const edit_terminal = terminal => {
        const writable = terminal ? state.data.can_write : state.data.can_create;
        const locked = Boolean(terminal?.has_requests);
        const payment_types = {Card: "CARD_PURCHASE", Transfer: "POS_TRANSFER", "Card or transfer": "ANY"};
        const dialog = new frappe.ui.Dialog({title: __(terminal ? "Terminal" : "Add terminal"), fields: [
            {fieldname: "terminal_serial", fieldtype: "Data", label: __("Serial number"), reqd: 1, read_only: !writable || locked},
            {fieldname: "pos_profile", fieldtype: "Link", label: __("Till"), options: "POS Profile", reqd: 1, read_only: !writable || locked,
                get_query: () => ({filters: {company: "K3LS LIMITED", disabled: 0}})},
            {fieldname: "mode_of_payment", fieldtype: "Link", label: __("Payment method"), options: "Mode of Payment", reqd: 1, read_only: !writable || locked,
                get_query: () => ({filters: {enabled: 1, name: "Moniepoint MFB"}})},
            {fieldname: "payment_type", fieldtype: "Select", label: __("Payment type"), options: Object.keys(payment_types).join("\n"), reqd: 1, read_only: !writable || locked},
            {fieldname: "enabled", fieldtype: "Check", label: __("Use terminal"), read_only: !writable},
            {fieldname: "notice", fieldtype: "HTML", options: locked ? `<p>${escape(__("This terminal has payment requests. Its details are locked to preserve their records."))}</p>` : ""},
            {fieldname: "error", fieldtype: "HTML"},
        ], primary_action_label: writable ? __("Save terminal") : undefined,
        primary_action: writable ? async values => {
            if (dialog.k3ls_saving) return;
            dialog.k3ls_saving = true; dialog.disable_primary_action();
            dialog.fields_dict.error.$wrapper.empty();
            try {
                await frappe.call({method: "moniepoint_pos.settings.save_terminal", type: "POST", args: {
                    name: terminal?.name, modified: terminal?.modified,
                    values: {terminal_serial: values.terminal_serial, company: "K3LS LIMITED", pos_profile: values.pos_profile,
                        mode_of_payment: values.mode_of_payment, payment_method: payment_types[values.payment_type], enabled: values.enabled},
                }});
                dialog.hide(); reload();
            } catch (error) {
                $("<p role='alert'></p>").text(__("Terminal wasn't saved. Check the details and retry.")).appendTo(dialog.fields_dict.error.$wrapper);
            } finally {dialog.k3ls_saving = false; dialog.enable_primary_action();}
        } : undefined});
        dialog.set_values({terminal_serial: terminal?.terminal_serial || "", pos_profile: terminal?.pos_profile || frappe.boot.k3ls_till_profile || "",
            mode_of_payment: terminal?.mode_of_payment || "Moniepoint MFB", enabled: terminal?.enabled || 0,
            payment_type: Object.keys(payment_types).find(label => payment_types[label] === terminal?.payment_method) || "Card or transfer"});
        dialog.show();
    };
    const render_payments = () => {
        payments.empty();
        const header = $("<div class='k3ls-moniepoint-toolbar'></div>").appendTo(payments);
        $("<h2></h2>").text(__("Payment requests")).appendTo(header);
        $("<button type='button' class='btn btn-default'></button>").text(__("Refresh")).on("click", reload).appendTo(header);
        $("<p class='text-muted'></p>").text(__("Accepted means Moniepoint received the request, not that the customer paid. These statuses do not mark a sale as paid."))
            .appendTo(payments);
        const filters = $("<div class='k3ls-moniepoint-filters'></div>").appendTo(payments);
        const requests = $("<select class='form-control' aria-label='Request status'></select>").appendTo(filters);
        for (const value of ["", "Created", "Accepted", "Unknown", "Rejected"]) $("<option></option>").val(value)
            .text(value ? `${__(value)} (${state.data.counts[value] || 0})` : __("All requests")).appendTo(requests);
        requests.val(state.request_state).on("change", () => {state.request_state = requests.val(); state.start = 0; reload();});
        const provider = $("<select class='form-control' aria-label='Moniepoint status'></select>").appendTo(filters);
        for (const value of ["", "PENDING", "PROCESSED", "COMPLETED", "CANCELLED", "SUCCESSFUL", "FAILED", "REJECTED", "EXPIRED"]) {
            $("<option></option>").val(value).text(value ? __(value[0] + value.slice(1).toLowerCase()) : __("All Moniepoint statuses")).appendTo(provider);
        }
        provider.val(state.provider_state).on("change", () => {state.provider_state = provider.val(); state.start = 0; reload();});
        const list = $("<div class='k3ls-moniepoint-records'></div>").appendTo(payments);
        if (!state.data.transactions.length) $("<p class='text-muted'></p>").text(__("No payment requests here.")).appendTo(list);
        for (const transaction of state.data.transactions) {
            const button = $("<button type='button' class='k3ls-moniepoint-record'></button>").appendTo(list);
            const detail = $("<span></span>").appendTo(button);
            $("<strong></strong>").text(transaction.invoice).appendTo(detail);
            $("<small></small>").text(`${transaction.state} · ${transaction.processing_status || __("Not reported")}`).appendTo(detail);
            $("<span></span>").text(amount(transaction.request_amount, transaction.amount_units)).appendTo(button);
            button.on("click", () => {
                const dialog = new frappe.ui.Dialog({title: __("Payment request"), fields: [{fieldname: "details", fieldtype: "HTML"}]});
                const summary = $("<dl class='k3ls-intake-ticket'></dl>").appendTo(dialog.fields_dict.details.$wrapper);
                const terminal = state.data.terminals.find(device => device.name === transaction.terminal);
                row(summary, "Sale", transaction.invoice); row(summary, "Terminal", terminal?.terminal_serial || transaction.terminal);
                row(summary, "Reference", transaction.merchant_reference); row(summary, "Request status", transaction.state);
                row(summary, "Moniepoint status", transaction.processing_status);
                row(summary, "Requested", amount(transaction.request_amount, transaction.amount_units));
                row(summary, "Reported amount", amount(transaction.actual_amount, transaction.amount_units));
                row(summary, "Last checked", transaction.last_checked ? frappe.datetime.str_to_user(transaction.last_checked) : "");
                dialog.show();
            });
        }
        const pager = $("<div class='k3ls-moniepoint-toolbar'></div>").appendTo(payments);
        if (state.start) $("<button type='button' class='btn btn-default'></button>").text(__("Previous"))
            .on("click", () => {state.start = Math.max(0, state.start - 50); reload();}).appendTo(pager);
        if (state.data.has_more) $("<button type='button' class='btn btn-default'></button>").text(__("Next"))
            .on("click", () => {state.start += 50; reload();}).appendTo(pager);
    };
    frm.k3ls_moniepoint_admin = {reload};
    select("connection");
}
