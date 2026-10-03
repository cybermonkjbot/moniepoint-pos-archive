/* Focus the core permission editor without granting, clearing or combining rights. */
(() => {
    if (!frappe.boot.k3ls_shop_ui || !frappe.user.has_role("System Manager")) return;
    const engine = frappe.PermissionEngine.prototype;
    if (engine.k3ls_simple_permissions) return;
    engine.k3ls_simple_permissions = true;
    const screens = {Item: "Products", Customer: "Customers", "POS Invoice": "Sales", "Sales Invoice": "Repair invoices",
        "K3LS Repair": "Repairs", Supplier: "Suppliers", "Purchase Invoice": "Restock", "Payment Entry": "Money in/out",
        Account: "Accounts", "POS Profile": "Checkout settings", User: "Users", "Moniepoint Settings": "Moniepoint settings",
        "Moniepoint Terminal": "Moniepoint terminals", "Moniepoint Transaction": "Moniepoint requests"};
    const roles = frappe.k3ls_role_labels;
    const rights = {read: "View", create: "Add", write: "Edit", submit: "Confirm", print: "Print"};
    const page_load = frappe.pages["permission-manager"].on_page_load;
    frappe.pages["permission-manager"].on_page_load = wrapper => {
        page_load(wrapper);
        wrapper.page.set_title(__("Shop access"));
        wrapper.page.wrapper.addClass("k3ls-permissions");
        wrapper.page.main.children().not(".perm-engine, .page-form").addClass("k3ls-permissions-help");
    };
    const options_for = (options, labels, advanced) => [{value: "", label: advanced ? "All" : "Choose"},
        ...options.filter(option => advanced || option.value in labels)
            .map(option => ({...option, label: advanced ? option.label : labels[option.value]}))];
    const setup_page = engine.setup_page;
    engine.setup_page = function () {
        setup_page.call(this);
        this.page.set_title(__("Shop access"));
        this.page.wrapper.addClass("k3ls-permissions");
        this.page.main.children().not(this.body).not(".page-form").addClass("k3ls-permissions-help");
        this.page.remove_inner_button(__("Set User Permissions"));
        this.doctype_select.$wrapper.hide();
        this.role_select.$wrapper.hide();
        this.k3ls_screen_select = this.page.add_field({fieldname: "shop_screen", fieldtype: "Select", label: __("Screen"),
            options: options_for(this.options.doctypes, screens, false), change: () => {
                const value = this.k3ls_screen_select.get_value();
                this.doctype_select.set_input(value);
                if (value) frappe.set_route("permission-manager", value);
                else this.refresh();
            }});
        this.k3ls_role_select = this.page.add_field({fieldname: "shop_role", fieldtype: "Select", label: __("Role"),
            options: options_for(this.options.roles, roles, false), change: () => {
                this.role_select.set_input(this.k3ls_role_select.get_value());
                this.refresh();
            }});
        this.k3ls_screen_select.$input.attr("aria-label", __("Screen"));
        this.k3ls_role_select.$input.attr("aria-label", __("Role"));
        this.k3ls_screen_select.$input.find("option[value='']").text(__("Choose screen"));
        this.k3ls_role_select.$input.find("option[value='']").text(__("All shop roles"));
        this.k3ls_more = this.page.add_menu_item(__("More options"), () => {
            this.k3ls_advanced = !this.k3ls_advanced;
            this.k3ls_more.find(".menu-item-label").text(__(this.k3ls_advanced ? "Fewer options" : "More options"));
            for (const [control, all, labels, selected] of [
                [this.k3ls_screen_select, this.options.doctypes, screens, this.get_doctype()],
                [this.k3ls_role_select, this.options.roles, roles, this.get_role()],
            ]) {
                // Keep directly routed advanced selections, rather than silently changing them.
                const options = options_for(all, labels, this.k3ls_advanced);
                if (selected && !options.some(option => option.value === selected)) {
                    options.push({value: selected, label: __(selected)});
                }
                control.df.options = options;
                control.refresh();
                control.set_input(selected);
            }
            this.k3ls_screen_select.$input.find("option[value='']").text(__(this.k3ls_advanced ? "All screens" : "Choose screen"));
            this.k3ls_role_select.$input.find("option[value='']").text(__(this.k3ls_advanced ? "All roles" : "All shop roles"));
            this.refresh();
        });
        this.page.add_menu_item(__("Users"), () => frappe.set_route("List", "User"));
        this.set_from_route();
    };
    engine.set_from_route = function () {
        // Route synchronization is not a user change. Do not trigger navigation while leaving this page.
        if (frappe.get_route()?.[0] !== "permission-manager") return;
        if (!this.doctype_select) {
            setTimeout(() => this.set_from_route(), 500);
            return;
        }
        const route_options = frappe.route_options || {};
        this.doctype_select.set_input(frappe.get_route()[1] || route_options.doctype || this.get_doctype() || "Item");
        this.role_select.set_input(route_options.role ?? this.get_role() ?? "");
        frappe.route_options = null;
        for (const [control, selected] of [[this.k3ls_screen_select, this.get_doctype()], [this.k3ls_role_select, this.get_role()]]) {
            if (!control) continue;
            if (selected && !control.df.options.some(option => option.value === selected)) {
                control.df.options = [...control.df.options, {value: selected, label: __(selected)}];
                control.refresh();
            }
            control.set_input(selected);
        }
        this.refresh();
    };
    engine.refresh = function () {
        this.page.clear_secondary_action();
        this.page.clear_primary_action();
        const request = this.k3ls_request = (this.k3ls_request || 0) + 1;
        if (!this.doctype_select) return frappe.k3ls_loading(this.body, "Loading access");
        const doctype = this.get_doctype(), role = this.get_role();
        if (!doctype && !role) return this.set_empty_message(__("Choose a screen or role."));
        frappe.k3ls_loading(this.body, "Loading access");
        return frappe.call({module: "frappe.core", page: "permission_manager", method: "get_permissions", args: {doctype, role}})
            .then(response => {
                if (request !== this.k3ls_request) return;
                this.body.attr("aria-busy", "false");
                this.render(response.message);
            }).catch(() => {
                if (request !== this.k3ls_request) return;
                this.body.empty().attr("aria-busy", "false").append($("<p role='alert'></p>").text(__("Access could not load.")));
                $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                    .on("click", () => this.refresh()).appendTo(this.body);
            });
    };
    const render = engine.render;
    engine.render = function (permissions) {
        const all = permissions || [];
        const visible = this.k3ls_advanced ? all : all.filter(row => !Number(row.permlevel) && row.parent in screens && row.role in roles);
        render.call(this, visible);
        this.perm_list = all;
        if (frappe.boot.read_only) this.body.find("input, .btn-remove-perm").prop("disabled", true);
        else $("<p class='k3ls-access-note'></p>").text(__("Changes save immediately.")).appendTo(this.body);
        this.page.main.children(".k3ls-permissions-help").toggle(Boolean(this.k3ls_advanced));
        if (!this.k3ls_advanced && visible.length !== all.length) {
            $("<p class='k3ls-access-note'></p>").text(__("Other access rules are in More options.")).appendTo(this.body);
        }
    };
    const show_table = engine.show_permission_table;
    engine.show_permission_table = function (permissions) {
        show_table.call(this, permissions);
        if (this.k3ls_advanced) return;
        this.table.find("thead th").eq(0).text(__("Screen"));
        this.table.find("thead th").eq(3).text(__("Access"));
        this.table.find("tr").each(function () {$(this).children().eq(2).hide(); $(this).children().eq(4).hide();});
    };
    const add_cell = engine.add_cell;
    engine.add_cell = function (row, permission, field) {
        const cell = add_cell.call(this, row, permission, field);
        if (!this.k3ls_advanced) cell.attr("data-label", __(field === "parent" ? "Screen" : field === "role" ? "Role" : "Access"));
        if (!this.k3ls_advanced && field === "parent") cell.text(__(screens[permission.parent] || permission.parent));
        return cell;
    };
    const show_users = engine.set_show_users;
    engine.set_show_users = function (cell, role) {
        show_users.call(this, cell, role);
        if (!this.k3ls_advanced) cell.find("a").text(__(roles[role] || role));
    };
    const add_check = engine.add_check;
    engine.add_check = function (cell, permission, field, label, description) {
        if (!this.k3ls_advanced && field !== "if_owner" && !(field in rights)) return;
        return add_check.call(this, cell, permission, field,
            this.k3ls_advanced ? label : field === "if_owner" ? "Own records only" : rights[field], description);
    };
    const add_rule = engine.show_add_rule;
    engine.show_add_rule = function () {
        if (frappe.boot.read_only) return;
        if (this.k3ls_advanced) return add_rule.call(this);
        this.page.set_primary_action(__("Add access"), () => {
            const dialog = new frappe.ui.Dialog({title: __("Add access"), fields: [
                {fieldname: "parent", fieldtype: "Select", label: __("Screen"), reqd: 1, options: options_for(this.options.doctypes, screens, false)},
                {fieldname: "role", fieldtype: "Select", label: __("Role"), reqd: 1, options: options_for(this.options.roles, roles, false)},
            ], primary_action_label: __("Add"), primary_action: async values => {
                if (!values) return;
                dialog.get_primary_btn().prop("disabled", true);
                try {
                    const response = await frappe.call({module: "frappe.core", page: "permission_manager", method: "add",
                        args: {...values, permlevel: 0}});
                    if (response.exc) return;
                    dialog.hide(); this.refresh();
                } finally {dialog.get_primary_btn().prop("disabled", false);}
            }});
            if (this.get_doctype() in screens) dialog.set_value("parent", this.get_doctype());
            if (this.get_role() in roles) dialog.set_value("role", this.get_role());
            dialog.show();
        }, "small-add");
    };
    const reset_button = engine.make_reset_button;
    engine.make_reset_button = function () {
        if (frappe.boot.read_only) return;
        if (this.k3ls_advanced) return reset_button.call(this);
    };
})();
