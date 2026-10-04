frappe.pages["shop-operations"].on_page_load = wrapper => {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Shop"), single_column: true});
    const content = $("<div class='k3ls-operations'></div>").appendTo(page.main);
    const titles = {intake: "Receive stock", inspection: "Stock checks", movements: "Stock movements", counts: "Count stock",
        requests: "Requests", returns: "Returns", "trade-ins": "Trade-ins", debts: "Older balances", plans: "Payment plans",
        receipts: "Payments to check", deliveries: "Deliveries", "owner-stock": "Owner stock", "account-checks": "Account checks", audit: "Action history", payables: "Money we owe", receivables: "Money owed", unplanned: "Balances without a plan", review: "Owner review", inventory: "Stock", units: "Devices", dashboard: "Review", controls: "Access reviews"};
    const groups = {intake: ["intake", "inspection"], movements: ["inventory", "movements", "counts", "units", "owner-stock"],
        returns: ["returns", "trade-ins"], review: ["dashboard", "receipts", "requests", "account-checks", "deliveries", "controls", "audit"], payables: ["payables", "receivables", "debts", "plans", "unplanned"]};
    const e = frappe.utils.escape_html;
    let section = "intake", search = "", request = 0, offset = 0, metadata = {};
    const rpc = async (method, args = {}, get = false) => (await frappe.call({method: `moniepoint_pos.${method}`, args, type: get ? "GET" : "POST"})).message;
    const key = () => window.crypto.randomUUID();
    const button = (parent, title, action, primary = false) => $("<button type='button'></button>").addClass(primary ? "btn btn-primary" : "btn btn-default").text(__(title)).on("click", action).appendTo(parent);
    const money = value => format_currency(value, "NGN");
    const labels = {"POS Invoice": "Till sale", "Sales Invoice": "Sale or repair bill", "Purchase Invoice": "Restock bill", "K3LS Debt": "Older balance",
        "K3LS Owner Stock": "Owner payout", "K3LS Delivery": "Delivery", "K3LS Shop Request": "Expense", "K3LS Repair": "Repair", Item: "Product",
        "K3LS Owned": "K3LS", "Sister Owned": "Sister's stock", "Third-party Owner": "Another owner's stock", "Moniepoint MFB": "Moniepoint", Delete: "Stop product or contact"};
    const display = value => __(labels[value] || value);
    const icons = {intake: "package-plus", inspection: "clipboard-check", movements: "arrow-right-left", counts: "list-checks", requests: "clipboard",
        returns: "undo-2", "trade-ins": "repeat", debts: "wallet", plans: "calendar", receipts: "receipt", deliveries: "truck", "owner-stock": "package", units: "laptop", controls: "shield-check", audit: "history"};

    wrapper.refresh = async () => {
        const current = ++request;
        content.attr("aria-busy", "true");
        frappe.k3ls_loading(content, "Loading records");
        try {
            if (["payables", "receivables", "unplanned"].includes(section)) {await money_list(current); return;}
            if (section === "inventory") {await inventory_list(current); return;}
            if (section === "dashboard") {await dashboard(current); return;}
            const filter = frappe.k3ls_review_filter?.section === section ? frappe.k3ls_review_filter : null;
            const [meta, result] = await Promise.all([rpc("operations.metadata", {kind: section}, true), rpc("operations.records", {kind: section, search, start: offset, names: filter?.names}, true)]);
            if (current !== request) return;
            metadata[section] = meta;
            content.empty();
            controls(meta);
            const list = $("<div class='k3ls-operation-list'></div>").appendTo(content);
            if (!result.rows.length) $("<p class='k3ls-shop-empty' role='status'></p>").text(__("No records yet")).appendTo(list);
            for (const row of result.rows) {
                const card = $("<button type='button' class='k3ls-operation-row'></button>").appendTo(list).on("click", () => open(section, row.name));
                const title = row.title || row.details || row.serial || row.repair || row.item || row.supplier || row.customer || row.reference_name || row.custodian || row.record_name || row.name;
                card.html(`<span class='k3ls-account-icon' aria-hidden='true'>${frappe.utils.icon(icons[section] || "clipboard", "md")}</span><span class='k3ls-operation-title'><strong>${e(title)}</strong><small>${e(row.name)}</small></span><span class='k3ls-operation-status'>${e(__(row.status || row.action || ""))}</span><span aria-hidden='true'>${frappe.utils.icon("chevron-right", "sm")}</span>`);
            }
            const pager = $("<div class='k3ls-operation-actions'></div>").appendTo(content);
            if (offset) button(pager, "Previous", () => {offset = Math.max(0, offset - 50); wrapper.refresh();});
            if (result.has_more) button(pager, "More", () => {offset += 50; wrapper.refresh();});
        } catch (error) {
            if (current !== request) return;
            content.empty().append($("<p role='alert'></p>").text(error.message || __("Records could not load.")));
            button(content, "Retry", wrapper.refresh);
        } finally {if (current === request) content.attr("aria-busy", "false");}
    };

    function controls(meta) {
        const tools = $("<div class='k3ls-operation-toolbar'></div>").appendTo(content);
        const input = $("<input type='search' class='form-control'>").attr({placeholder: __("Search records"), "aria-label": __("Search records")}).val(search);
        let timer;
        input.on("input", () => {clearTimeout(timer); timer = setTimeout(() => {search = input.val(); offset = 0; wrapper.refresh();}, 400);});
        frappe.k3ls_search_field(input).appendTo(tools);
        if (meta.can_create) button(tools, "Add", () => edit(section), true);
        if (frappe.k3ls_review_filter?.section === section) button(tools, "Show all", () => {frappe.k3ls_review_filter = null; offset = 0; wrapper.refresh();});
        const owner = frappe.user.has_role("System Manager");
        const chosen = !owner && ["requests", "receipts", "deliveries"].includes(section) ? ["requests", "receipts", "deliveries"]
            : Object.values(groups).find(group => group.includes(section)) || [section];
        const tabs = $("<nav class='k3ls-operation-tabs' aria-label='Shop sections'></nav>").appendTo(content);
        for (const item of chosen) {
            if (!owner && ["owner-stock", "audit", "payables", "receivables", "unplanned", "debts", "plans", "account-checks", "trade-ins", "controls"].includes(item)) continue;
            button(tabs, titles[item], () => frappe.set_route("shop-operations", item)).toggleClass("selected", item === section).attr("aria-current", item === section ? "page" : "false");
        }
    }

    async function edit(kind, doc = null, defaults = {}) {
        const meta = metadata[kind] || await rpc("operations.metadata", {kind}, true);
        metadata[kind] = meta;
        const fields = meta.fields.map(field => ({...field, label: __(field.label), reqd: field.reqd || 0,
            ...(field.fieldtype === "Select" ? {options: String(field.options || "").split("\n").map(value => ({value, label: e(display(value))}))} : {}),
            ...(kind === "returns" && field.fieldname === "sale_line" ? {fieldtype: "Select", options: [""]} : {}),
            default: doc ? doc[field.fieldname] : defaults[field.fieldname] ?? (field.fieldtype === "Date" ? frappe.datetime.get_today() : field.default)}));
        // Native dialogs preserve drafts on errors and discard them on cancel.
        // Frappe inserts layout sections into its fields array. Keep those out of
        // the intake stage list so hiding later fields cannot hide the whole form.
        const dialog = new frappe.ui.Dialog({title: __(doc ? "Edit record" : titles[kind]), size: "extra-large", fields: [...fields],
            primary_action_label: __(doc ? "Save" : "Add"), primary_action: async values => {
                dialog.disable_primary_action();
                try {
                    const saved = await rpc("operations.save", {kind, values, name: doc?.name, modified: doc?.modified, request_key: requestKey});
                    dialog.hide(); await wrapper.refresh(); open(kind, saved.doc.name);
                } finally {dialog.enable_primary_action();}
            }});
        const requestKey = key();
        dialog.show();
        for (const field of fields) {
            if (field.fieldtype === "Table") {
                dialog.fields_dict[field.fieldname].df.data = structuredClone(doc?.[field.fieldname] || defaults[field.fieldname] || []);
                dialog.fields_dict[field.fieldname].grid.refresh();
            }
        }
        if (doc) dialog.set_values(doc);
        if (kind === "intake") {
            const grid = dialog.fields_dict.products.grid;
            const productField = grid.docfields.find(field => field.fieldname === "item");
            const pendingProducts = new Set();
            async function fill_product(row, force = false) {
                const item = row.item;
                if (!item) return;
                const pending = rpc("operations.intake_product", {item}, true);
                pendingProducts.add(pending);
                try {
                    const values = await pending;
                    if (row.item !== item || !grid.get_data().includes(row)) return;
                    for (const [field, value] of Object.entries(values)) if (value != null && (force || !row[field])) row[field] = value;
                    grid.refresh();
                } finally {pendingProducts.delete(pending);}
            }
            if (productField) productField.onchange = function () {return fill_product(this.grid_row.doc, true);};
            grid.refresh();
            for (const row of grid.get_data()) if (row.item && !doc) fill_product(row);
            const save = dialog.primary_action;
            dialog.primary_action = async values => {
                dialog.disable_primary_action();
                try {await Promise.all([...pendingProducts]); return await save({...values, products: structuredClone(grid.get_data())});}
                finally {dialog.enable_primary_action();}
            };
            if (doc) dialog.set_primary_action(__("Save"), dialog.primary_action);
            const fill_source = async () => {
                const supplier = dialog.get_value("supplier");
                if (!supplier) return;
                const values = await rpc("operations.source_details", {supplier}, true);
                if (dialog.get_value("supplier") !== supplier) return;
                for (const [field, value] of Object.entries({source_phone: values.phone, source_address: values.address, source_type: values.source_type, ownership: values.ownership})) {
                    if (dialog.fields_dict[field] && (field === "ownership" || field === "source_type" || !dialog.get_value(field))) await dialog.set_value(field, value);
                }
            };
            dialog.fields_dict.supplier.df.onchange = fill_source;
            if (!doc && defaults.supplier) fill_source();
            if (meta.owner) button(dialog.fields_dict.supplier.$wrapper, "New source", () => new_source(dialog));
            if (!doc) guided_intake(dialog, fields);
        }
        if (kind === "requests") {
            const sync = () => {
                const type = dialog.get_value("request_type");
                for (const name of ["amount", "paid_by", "category", "item", "serials", "related_doctype", "related_name"]) {
                    const visible = ["amount", "paid_by", "category"].includes(name) ? type === "Expense"
                        : name === "serials" ? ["Missing stock", "Write-off"].includes(type)
                        : name === "item" ? ["Missing stock", "Write-off", "Price change"].includes(type)
                        : ["Correction", "Cancel", "Delete", "Credit sale", "Refund"].includes(type);
                    dialog.set_df_property(name, "hidden", !visible);
                    dialog.set_df_property(name, "reqd", visible && !["category", "serials"].includes(name));
                }
            };
            dialog.fields_dict.request_type.df.onchange = sync;
            sync();
        }
        if (kind === "debts") {
            const sync = () => {
                const receive = dialog.get_value("direction") === "Customer owes us";
                for (const name of ["customer", "supplier"]) {
                    const active = receive === (name === "customer");
                    dialog.set_df_property(name, "hidden", !active); dialog.set_df_property(name, "reqd", active);
                    if (!active && dialog.get_value(name)) dialog.set_value(name, "");
                }
            };
            dialog.fields_dict.direction.df.onchange = sync;
            sync();
        }
        if (kind === "returns") {
            let lineRequest = 0;
            const choose_line = async () => {
                const current = ++lineRequest;
                const type = dialog.get_value("invoice_type"), invoice = dialog.get_value("invoice");
                if (!type || !invoice) return;
                const rows = await rpc("operations.sale_lines", {invoice_type: type, invoice}, true);
                if (current !== lineRequest || dialog.get_value("invoice") !== invoice) return;
                const field = dialog.fields_dict.sale_line;
                field.df.options = ["", ...rows.map(row => ({value: row.name, label: e(`${row.title || row.item} · ${row.quantity} ${__("pieces")}`)}))];
                field.refresh();
                field.df.onchange = () => {
                    const row = rows.find(row => row.name === dialog.get_value("sale_line"));
                    if (row) dialog.set_values({item: row.item, quantity: 1, serials: row.quantity === 1 ? row.serials : ""});
                };
                if (doc?.sale_line) dialog.set_value("sale_line", doc.sale_line);
            };
            dialog.fields_dict.invoice.df.onchange = choose_line;
            dialog.fields_dict.invoice_type.df.onchange = () => {++lineRequest; dialog.set_values({invoice: "", sale_line: "", item: ""});};
            choose_line();
        }
        dialog.fields_dict.supplier?.set_query?.(() => ({filters: {disabled: 0}}));
        dialog.fields_dict.customer?.set_query?.(() => ({filters: {disabled: 0, name: ["!=", "K3LS Walk-in Customer"]}}));
        for (const name of ["from_warehouse", "to_warehouse"]) dialog.fields_dict[name]?.set_query?.(() => ({filters: {company: "K3LS LIMITED", is_group: 0, disabled: 0}}));
        dialog.fields_dict.account?.set_query?.(() => ({filters: {company: "K3LS LIMITED", is_group: 0, disabled: 0, account_type: ["in", ["Cash", "Bank"]]}}));
        if (kind === "movements") {
            const sync = () => {
                const customerRepair = Boolean(dialog.get_value("repair"));
                for (const field of ["item", "from_warehouse", "to_warehouse"]) {dialog.set_df_property(field, "hidden", customerRepair); dialog.set_df_property(field, "reqd", !customerRepair);}
                for (const field of ["agent_customer", "agreed_amount", "settle_by"]) if (dialog.fields_dict[field]) {
                    const agent = dialog.get_value("movement_type") === "With agent";
                    dialog.set_df_property(field, "hidden", !agent); dialog.set_df_property(field, "reqd", agent);
                }
            };
            dialog.fields_dict.repair.df.onchange = sync;
            dialog.fields_dict.movement_type.df.onchange = sync;
            sync();
        }
        if (kind === "receipts") {
            const sync = () => {
                if (dialog.fields_dict.matched_on) dialog.set_df_property("matched_on", "hidden", dialog.get_value("method") === "Cash");
                for (const field of ["plan", "instalment", "reversal_of"]) if (dialog.fields_dict[field]) dialog.set_df_property(field, "hidden", true);
            };
            dialog.fields_dict.method.df.onchange = sync;
            sync();
        }
    }

    function guided_intake(dialog, fields) {
        const stages = [["supplier", "source_type", "ownership", "source_phone", "source_address", "source_reference", "received_on", "due_date", "arrangement"], ["products"], ["notes", "evidence"]];
        const names = ["Stock source", "Products received", "Save stock intake"];
        const required = Object.fromEntries(fields.map(field => [field.fieldname, field.reqd]));
        const save = dialog.primary_action;
        let stage = 0;
        const back = button(dialog.$wrapper.find(".modal-footer"), "Back", () => {stage--; show();});
        function show() {
            dialog.set_title(__(names[stage]));
            for (const field of fields) {
                dialog.set_df_property(field.fieldname, "hidden", !stages[stage].includes(field.fieldname));
                dialog.set_df_property(field.fieldname, "reqd", stage === 2 ? required[field.fieldname] : stages[stage].includes(field.fieldname) ? required[field.fieldname] : 0);
            }
            back.toggle(stage > 0);
            dialog.set_primary_action(__(stage === 2 ? "Save intake" : "Continue"), async values => {
                if (stage === 2) return save(values);
                stage++; show();
            });
        }
        show();
    }

    function new_source(parent) {
        const dialog = new frappe.ui.Dialog({title: __("New source"), fields: [
            {fieldname: "name", fieldtype: "Data", label: __("Name"), reqd: 1}, {fieldname: "phone", fieldtype: "Data", label: __("Phone"), reqd: 1},
            {fieldname: "address", fieldtype: "Small Text", label: __("Address"), reqd: 1}, {fieldname: "city", fieldtype: "Data", label: __("Town"), reqd: 1},
            {fieldname: "source_type", fieldtype: "Select", label: __("Type"), options: "Supplier\nIndividual seller\nSister owner\nExternal owner", reqd: 1},
            {fieldname: "customer", fieldtype: "Link", options: "Customer", label: __("Existing customer") }],
            primary_action_label: __("Add source"), primary_action: async values => {
                dialog.disable_primary_action();
                try {const source = await rpc("operations.add_source", values); dialog.hide(); await parent.set_values({supplier: source.name, source_phone: source.phone, source_address: source.address});}
                finally {dialog.enable_primary_action();}
            }});
        dialog.show();
    }

    async function open(kind, name) {
        const dialog = new frappe.ui.Dialog({title: __(titles[kind]), size: "extra-large", fields: [{fieldname: "body", fieldtype: "HTML"}]});
        const body = dialog.fields_dict.body.$wrapper;
        frappe.k3ls_loading(body, "Loading details"); dialog.show();
        try {
            const [meta, data] = await Promise.all([rpc("operations.metadata", {kind}, true), rpc("operations.details", {kind, name}, true)]);
            metadata[kind] = meta;
            const doc = data.doc;
            body.empty();
            $("<h3></h3>").text(doc.name).appendTo(body);
            if (doc.status) $("<p class='k3ls-operation-status'></p>").text(__(doc.status)).appendTo(body);
            const details = $("<dl class='k3ls-operation-details'></dl>").appendTo(body);
            for (const field of meta.display_fields) {
                const value = doc[field.fieldname];
                if (value == null || value === "" || field.fieldtype === "Table" || field.hidden) continue;
                $("<dt></dt>").text(__(field.label)).appendTo(details);
                $("<dd></dd>").text(field.fieldtype === "Currency" ? money(value) : field.fieldtype === "Check" ? __(value ? "Yes" : "No") : display(value)).appendTo(details);
            }
            for (const field of meta.display_fields.filter(field => field.fieldtype === "Table")) {
                const rows = doc[field.fieldname] || [];
                const columns = field.fields.filter(col => col.in_list_view);
                const table = $("<div class='k3ls-operation-table'><table class='table'><thead><tr></tr></thead><tbody></tbody></table></div>").appendTo(body);
                for (const col of columns) $("<th scope='col'></th>").text(__(col.label)).appendTo(table.find("thead tr"));
                $("<th scope='col'></th>").text(__("Details")).appendTo(table.find("thead tr"));
                for (const row of rows) {
                    const tr = $("<tr></tr>").appendTo(table.find("tbody"));
                    for (const col of columns) $("<td></td>").text(col.fieldtype === "Currency" ? money(row[col.fieldname] || 0) : row[col.fieldname] ?? "").appendTo(tr);
                    button($("<td></td>").appendTo(tr), "View", () => row_details(field, row));
                }
            }
            if (data.balance) $("<p></p>").text(`${__("Left to pay")}: ${money(data.balance.amount)}`).appendTo(body);
            if (data.plan) $("<p></p>").text(`${__("Not covered by plan")}: ${money(data.plan.unscheduled)} · ${__("Overdue payments")}: ${data.plan.overdue.length}`).appendTo(body);
            const actions = $("<div class='k3ls-operation-actions'></div>").appendTo(body);
            if (data.editable && kind !== "audit") button(actions, "Edit", () => {dialog.hide(); edit(kind, doc);});
            const run = (label, action, fields = []) => button(actions, label, () => confirm_action(kind, doc, action, label, fields, dialog), true);
            if (data.owner) {
                if (["Approved", "Rejected"].includes(doc.status)) run("Return for correction", "revise", [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}]);
                if (doc.status === "Pending" && kind !== "receipts") {
                    run("Approve", "approve"); run("Reject", "reject", [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}]);
                }
                if (doc.status === "Approved") {
                    const fields = kind === "returns" && ["Refund", "Exchange"].includes(doc.decision) ? [{fieldname: "method", fieldtype: "Select", label: __("Refund account"), options: "Cash\nMoniepoint MFB\nFCMB\nUBA", reqd: 1}]
                        : kind === "requests" && ["Write-off", "Missing stock"].includes(doc.request_type) ? [{fieldname: "quantity", fieldtype: "Int", label: __("Pieces remaining"), reqd: 1},
                            {fieldname: "serials", fieldtype: "Small Text", label: __("Serial numbers to remove"), default: doc.serials}]
                        : kind === "requests" && doc.request_type === "Price change" ? [{fieldname: "selling_price", fieldtype: "Currency", label: __("New selling price"), reqd: 1}]
                        : kind === "requests" && doc.request_type === "Correction" ? correction_fields(doc) : [];
                    run("Confirm", "post", fields);
                }
                if (kind === "receipts") {
                    if (doc.status === "Pending") {run("Verify payment", "verify"); run("Reject", "reject", [{fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1}]);}
                    if (doc.status === "Verified") {if (doc.method !== "Cash") run("Bank matched", "matched", [{fieldname: "date", fieldtype: "Date", label: __("Matched on"), default: frappe.datetime.get_today()}]);
                        run("Reverse payment", "reverse", [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}]);}
                }
                if (kind === "movements" && ["Sent", "Received"].includes(doc.status)) run("Returned to shop", "return");
                if (kind === "movements" && ["Sent", "Received"].includes(doc.status) && doc.movement_type === "With agent") run("Agent sold stock", "settle-agent", [{fieldname: "condition", fieldtype: "Small Text", label: __("Condition at sale"), reqd: 1}]);
                if (kind === "owner-stock" && doc.status === "Available") {
                    const fields = [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}, {fieldname: "serials", fieldtype: "Small Text", label: __("Serial numbers")}];
                    run("Return to owner", "return-owner", fields); run("Owner sold directly", "owner-direct", fields);
                    if (doc.arrangement === "On demand") run("Receive at shop", "receive-owner", [{fieldname: "serials", fieldtype: "Small Text", label: __("Serial numbers")}]);
                    run("Change owner terms", "terms", [{fieldname: "payout_per_piece", fieldtype: "Currency", options: "NGN", label: __("Payout per piece"), reqd: 1, default: doc.payout_per_piece},
                        {fieldname: "due_date", fieldtype: "Date", label: __("Pay owner by"), reqd: 1, default: doc.due_date},
                        {fieldname: "agreement", fieldtype: "Small Text", label: __("New agreement"), reqd: 1},
                        {fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}]);
                }
                if (kind === "account-checks" && doc.status === "Open") run("Mark reviewed", "reviewed");
                if (kind === "plans" && doc.status === "Active") {
                    run("Record follow-up", "contact", [{fieldname: "next_follow_up", fieldtype: "Date", label: __("Follow up on")},
                        {fieldname: "instalment", fieldtype: "Select", label: __("Instalment"), options: ["", ...doc.instalments.map(row => ({value: row.name, label: e(`${row.promise_date || row.due_date} · ${money(row.amount - (row.paid || 0))}`)}))]},
                        {fieldname: "promise_date", fieldtype: "Date", label: __("New promise date")}, {fieldname: "notes", fieldtype: "Small Text", label: __("Contact notes"), reqd: 1}]);
                    run("Close plan", "close");
                    for (const row of doc.instalments) if (row.amount > (row.paid || 0)) button(actions, `${__("Take payment")} · ${row.promise_date || row.due_date} · ${money(row.amount - (row.paid || 0))}`, () => {dialog.hide(); edit("receipts", null, {reference_type: doc.reference_type, reference_name: doc.reference_name, amount: row.amount - (row.paid || 0), plan: doc.name, instalment: row.name});});
                }
                if (kind === "deliveries" && doc.status === "Dispatched") run("Delivered", "delivered", [{fieldname: "proof", fieldtype: "Attach", label: __("Delivery proof"), reqd: 1}]);
                if (kind === "deliveries" && ["Pending", "Approved", "Dispatched"].includes(doc.status)) run("Cancel delivery", "cancel-delivery", [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1}]);
                if (kind === "controls" && doc.status !== "Done") button(actions, "Open user", () => {dialog.hide(); frappe.set_route("Form", "User", doc.user);});
                if (data.balance?.amount > 0) button(actions, "Record payment", () => {dialog.hide(); edit("receipts", null, {reference_type: doc.doctype, reference_name: doc.name, amount: data.balance.amount});});
            }
            if (kind === "movements" && doc.status === "Sent") run("Received", "received");
            if (kind === "requests" && doc.request_type === "Credit sale" && doc.related_name) button(actions, "Open saved sale", () => {dialog.hide(); frappe.set_route("Form", doc.related_doctype, doc.related_name);});
            if (kind === "receipts" && doc.checkout_sale) button(actions, "Open saved sale", () => {dialog.hide(); frappe.set_route("Form", "POS Invoice", doc.checkout_sale);});
            if (kind === "returns" && doc.status === "Done" && doc.decision === "Exchange") button(actions, "Choose replacement in POS", () => {dialog.hide(); frappe.set_route("point-of-sale");});
            for (const [field, type, label] of [["purchase_invoice", "Purchase Invoice", "Restock bill"], ["stock_entry", "Stock Entry", "Stock record"], ["invoice", "Sales Invoice", "Delivery bill"], ["repair", "K3LS Repair", "Repair"], ["journal", "Journal Entry", "Accounting record"]]) {
                if (!doc[field] || (field === "invoice" && kind !== "deliveries")) continue;
                button(actions, label, () => {dialog.hide(); frappe.set_route("Form", type, doc[field]);});
            }
        } catch (error) {body.empty().append($("<p role='alert'></p>").text(error.message || __("Details could not load.")));}
    }

    function row_details(field, row) {
        const dialog = new frappe.ui.Dialog({title: __(field.label), fields: [{fieldname: "body", fieldtype: "HTML"}]});
        const list = $("<dl class='k3ls-operation-details'></dl>").appendTo(dialog.fields_dict.body.$wrapper);
        for (const col of field.fields) if (row[col.fieldname] != null && row[col.fieldname] !== "" && !col.hidden) {
            $("<dt></dt>").text(__(col.label)).appendTo(list);
            $("<dd></dd>").text(col.fieldtype === "Currency" ? money(row[col.fieldname]) : display(row[col.fieldname])).appendTo(list);
        }
        dialog.show();
    }

    function confirm_action(kind, doc, action, label, fields, original) {
        const dialog = new frappe.ui.Dialog({title: __(label), fields: [{fieldname: "message", fieldtype: "HTML", options: `<p>${e(doc.name)}</p>`}, ...fields],
            primary_action_label: __(label), primary_action: async values => {
                dialog.disable_primary_action();
                try {
                    if (values.changed_field) values.changes = {[values.changed_field]: values.changed_value};
                    await rpc("operations.action", {kind, name: doc.name, modified: doc.modified, action, values});
                    dialog.hide(); original.hide(); await wrapper.refresh(); open(kind, doc.name);
                } finally {dialog.enable_primary_action();}
            }});
        dialog.show();
    }

    function correction_fields(doc) {
        const fields = {Item: {item_name: "Product name", custom_k3ls_model: "Model", custom_k3ls_configuration: "Specifications", custom_k3ls_mode: "Mode", custom_k3ls_colour: "Colour"},
            Customer: {customer_name: "Name", customer_details: "Notes"}, Supplier: {supplier_name: "Name", supplier_details: "Notes"},
            "K3LS Repair": {device: "Device", configuration: "Specifications", colour: "Colour", notes: "Notes"}};
        return [{fieldname: "changed_field", fieldtype: "Select", label: __("Change"), options: Object.entries(fields[doc.related_doctype] || {}).map(([value, label]) => ({value, label: __(label)})), reqd: 1},
            {fieldname: "changed_value", fieldtype: "Small Text", label: __("New value"), reqd: 1}];
    }

    async function money_list(current) {
        const data = await rpc("ops_money.overview", {}, true);
        if (current !== request) return;
        content.empty(); controls({can_create: false});
        const direction = section === "payables" ? "Pay" : "Receive";
        const filter = frappe.k3ls_review_filter?.section === section ? frappe.k3ls_review_filter : null;
        const rows = data.rows.filter(row => (section === "unplanned" ? row.unplanned_amount > 0 : row.direction === direction)
            && (!filter?.names || filter.names.includes(row.name)) && (!search || `${row.party} ${row.name} ${row.due_date || ""} ${row.overdue ? "overdue" : ""}`.toLowerCase().includes(search.toLowerCase())));
        $("<h2></h2>").text(money(rows.filter(row => row.currency === "NGN").reduce((total, row) => total + row.amount, 0))).appendTo(content);
        for (const row of rows) {
            const card = $("<section class='k3ls-operation-money'></section>").appendTo(content);
            $("<strong></strong>").text(`${row.party} · ${money(row.amount)}`).appendTo(card);
            if (section === "unplanned") $("<p></p>").text(`${__(row.direction === "Pay" ? "We owe" : "Customer owes")} · ${money(row.unplanned_amount)} ${__("without a plan")}`).appendTo(card);
            $("<p></p>").text(`${row.name} · ${row.overdue ? __("Overdue") : row.due_date || ""}`).appendTo(card);
            const actions = $("<div class='k3ls-operation-actions'></div>").appendTo(card);
            button(actions, "Record payment", () => row.plan ? open("plans", row.plan) : edit("receipts", null, {reference_type: row.type, reference_name: row.name, amount: row.amount}), true);
            button(actions, row.plan ? "Open plan" : "Plan payments", () => row.plan ? open("plans", row.plan) : edit("plans", null, {reference_type: row.type, reference_name: row.name}));
        }
        if (!rows.length) $("<p class='k3ls-shop-empty'></p>").text(__(search ? "No matching balances" : "Nothing left to pay")).appendTo(content);
    }
    async function inventory_list(current) {
        const filter = frappe.k3ls_review_filter?.section === section ? frappe.k3ls_review_filter : null;
        const data = await rpc("operations.inventory", {search, start: offset, item: frappe.get_route()[2], names: filter?.names}, true);
        if (current !== request) return;
        content.empty(); controls({can_create: false});
        for (const row of data.rows) {
            const card = $("<section class='k3ls-operation-money'></section>").appendTo(content);
            $("<h3></h3>").text(row.item_name).appendTo(card);
            $("<p></p>").text([row.custom_k3ls_model, row.custom_k3ls_configuration, row.custom_k3ls_colour, row.custom_k3ls_final_condition].filter(Boolean).join(" · ")).appendTo(card);
            for (const place of row.locations) $("<p></p>").text(`${place.warehouse} · ${place.pieces} ${__("pieces")}`).appendTo(card);
            for (const unit of row.units) button(card, `${unit.serial} · ${__(unit.status)}`, () => open("units", unit.name));
            for (const movement of row.movements) $("<p></p>").text(`${movement.custodian} · ${movement.phone || ""} · ${__(movement.status)}${movement.overdue ? " · " + __("Overdue") : ""} · ${movement.expected_return || ""}`).appendTo(card);
            button(card, "Move stock", () => edit("movements", null, {item: row.name}));
        }
        if (!data.rows.length) $("<p role='status'></p>").text(__("No matching products")).appendTo(content);
        if (offset) button(content, "Previous", () => {offset = Math.max(0, offset - 50); wrapper.refresh();});
        if (data.has_more) button(content, "More", () => {offset += 50; wrapper.refresh();});
    }

    async function dashboard(current) {
        const data = await rpc("operations.review", {}, true);
        if (current !== request) return;
        content.empty(); controls({can_create: false});
        for (const group of data.groups) {
            const card = $("<section class='k3ls-operation-money'></section>").appendTo(content);
            $("<h3></h3>").text(__(group.title)).appendTo(card);
            for (const metric of group.metrics) button(card, `${__(metric.title)} · ${metric.currency ? money(metric.value) : metric.value}`, () => {
                frappe.k3ls_review_filter = {section: metric.section, names: metric.names};
                return metric.section === "repairs" ? frappe.set_route("shop-repairs") : frappe.set_route("shop-operations", metric.section);
            });
        }
        if (data.owner) {
            const reports = $("<div class='k3ls-operation-actions'></div>").appendTo(content);
            for (const report of data.reports) button(reports, report.title, () => frappe.set_route("query-report", report.name, {company: "K3LS LIMITED"}));
            button(reports, "Export review", async () => {
                const result = await rpc("operations.export_review", {}, true);
                const url = URL.createObjectURL(new Blob([result.csv], {type: "text/csv;charset=utf-8"}));
                const link = document.createElement("a"); link.href = url; link.download = "K3LS-review.csv"; link.click(); URL.revokeObjectURL(url);
            });
        }
    }
    wrapper.show_section = kind => {section = kind === "review" ? "dashboard" : titles[kind] ? kind : "intake"; offset = 0; search = ""; page.set_title(__(titles[section])); return wrapper.refresh();};
    frappe.k3ls_operations_page = wrapper;
    wrapper.open_record = open;
    wrapper.add_record = edit;
    page.set_secondary_action(__("Refresh"), wrapper.refresh);
};
frappe.pages["shop-operations"].on_page_show = wrapper => {
    const route = frappe.get_route();
    const section = route[1] || frappe.route_options?.section || "intake";
    wrapper.show_section(section);
    if (route[2] && section !== "inventory") wrapper.open_record(section, route[2]);
    const pending = frappe.k3ls_pending_workflow;
    if (pending && pending.kind === section) {
        frappe.k3ls_pending_workflow = null;
        wrapper.add_record(pending.kind, null, pending.defaults);
    }
};
