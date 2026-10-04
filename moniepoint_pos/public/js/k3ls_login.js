/* Keep Frappe's login requests, redirects, reset links and verification intact. */
(() => {
    if (!document.body.classList.contains("k3ls-login-page")) return;

    const apply = () => {
        $(".for-login .page-card-head h4, .for-email-login .page-card-head h4").text(__("Sign in"));
        $(".form-login .btn-login:not(.btn-ldap-login)").text(__("Sign in"));
        $(".for-forgot .page-card-head h4").text(__("Reset password"));
        $(".for-forgot .page-card-subtitle").text(__("We'll email you a reset link."));
        $(".for-forgot .btn-forgot").text(__("Send reset link"));
        $(".login-error-banner").attr({ role: "alert", "aria-live": "assertive" });
        $(".login-success-banner").attr({ role: "status", "aria-live": "polite" });
        $(".field-error").each(function (index) {
            const id = "k3ls-login-error-" + index;
            $(this).attr({ id, "aria-live": "polite" });
            $(this).closest(".form-group").find("input").attr("aria-describedby", id);
        });
        $(".toggle-password").attr({ role: "button", tabindex: "0", "aria-label": __("Show password"), "aria-pressed": "false" });
    };

    $(apply);
    $(document).on("login_rendered.k3ls", apply);
    // Core resets action labels when switching between sign-in and reset.
    $(window).on("hashchange.k3ls", apply);
    $(document).on("keydown.k3ls", ".toggle-password", function (event) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            $(this).trigger("click");
        }
    });
    $(document).on("click.k3ls", ".toggle-password", function () {
        const visible = $($(this).attr("toggle")).attr("type") === "text";
        $(this).attr({ "aria-label": visible ? __("Hide password") : __("Show password"), "aria-pressed": String(visible) });
    });
})();
