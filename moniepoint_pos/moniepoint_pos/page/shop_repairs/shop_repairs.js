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
    let intake = null;
    page.set_secondary_action(__("Refresh"), () => wrapper.refresh());
    page.add_menu_item(__("All repair records"), () => frappe.set_route("List", "K3LS Repair"));

    wrapper.refresh = async () => {
        if (intake) return;
        const token = ++request;
        results.attr("aria-busy", "true");
        try {
            const {message: data} = await frappe.call({method: "moniepoint_pos.repairs.overview", type: "GET",
                args: {status: selected, search, start}});
            if (token !== request) return;
            if (data.can_create) page.set_primary_action(__("New repair"), start_intake);
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
                    .text(__("New repair")).on("click", start_intake).appendTo(empty);
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

    function start_intake() {
        if (intake) return;
        ++request;
        toolbar.hide(); results.hide(); pager.hide();
        page.set_title(__("New repair"));
        page.clear_primary_action();
        page.set_secondary_action(__("All repairs"), leave_intake);
        content.addClass("k3ls-intake-active");
        const shell = $("<div class='k3ls-repair-intake'></div>").appendTo(content);
        const editor = $("<div class='k3ls-intake-editor'></div>").appendTo(shell);
        const side = $("<div class='k3ls-intake-side'></div>").appendTo(shell);
        const state = intake = {shell, controls: {}, dirty: false, busy: false, customer_request: 0, filled_contact: {}, step: "device"};
        const phone_tabs = $("<nav class='k3ls-intake-phone-tabs' aria-label='Repair details'></nav>").prependTo(shell);
        const phone_footer = $("<div class='k3ls-intake-phone-footer'></div>").appendTo(shell);
        const next = $("<button type='button' class='btn btn-primary'></button>").appendTo(phone_footer);
        const steps = ["device", "problem", "customer"];
        const show_step = (step, focus=false) => {
            state.step = step;
            shell.attr("data-phone-step", step);
            phone_tabs.find("button").each(function () {$(this).attr("aria-pressed", String(this.dataset.step === step));});
            next.text(__(step === "customer" ? "Save repair" : step === "device" ? "Continue" : "Add customer"));
            if (focus) state.controls[step === "device" ? "device" : step === "problem" ? "fault_reported" : "customer"].set_focus();
        };
        for (const step of steps) $("<button type='button'></button>").attr("data-step", step)
            .text(__(step[0].toUpperCase() + step.slice(1))).on("click", () => show_step(step)).appendTo(phone_tabs);
        const panel = (parent, title) => {
            const card = $("<section class='k3ls-intake-card'></section>").appendTo(parent);
            $("<h2></h2>").text(__(title)).appendTo(card);
            return card;
        };
        const make = (parent, name, label, type="Data", extra={}) => {
            const control = frappe.ui.form.make_control({parent, render_input: true,
                df: {fieldname: name, fieldtype: type, label: __(label), onchange: () => {
                    state.dirty = true; update_ticket();
                }, ...extra}});
            state.controls[name] = control;
            control.$wrapper.removeClass("has-error");
            if (control.$input) {
                const id = `k3ls-intake-${name}`;
                control.$input.attr({id, "aria-label": __(label)});
                control.$wrapper.find("label").attr("for", id);
                control.$input.on("input.k3ls-intake change.k3ls-intake", () => {
                    state.dirty = true; update_ticket();
                });
            }
            return control;
        };
        const device = panel(editor, "Device").addClass("k3ls-intake-device-card");
        const types = $("<div class='k3ls-intake-devices' role='group' aria-label='Device type'></div>").appendTo(device);
        const device_buttons = [];
        for (const [label, icon] of [["Laptop", "laptop"], ["Phone", "smartphone"], ["Tablet", "tablet"], ["Other", "package"]]) {
            const button = $("<button type='button' aria-pressed='false'></button>")
                .append($("<span aria-hidden='true'></span>").html(frappe.utils.icon(icon, "lg")))
                .append($("<span></span>").text(__(label))).appendTo(types);
            device_buttons.push({button, label});
            button.on("click", async () => {
                for (const item of device_buttons) item.button.attr("aria-pressed", String(item.button === button));
                const control = state.controls.device;
                const current = control.get_value() || "";
                if (!current || ["Laptop", "Phone", "Tablet"].includes(current)) await control.set_value(label === "Other" ? "" : label);
                control.$input.attr("placeholder", __(label === "Laptop" ? "Brand and model, e.g. HP EliteBook" : label === "Phone" ? "Brand and model, e.g. iPhone 13" : "Brand and model"));
                control.set_focus();
            });
        }
        const device_fields = $("<div class='k3ls-intake-fields'></div>").appendTo(device);
        make(device_fields, "device", "Device or model", "Data", {reqd: 1, placeholder: __("Brand and model")});
        make(device_fields, "serial_no", "Serial or IMEI");

        const problem = panel(editor, "Problem").addClass("k3ls-intake-problem-card");
        const faults = $("<div class='k3ls-intake-chips' role='group' aria-label='Common problems'></div>").appendTo(problem);
        for (const label of ["Screen", "Battery", "Won't turn on", "Charging", "Keyboard", "Software"]) {
            $("<button type='button' aria-pressed='false'></button>").text(__(label)).appendTo(faults).on("click", async function () {
                const control = state.controls.fault_reported;
                const parts = (control.get_value() || "").split("\n").filter(Boolean);
                const index = parts.indexOf(__(label));
                if (index === -1) parts.push(__(label)); else parts.splice(index, 1);
                await control.set_value(parts.join("\n"));
                update_ticket();
            });
        }
        make(problem, "fault_reported", "What's wrong?", "Small Text", {reqd: 1});
        make(problem, "arrival_condition", "Condition received", "Small Text", {reqd: 1, placeholder: __("Scratches, cracks or other damage")});
        const extras = $("<details class='k3ls-intake-extras'></details>").appendTo(problem);
        $("<summary></summary>").text(__("Accessories and photo")).appendTo(extras);
        make(extras, "accessories_received", "Accessories left with us", "Small Text");
        make(extras, "intake_evidence", "Device photo", "Attach", {options: {allow_web_link: false, allow_toggle_private: false, is_private: 1}});

        const customer = panel(side, "Customer").addClass("k3ls-intake-customer-card");
        make(customer, "customer", "Customer", "Link", {options: "Customer", reqd: 1,
            get_query: () => ({filters: {name: ["!=", "K3LS Walk-in Customer"], disabled: 0}}),
            onchange: async () => {
                if (!state.ready) return;
                state.dirty = true;
                const name = state.controls.customer.get_value();
                const token = ++state.customer_request;
                update_ticket();
                for (const field of ["customer_phone", "customer_address"]) {
                    const control = state.controls[field];
                    if (state.filled_contact[field] && control.get_value() === state.filled_contact[field]) await control.set_value("");
                }
                state.filled_contact = {};
                if (!name) return;
                const phone_before = state.controls.customer_phone.get_value();
                const address_before = state.controls.customer_address.get_value();
                try {
                    const {message: info} = await frappe.call({method: "moniepoint_pos.repairs.customer_details", type: "GET", args: {name}});
                    if (intake !== state || token !== state.customer_request) return;
                    if (!phone_before && !state.controls.customer_phone.get_value() && info.phone) {
                        await state.controls.customer_phone.set_value(info.phone);
                        state.filled_contact.customer_phone = info.phone;
                    }
                    if (!address_before && !state.controls.customer_address.get_value() && info.address) {
                        await state.controls.customer_address.set_value(info.address);
                        state.filled_contact.customer_address = info.address;
                    }
                    await state.controls.relationship.set_value(info.returning ? "Returning" : "New");
                    update_ticket();
                } catch (error) { /* Contact fields remain editable if lookup fails. */ }
            }});
        make(customer, "customer_phone", "Phone", "Data", {reqd: 1});
        make(customer, "customer_address", "Address", "Small Text", {reqd: 1});
        make(customer, "relationship", "Customer type", "Select", {options: "New\nReturning"});

        const ticket = panel(side, "Repair ticket").addClass("k3ls-intake-ticket-card");
        const summary = $("<dl class='k3ls-intake-ticket' aria-live='polite'></dl>").appendTo(ticket);
        const message = $("<p class='k3ls-intake-error' role='alert' hidden></p>").appendTo(ticket);
        const save = $("<button type='button' class='btn btn-primary k3ls-intake-save'></button>").text(__("Save repair")).appendTo(ticket);
        state.save = save;
        function update_ticket() {
            if (intake !== state || !state.ready) return;
            const value = name => {
                const control = state.controls[name];
                return String(control?.df.fieldtype === "Link" ? control.get_value() || "" : control?.$input?.val() ?? control?.get_value() ?? "").trim();
            };
            summary.empty();
            for (const [label, text] of [["Device", value("device") || __("Not added")], ["Problem", value("fault_reported") || __("Not added")],
                ["Condition", value("arrival_condition") || __("Not added")], ["Status", __("Received")]]) {
                $("<dt></dt>").text(__(label)).appendTo(summary);
                $("<dd></dd>").text(text).appendTo(summary);
            }
            const problems = value("fault_reported").split("\n");
            faults.find("button").each(function () { $(this).attr("aria-pressed", String(problems.includes($(this).text()))); });
        }
        save.on("click", async () => {
            if (state.busy) return;
            const values = {}, missing = [];
            for (const [name, control] of Object.entries(state.controls)) {
                const value = control.get_value();
                values[name] = typeof value === "string" ? value.trim() : value;
                const invalid = Boolean(control.df.reqd && !values[name]);
                control.$wrapper.toggleClass("has-error", invalid);
                control.$input?.attr("aria-invalid", String(invalid));
                if (invalid) missing.push(control);
            }
            if (values.customer === "K3LS Walk-in Customer") {
                if (window.matchMedia("(max-width: 767px)").matches) show_step("customer");
                message.text(__("Choose the customer's name for this repair.")).prop("hidden", false);
                phone_error.text(message.text()).prop("hidden", false);
                state.controls.customer.set_focus();
                return;
            }
            if (missing.length) {
                if (window.matchMedia("(max-width: 767px)").matches) {
                    const name = missing[0].df.fieldname;
                    show_step(["device", "serial_no"].includes(name) ? "device" : ["fault_reported", "arrival_condition"].includes(name) ? "problem" : "customer");
                }
                message.text(__("Add {0}.", [missing.map(control => control.df.label.toLowerCase()).join(", ")])).prop("hidden", false);
                phone_error.text(message.text()).prop("hidden", false);
                missing[0].set_focus();
                return;
            }
            state.busy = true;
            shell.attr("aria-busy", "true");
            save.prop("disabled", true).text(__("Saving…"));
            next.prop("disabled", true).text(__("Saving…"));
            message.prop("hidden", true);
            phone_error.prop("hidden", true);
            try {
                const {message: saved} = await frappe.call({method: "moniepoint_pos.repairs.save", type: "POST", args: {values, section: "intake"}});
                finish_intake();
                wrapper.refresh();
                open(saved.repair.name);
            } catch (error) {
                message.text(__("Repair wasn't saved. Check the details and retry.")).prop("hidden", false);
                phone_error.text(message.text()).prop("hidden", false);
            } finally {
                state.busy = false;
                shell.attr("aria-busy", "false");
                save.prop("disabled", false).text(__("Save repair"));
                next.prop("disabled", false); show_step(state.step);
            }
        });
        const phone_error = $("<p class='k3ls-intake-error' role='alert' hidden></p>").prependTo(phone_footer);
        next.on("click", () => {
            if (state.busy) return;
            if (state.step === "customer") {save.trigger("click"); return;}
            const required = state.step === "device" ? ["device"] : ["fault_reported", "arrival_condition"];
            const missing = required.map(name => state.controls[name]).find(control => !String(control.get_value() || "").trim());
            if (missing) {
                phone_error.text(__("Add {0}.", [missing.df.label.toLowerCase()])).prop("hidden", false);
                missing.$input?.attr("aria-invalid", "true"); missing.set_focus(); return;
            }
            phone_error.prop("hidden", true);
            show_step(steps[steps.indexOf(state.step) + 1]);
            content[0].scrollIntoView({block: "start"});
        });
        show_step("device");
        state.ready = true;
        state.controls.relationship.set_value("New").then(() => {state.dirty = false; update_ticket();});
        update_ticket();
    }

    function finish_intake() {
        intake.shell.remove(); intake = null;
        content.removeClass("k3ls-intake-active");
        toolbar.show(); results.show(); pager.show();
        page.set_title(__("Repairs"));
        page.set_secondary_action(__("Refresh"), () => wrapper.refresh());
    }

    function leave_intake() {
        if (!intake || intake.busy) return;
        const leave = () => {finish_intake(); wrapper.refresh();};
        if (!intake.dirty) {leave(); return;}
        const dialog = new frappe.ui.Dialog({title: __("Discard repair?"), fields: [{fieldname: "notice", fieldtype: "HTML", options: `<p>${escape(__("The repair hasn't been saved."))}</p>`}],
            primary_action_label: __("Discard"), primary_action: () => {dialog.hide(); leave();},
            secondary_action_label: __("Keep editing"), secondary_action: () => dialog.hide()});
        dialog.show();
    }

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
