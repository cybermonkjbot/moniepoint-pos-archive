frappe.pages["shop-repairs"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Repairs"), single_column: true});
    const content = $("<div class='k3ls-repairs'></div>").appendTo(page.main);
    const escape = frappe.utils.escape_html;
    const labels = {Active: "Active", All: "All", Received: "Received", Diagnosing: "Checking",
        "Awaiting approval": "Awaiting approval", "In repair": "In repair",
        "Ready for collection": "Ready", Collected: "Collected", Cancelled: "Cancelled"};
    let selected = "Active", search = "", start = 0, request = 0, timer;
    const toolbar = $("<div class='k3ls-repair-toolbar'></div>").appendTo(content);
    const filters = $("<div class='k3ls-repair-filters' role='group' aria-label='Repair status'></div>").appendTo(toolbar);
    $("<input type='search' class='form-control' placeholder='Find customer, device or repair' aria-label='Find repairs'>")
        .appendTo(toolbar).on("input", function () {
            clearTimeout(timer);
            timer = setTimeout(() => {search = this.value.trim(); start = 0; wrapper.refresh();}, 250);
        });
    const results = $("<div class='k3ls-repair-results' aria-live='polite'></div>").appendTo(content);
    const pager = $("<div class='k3ls-repair-pager'></div>").appendTo(content);
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());
    page.add_menu_item(__("All repair records"), () => frappe.set_route("List", "K3LS Repair"));

    wrapper.refresh = async () => {
        const token = ++request;
        results.attr("aria-busy", "true");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.repairs.overview", type: "GET",
                args: {status: selected, search, start}});
            if (token !== request) return;
            if (data.can_create) page.set_primary_action(__("New repair"), () => edit(null, "intake"));
            filters.empty();
            for (const status of ["Active", "Received", "Diagnosing", "Awaiting approval", "In repair", "Ready for collection", "All"]) {
                const count = status === "Active" ? Object.entries(data.counts).reduce((sum, [key, value]) => sum + (!["Collected", "Cancelled"].includes(key) ? value : 0), 0)
                    : status === "All" ? Object.values(data.counts).reduce((a, b) => a + b, 0) : data.counts[status] || 0;
                $("<button type='button'></button>").text(`${__(labels[status])} ${count}`)
                    .attr("aria-pressed", String(status === selected)).toggleClass("selected", status === selected)
                    .on("click", () => {selected = status; start = 0; wrapper.refresh();}).appendTo(filters);
            }
            results.empty();
            if (!data.repairs.length) {
                const empty = $("<div class='k3ls-shop-empty'></div>").appendTo(results);
                $("<span aria-hidden='true'></span>").html(frappe.utils.icon("wrench", "lg")).appendTo(empty);
                $("<h2></h2>").text(__(search ? "No matching repairs" : selected === "Active" ? "No active repairs" : "No repairs here")).appendTo(empty);
                if (data.can_create && !search) $("<button type='button' class='btn btn-primary'></button>")
                    .text(__("New repair")).on("click", () => edit(null, "intake")).appendTo(empty);
            }
            for (const repair of data.repairs) {
                const row = $("<button type='button' class='k3ls-repair-row'></button>").appendTo(results)
                    .on("click", () => open(repair.name));
                row.html(`<span class="k3ls-repair-icon" aria-hidden="true">${frappe.utils.icon("wrench", "md")}</span>
                    <span class="k3ls-repair-device"><strong>${escape(repair.device)}</strong><span>${escape(repair.customer)} · ${escape(repair.customer_phone)}</span><small>${escape(repair.name)}</small></span>
                    <span class="k3ls-repair-status">${escape(__(labels[repair.status]))}</span>
                    <span class="k3ls-repair-due">${repair.expected_ready_date ? escape(__("Ready by {0}", [frappe.datetime.str_to_user(repair.expected_ready_date)])) : ""}</span>
                    <span aria-hidden="true">${frappe.utils.icon("chevron-right", "sm")}</span>`);
                row.find(".k3ls-repair-status").attr("data-status", repair.status);
            }
            pager.empty();
            if (start) $("<button type='button' class='btn btn-default'></button>").text(__("Previous"))
                .on("click", () => {start = Math.max(0, start - 50); wrapper.refresh();}).appendTo(pager);
            if (data.has_more) $("<button type='button' class='btn btn-default'></button>").text(__("Next"))
                .on("click", () => {start += 50; wrapper.refresh();}).appendTo(pager);
        } catch (error) {
            if (token !== request) return;
            results.empty().append($("<p></p>").text(__("Repairs could not load.")));
            $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                .on("click", () => wrapper.refresh()).appendTo(results);
        } finally {if (token === request) results.attr("aria-busy", "false");}
    };

    async function open(name) {
        const {message: data} = await frappe.call({method: "moniepoint_pos.repairs.details", type: "GET", args: {name}});
        const doc = data.repair;
        const dialog = new frappe.ui.Dialog({title: doc.device, size: "large", fields: [{fieldname: "summary", fieldtype: "HTML"}]});
        dialog.$wrapper.addClass("k3ls-repair-dialog");
        const body = dialog.fields_dict.summary.$wrapper;
        $("<p class='k3ls-repair-detail-status'></p>").text(`${doc.name} · ${__(labels[doc.status])}`).appendTo(body);
        const steps = $("<ol class='k3ls-repair-steps' aria-label='Repair progress'></ol>").appendTo(body);
        const phases = ["Received", "Diagnosing", "Awaiting approval", "In repair", "Ready for collection", "Collected"];
        for (const [index, status] of phases.entries()) $("<li></li>").text(__(labels[status]))
            .toggleClass("current", status === doc.status).toggleClass("done", index < phases.indexOf(doc.status))
            .attr("aria-current", status === doc.status ? "step" : null).appendTo(steps);
        const summary = $("<dl class='k3ls-repair-summary'></dl>").appendTo(body);
        const add = (label, value) => {
            if (!value) return;
            $("<dt></dt>").text(__(label)).appendTo(summary);
            $("<dd></dd>").text(value).appendTo(summary);
        };
        add("Customer", doc.customer); add("Phone", doc.customer_phone); add("Serial or IMEI", doc.serial_no);
        add("Reported fault", doc.fault_reported); add("Condition received", doc.arrival_condition);
        add("Problem found", doc.diagnosis); add("Work done", doc.work_done); add("Condition now", doc.final_condition);
        add("Ready by", doc.expected_ready_date && frappe.datetime.str_to_user(doc.expected_ready_date));
        if (data.can_bill) {
            add("Price", flt(doc.customer_charge) ? format_currency(doc.customer_charge, doc.currency) : __("Not set"));
            add("Price approved", doc.quote_approved ? __("Yes") : __("No"));
            add("Payment", !data.invoice ? __("No invoice yet") : data.invoice.docstatus === 0 ? __("Invoice not confirmed")
                : data.invoice.docstatus === 2 ? __("Invoice cancelled") : flt(data.invoice.outstanding) > 0
                    ? __("Left to pay {0}", [format_currency(data.invoice.outstanding, data.invoice.currency)]) : __("Paid"));
        }
        const actions = $("<div class='k3ls-repair-actions'></div>").appendTo(body);
        const action = (label, fn, primary=false) => $("<button type='button' class='btn'></button>")
            .addClass(primary ? "btn-primary" : "btn-default").text(__(label)).on("click", () => {dialog.hide(); fn();}).appendTo(actions);
        if (data.can_write && !["Collected", "Cancelled"].includes(doc.status)) {
            action("Edit device", () => edit(data, "intake"));
            action("Update work", () => edit(data, "progress"));
            if (data.can_bill) action("Price and approval", () => edit(data, "price"));
            const next = {Received: ["Start checking", "check"], Diagnosing: ["Ask for approval", "approval"],
                "Awaiting approval": ["Start repair", "start"], "In repair": ["Mark ready", "ready"],
                "Ready for collection": ["Mark collected", "collect"]}[doc.status];
            if (next && (next[1] !== "collect" || data.can_bill)) action(next[0], () => advance(data, next[1], next[0]), true);
        }
        if (data.can_bill && doc.status !== "Cancelled") {
            if (!data.invoice) action("Create invoice", () => invoice(data));
            else action("Open invoice", () => frappe.set_route("Form", "Sales Invoice", data.invoice.name));
            if (data.invoice?.docstatus === 1 && flt(data.invoice.outstanding) > 0)
                action("Take payment", () => frappe.set_route("shop-money-owed", doc.customer));
        }
        action("Full record", () => frappe.set_route("Form", "K3LS Repair", doc.name));
        dialog.show();
    }

    function edit(data, section) {
        const doc = data?.repair || {};
        const field = (fieldname, label, fieldtype="Data", extra={}) => ({fieldname, label: __(label), fieldtype,
            default: doc[fieldname], ...extra});
        const fields = section === "intake" ? [
            field("customer", "Customer", "Link", {options: "Customer", reqd: 1,
                get_query: () => ({filters: {name: ["!=", "K3LS Walk-in Customer"], disabled: 0}})}),
            field("customer_phone", "Phone", "Data", {reqd: 1}),
            field("customer_address", "Address", "Small Text", {reqd: 1, rows: 2}),
            field("relationship", "Customer type", "Select", {options: "New\nReturning", default: doc.relationship || "New", reqd: 1}),
            {fieldtype: "Column Break"}, field("device", "Device or model", "Data", {reqd: 1}),
            field("serial_no", "Serial or IMEI"), field("accessories_received", "Accessories left with us", "Small Text", {rows: 2}),
            {fieldtype: "Section Break"}, field("fault_reported", "Reported fault", "Small Text", {reqd: 1}),
            field("arrival_condition", "Condition received", "Small Text", {reqd: 1}),
            field("intake_evidence", "Device photo", "Attach")
        ] : section === "progress" ? [
            field("assigned_to", "Repairer", "Link", {options: "User"}), field("expected_ready_date", "Ready by", "Date"),
            field("diagnosis", "Problem found", "Small Text"), field("work_done", "Work done", "Small Text"),
            field("final_condition", "Condition now", "Small Text"), field("notes", "Notes", "Small Text")
        ] : [field("customer_charge", "Price, NGN", "Currency", {options: "NGN"}),
            field("quote_approved", "Customer approved price", "Check"), field("approval_reference", "Approval reference"),
            field("payment_due_date", "Pay by", "Date"), {fieldtype: "Section Break", label: __("Shop costs")},
            field("parts_cost", "Parts, NGN", "Currency", {options: "NGN"}),
            field("labour_cost", "Labour, NGN", "Currency", {options: "NGN"}),
            field("other_cost", "Other costs, NGN", "Currency", {options: "NGN"})];
        const dialog = new frappe.ui.Dialog({title: !data ? __("New repair") : __(section === "intake" ? "Device and customer" : section === "progress" ? "Repair work" : "Price and approval"),
            size: "large", fields, primary_action_label: __(data ? "Save" : "Save repair"),
            primary_action: async values => {
                dialog.disable_primary_action();
                try {
                    const {message: saved} = await frappe.call({method: "moniepoint_pos.repairs.save", type: "POST",
                        args: {values, name: doc.name, modified: doc.modified, section}});
                    dialog.hide(); wrapper.refresh(); open(saved.repair.name);
                } finally {dialog.enable_primary_action();}
            }});
        dialog.$wrapper.addClass("k3ls-repair-dialog");
        if (dialog.fields_dict.intake_evidence) dialog.fields_dict.intake_evidence.df.options = {allow_web_link: false, allow_toggle_private: false, is_private: 1};
        dialog.show();
    }

    function advance(data, action, label) {
        const fields = action === "ready" ? [
            {fieldname: "work_done", label: __("Work done"), fieldtype: "Small Text", reqd: 1, default: data.repair.work_done},
            {fieldname: "final_condition", label: __("Condition now"), fieldtype: "Small Text", reqd: 1, default: data.repair.final_condition}
        ] : action === "approval" ? [{fieldname: "diagnosis", label: __("Problem found"), fieldtype: "Small Text", reqd: 1, default: data.repair.diagnosis}]
            : [{fieldname: "confirm", fieldtype: "HTML", options: `<p>${escape(action === "collect" && data.invoice?.docstatus === 1 && flt(data.invoice.outstanding) > 0
                ? __("{0} is still unpaid. Mark this device as collected?", [format_currency(data.invoice.outstanding, data.invoice.currency)])
                : __(action === "collect" ? "Mark this device as collected?" : action === "start" ? "Start work at the approved price?" : "Start checking this device?"))}</p>`}];
        const dialog = new frappe.ui.Dialog({title: __(label), fields, primary_action_label: __(label),
            primary_action: async values => {
                dialog.disable_primary_action();
                try {
                    await frappe.call({method: "moniepoint_pos.repairs.advance", type: "POST",
                        args: {name: data.repair.name, modified: data.repair.modified, action, values}});
                    dialog.hide(); wrapper.refresh(); open(data.repair.name);
                } finally {dialog.enable_primary_action();}
            }});
        dialog.show();
    }

    function invoice(data) {
        const dialog = new frappe.ui.Dialog({title: __("Create repair invoice"), fields: [{fieldname: "confirm", fieldtype: "HTML",
            options: `<p>${escape(__("Create an invoice for {0}?", [format_currency(data.repair.customer_charge, data.repair.currency)]))}</p>`}],
            primary_action_label: __("Create invoice"), primary_action: async () => {
                dialog.disable_primary_action();
                try {
                    const {message: saved} = await frappe.call({method: "moniepoint_pos.repairs.invoice", type: "POST",
                        args: {name: data.repair.name, modified: data.repair.modified}});
                    dialog.hide(); frappe.set_route("Form", "Sales Invoice", saved.invoice.name);
                } finally {dialog.enable_primary_action();}
            }});
        dialog.show();
    }
};
frappe.pages["shop-repairs"].on_page_show = wrapper => wrapper.refresh?.();
