/* Password actions use dedicated dialogs, not email or inline profile fields. */
(() => {
    if (!frappe.boot.k3ls_shop_ui) return;
    const call = (method, args) => frappe.call({method: "moniepoint_pos.security." + method, type: "POST", args});
    const password_fields = [
        {fieldname: "new_password", fieldtype: "Password", label: __("New password"), reqd: 1, description: __("10 to 72 characters.")},
        {fieldname: "confirm_password", fieldtype: "Password", label: __("Repeat password"), reqd: 1},
    ];
    const current_password = {fieldname: "current_password", fieldtype: "Password", label: __("Your current password"), reqd: 1};
    const clear_secrets = dialog => dialog.$wrapper.on("hidden.bs.modal", () => {
        for (const name of ["new_password", "confirm_password", "current_password"]) {
            const field = dialog.fields_dict[name];
            if (field) {field.value = ""; field.$input?.val("");}
        }
    });
    const error_in = (dialog, error) => {
        dialog.fields_dict.error.$wrapper.text(error).attr("role", "alert");
    };
    const save_password = (user, self, username = user) => {
        const dialog = new frappe.ui.Dialog({title: self ? __("Change password") : __("Reset password for {0}", [username]), fields: [
            {...current_password, label: __(self ? "Your current password" : "Your admin password")},
            ...password_fields.map(field => ({...field})),
            {fieldname: "notice", fieldtype: "HTML", options: `<p>${__("The account will be signed out on all devices.")}</p>`},
            {fieldname: "error", fieldtype: "HTML"},
        ], primary_action_label: __(self ? "Change password" : "Reset password"), primary_action: async values => {
            if (!values) return;
            if (values.new_password !== values.confirm_password) return error_in(dialog, __("The passwords do not match."));
            dialog.get_primary_btn().prop("disabled", true);
            try {
                const response = await call("change_password", {user, new_password: values.new_password,
                    confirm_password: values.confirm_password, current_password: values.current_password});
                if (response.exc || !response.message?.changed) return;
                dialog.hide();
                if (response.message.sign_in_again) location.assign("/login");
                else frappe.show_alert({message: __("Password changed"), indicator: "green"});
            } finally { dialog.get_primary_btn().prop("disabled", false); }
        }});
        clear_secrets(dialog);
        dialog.show();
        dialog.fields_dict.new_password.$input.attr({autocomplete: "new-password", minlength: 10, maxlength: 72});
        dialog.fields_dict.confirm_password.$input.attr("autocomplete", "new-password");
        dialog.fields_dict.current_password.$input.attr("autocomplete", "current-password");
    };
    const show_codes = data => {
        let text = [__("Recovery codes for {0}", [data.username]), "",
            __("Each code works once. Keep this file private."), "", ...data.codes].join("\n");
        const dialog = new frappe.ui.Dialog({title: __("Recovery codes"), fields: [
            {fieldname: "codes", fieldtype: "HTML"},
        ], primary_action_label: __("Save codes"), primary_action: () => {
            const url = URL.createObjectURL(new Blob([text + "\n"], {type: "text/plain;charset=utf-8"}));
            const link = document.createElement("a");
            link.href = url;
            link.download = "K3LS-recovery-" + data.username.replace(/[^a-zA-Z0-9_.-]/g, "_") + ".txt";
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }});
        const wrapper = dialog.fields_dict.codes.$wrapper;
        $("<p></p>").text(__("100 one-use codes for {0}. Save them now. They will not be shown again.", [data.username])).appendTo(wrapper);
        $("<pre tabindex='0'></pre>").css({"max-height": "40vh", overflow: "auto", "white-space": "pre-wrap"}).text(data.codes.join("\n")).appendTo(wrapper);
        dialog.$wrapper.on("hidden.bs.modal", () => {wrapper.empty(); data.codes.length = 0; text = "";});
        dialog.show();
    };
    const generate_codes = user => {
        const dialog = new frappe.ui.Dialog({title: __("New recovery codes"), fields: [
            {fieldname: "notice", fieldtype: "HTML", options: `<p>${__("This replaces all unused recovery codes for this account.")}</p>`},
            {...current_password},
        ], primary_action_label: __("Generate 100 codes"), primary_action: async values => {
            if (!values) return;
            dialog.get_primary_btn().prop("disabled", true);
            try {
                const response = await call("generate_recovery_codes", {user, current_password: values.current_password});
                if (response.exc || !response.message?.codes) return;
                dialog.hide();
                show_codes(response.message);
            } finally { dialog.get_primary_btn().prop("disabled", false); }
        }});
        clear_secrets(dialog); dialog.show();
    };
    frappe.k3ls_account_security = async (user = frappe.session.user) => {
        const dialog = new frappe.ui.Dialog({title: __("Password and recovery"), fields: [{fieldname: "actions", fieldtype: "HTML"}]});
        const area = dialog.fields_dict.actions.$wrapper;
        dialog.show();
        const load = async () => {
            area.empty();
            $("<p role='status'></p>").text(__("Loading…")).appendTo(area);
            try {
                const response = await frappe.call({method: "moniepoint_pos.security.account_security", type: "GET", args: {user}});
                if (response.exc || !response.message) throw new Error("Account security unavailable");
                const data = response.message;
                area.empty();
                $("<p></p>").text(data.username).appendTo(area);
                $("<p></p>").text(__("{0} recovery codes left", [data.remaining])).appendTo(area);
                $("<button type='button' class='btn btn-primary'></button>").text(__(data.self ? "Change password" : "Reset password"))
                    .on("click", () => {dialog.hide(); save_password(user, data.self, data.username);}).appendTo(area);
                $("<button type='button' class='btn btn-default'></button>").css("margin-left", "12px").text(__("New recovery codes"))
                    .on("click", () => {dialog.hide(); generate_codes(user);}).appendTo(area);
            } catch {
                area.empty();
                $("<p role='alert'></p>").text(__("Could not open password settings. Check your connection and access."))
                    .appendTo(area);
                $("<button type='button' class='btn btn-default'></button>").text(__("Try again"))
                    .on("click", load).appendTo(area);
            }
        };
        await load();
    };
    frappe.k3ls_new_user = () => {
        const dialog = new frappe.ui.Dialog({title: __("New user"), fields: [
            {fieldname: "first_name", fieldtype: "Data", label: __("Name"), reqd: 1},
            {fieldname: "username", fieldtype: "Data", label: __("Username"), reqd: 1},
            ...password_fields.map(field => ({...field})), {...current_password},
            {fieldname: "error", fieldtype: "HTML"},
        ], primary_action_label: __("Add user"), primary_action: async values => {
            if (!values) return;
            if (values.new_password !== values.confirm_password) return error_in(dialog, __("The passwords do not match."));
            dialog.get_primary_btn().prop("disabled", true);
            try {
                const {first_name, username, new_password, confirm_password, current_password} = values;
                const response = await call("create_user", {first_name, username, new_password, confirm_password, current_password});
                if (response.exc || !response.message?.user) return;
                dialog.hide();
                frappe.set_route("Form", "User", response.message.user);
            } finally {dialog.get_primary_btn().prop("disabled", false);}
        }});
        clear_secrets(dialog); dialog.show();
        dialog.fields_dict.username.$input.attr({autocapitalize: "none", spellcheck: "false", autocomplete: "off"});
    };
    frappe.ui.form.on("User", {refresh(frm) {
        if (frm.doc.name === "Guest") return;
        if (frm.is_new()) {
            frm.page.set_primary_action(__("Add user"), frappe.k3ls_new_user);
            return;
        }
        const self = frm.doc.name === frappe.session.user;
        const admin = frappe.session.user === "Administrator" || frappe.user.has_role("System Manager");
        if (!self && (!admin || frm.doc.name === "Administrator")) return;
        const reset = () => save_password(frm.doc.name, self, frm.doc.username || frm.doc.name);
        // Keep password access visible on every tab, independent of the password section.
        frm.add_custom_button(__(self ? "Change password" : "Reset password"), reset);
        const section = frm.layout.sections_dict.change_password;
        if (!section) return;
        frm.toggle_display("change_password", true);
        section.body.removeClass("hide");
        section.body.find(".k3ls-password-actions").remove();
        const actions = $("<div class='k3ls-password-actions'></div>").appendTo(section.body);
        $("<button type='button' class='btn btn-primary'></button>").text(__(self ? "Change password" : "Reset password"))
            .on("click", reset).appendTo(actions);
        $("<button type='button' class='btn btn-default'></button>").css("margin-left", "12px").text(__("Recovery codes"))
            .on("click", () => frappe.k3ls_account_security(frm.doc.name)).appendTo(actions);
    }});
})();
