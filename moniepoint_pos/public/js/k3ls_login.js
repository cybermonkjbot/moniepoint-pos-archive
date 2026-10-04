/* Keep Frappe's password authentication and verification; recovery uses codes. */
(() => {
    if (!document.body.classList.contains("k3ls-login-page")) return;

    const apply = () => {
        $(".for-login .page-card-head h4, .for-email-login .page-card-head h4").text(__("Sign in"));
        $(".form-login .btn-login:not(.btn-ldap-login)").text(__("Sign in"));
        $(".for-forgot .page-card-head h4").text(__("Reset password"));
        $(".login-error-banner").attr({ role: "alert", "aria-live": "assertive" });
        $(".login-success-banner").attr({ role: "status", "aria-live": "polite" });
        $(".field-error").each(function (index) {
            const id = "k3ls-login-error-" + index;
            $(this).attr({ id, "aria-live": "polite" });
            $(this).closest(".form-group").find("input").attr("aria-describedby", id);
        });
        $(".toggle-password").each(function () {
            const visible = $($(this).attr("toggle")).attr("type") === "text";
            $(this).attr({ "aria-label": visible ? __("Hide password") : __("Show password"), "aria-pressed": String(visible) });
        });
    };

    $(function () {
        apply();
        const show_error = login.show_field_error;
        login.show_field_error = function (id, message) {
            return show_error(id, id === "login_email" ? __("Enter your username.") : message);
        };
        // Reset actions never request email or create an email reset token.
        login.forgot = function () {
            login.reset_sections();
            $(".for-forgot").show();
            $("#recovery_username").val($("#login_email").val() || "").trigger("focus");
        };
        $(".k3ls-form-recovery").on("submit", async function (event) {
            event.preventDefault();
            if (!this.reportValidity()) return;
            const button = $(this).find("button[type=submit]");
            const password = $("#recovery_password").val();
            if (password !== $("#recovery_confirm").val()) {
                login.show_error_banner(__("The passwords do not match."));
                return;
            }
            button.prop("disabled", true).text(__("Resetting password"));
            try {
                const response = await frappe.call({method: "moniepoint_pos.security.recover_password", type: "POST", args: {
                    username: $("#recovery_username").val().trim(), token: $("#recovery_code").val().trim(),
                    new_password: password, confirm_password: $("#recovery_confirm").val(),
                }});
                if (!response.message?.changed || response.exc) return;
                $("#login_email").val($("#recovery_username").val());
                this.reset();
                $("#login_password").val("");
                window.location.hash = "login";
                frappe.msgprint({title: __("Password changed"), message: __("Sign in with your new password.")});
            } finally { button.prop("disabled", false).text(__("Reset password")); }
        });
        $(window).on("hashchange.k3ls-recovery", () => {
            if (window.location.hash !== "#forgot") $("#recovery_code, #recovery_password, #recovery_confirm").val("");
        });
        if (window.location.hash === "#forgot") login.forgot();
    });
    $(document).on("login_rendered.k3ls", apply);
    // Core resets action labels when switching between sign-in and reset.
    $(window).on("hashchange.k3ls", apply);
    $(document).on("click.k3ls", ".toggle-password", function () {
        const visible = $($(this).attr("toggle")).attr("type") === "text";
        $(this).attr({ "aria-label": visible ? __("Hide password") : __("Show password"), "aria-pressed": String(visible) });
    });
})();
