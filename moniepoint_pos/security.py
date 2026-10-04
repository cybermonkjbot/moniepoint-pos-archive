"""Username sign-in and account-scoped, single-use password recovery."""

import hashlib
import hmac
import re
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, today
from frappe.utils.password import check_password, update_password

CODE_COUNT = 100
CODE_DOCTYPE = "K3LS Recovery Code"
USERNAME_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9_.-]{2,39}"


def require_shop():
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        frappe.throw(_("Account security is unavailable."), frappe.PermissionError)


def username_value(value):
    value = str(value or "").strip().lower()
    if not re.fullmatch(USERNAME_PATTERN, value) or value == "guest":
        frappe.throw(_("Use 3 to 40 letters, numbers, dots, dashes or underscores for the username."))
    return value


def find_username(value):
    value = str(value or "").strip().lower()
    if value == "administrator":
        return frappe.db.get_value("User", "Administrator", ["name", "enabled", "username"], as_dict=True)
    if not re.fullmatch(USERNAME_PATTERN, value) or value == "guest":
        return None
    return frappe.db.get_value("User", {"username": value}, ["name", "enabled", "username"], as_dict=True)


def before_login(login_manager=None):
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        return
    supplied = frappe.form_dict.get("usr")
    if not supplied and frappe.form_dict.get("otp"):
        return  # Core validates the cached password and verification token.
    user = find_username(supplied)
    if not user or not user.enabled:
        from frappe.auth import get_login_attempt_tracker
        tracker = get_login_attempt_tracker(frappe.local.request_ip)
        tracker and tracker.add_failure_attempt()
        if login_manager:
            login_manager.fail(_("Incorrect username or password."), user=str(supplied or "")[:80])
        frappe.throw(_("Incorrect username or password."), frappe.AuthenticationError)
    # Keep existing record IDs and permissions. Only resolve the sign-in name.
    frappe.form_dict.usr = user.name


def before_request():
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        return
    frappe.flags.mute_emails = True
    cmd = str(frappe.form_dict.get("cmd") or "")
    path = frappe.request.path
    recovery_method = "moniepoint_pos.security.recover_password"
    if cmd == recovery_method or path.endswith("/" + recovery_method):
        # Account rate limits must not be bypassed by changing username case.
        frappe.form_dict.username = str(frappe.form_dict.get("username") or "").strip().lower()
        frappe.local.response_headers["Cache-Control"] = "no-store"
    email_methods = {
        "frappe.www.login.send_login_link", "frappe.www.login.login_via_key", "frappe.www.login.login_via_token",
        "frappe.core.doctype.user.user.reset_password", "frappe.core.doctype.user.user.sign_up",
        "frappe.integrations.doctype.ldap_settings.ldap_settings.login",
    }
    blocked_paths = {prefix + method for prefix in ("/api/method/", "/api/v1/method/", "/api/v2/method/") for method in email_methods}
    if cmd in email_methods or path in blocked_paths or any(path.startswith(prefix + "frappe.integrations.oauth2_logins.") for prefix in ("/api/method/", "/api/v1/method/", "/api/v2/method/")):
        frappe.throw(_("Use a username and password, or a recovery code."), frappe.PermissionError)


def require_user_access(user):
    require_shop()
    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in first."), frappe.PermissionError)
    target = frappe.get_doc("User", user)
    if target.name == "Guest":
        frappe.throw(_("The guest account cannot be changed."), frappe.PermissionError)
    if target.name != frappe.session.user:
        frappe.only_for("System Manager")
        # Owners may manage staff, but only Administrator can reset itself.
        if target.name == "Administrator" and frappe.session.user != "Administrator":
            frappe.throw(_("Only Administrator can change this account's password or recovery codes."), frappe.PermissionError)
    return target


def verify_actor(password):
    if not password:
        frappe.throw(_("Enter your current password."))
    check_password(frappe.session.user, password)


def lock_user(user):
    if not frappe.db.sql("SELECT name FROM `tabUser` WHERE name=%s FOR UPDATE", (user,)):
        frappe.throw(_("Account unavailable."), frappe.PermissionError)


def validate_password(password, confirm_password, user):
    from frappe.core.doctype.user.user import handle_password_test_fail, test_password_strength
    if not isinstance(password, str) or len(password) < 10 or len(password) > 72:
        frappe.throw(_("Use a password between 10 and 72 characters."))
    if password != confirm_password:
        frappe.throw(_("The passwords do not match."))
    data = frappe.db.get_value("User", user, ["first_name", "last_name", "username"])
    result = test_password_strength(password, user_data=data)
    feedback = result.get("feedback")
    if feedback and not feedback.get("password_policy_validation_passed"):
        handle_password_test_fail(feedback)


def set_password(user, password):
    existing_sessions = frappe.get_all("Sessions", filters={"user": user}, pluck="sid")
    update_password(user, password)
    frappe.db.set_value("User", user, {
        "reset_password_key": "", "last_reset_password_key_generated_on": None,
        "last_password_reset_date": today(),
    })
    # Clear sessions after the password/code transaction commits, not before.
    frappe.db.after_commit.add(lambda: reset_user_sessions(user, existing_sessions))
    frappe.clear_cache(user=user)


def reset_user_sessions(user, session_ids):
    # Capture existing sessions so a new sign-in racing the reset is not removed.
    from frappe.sessions import delete_session
    for sid in session_ids:
        delete_session(sid, user=user, reason="Password changed")
    if frappe.request and frappe.session.sid in session_ids:
        # sync_database schedules Session.update after this callback. Replace
        # the revoked current session so that update cannot cache it again.
        response = dict(frappe.local.response)
        try:
            frappe.local.login_manager.clear_cookies()
            frappe.local.login_manager.login_as_guest()
        finally:
            # Guest session creation must not overwrite the password result.
            frappe.local.response.clear()
            frappe.local.response.update(response)


def code_hash(user, code):
    from frappe.utils.password import get_encryption_key
    normalized = re.sub(r"[\s-]", "", str(code or "")).upper()
    if not re.fullmatch(r"[0-9A-F]{32}", normalized):
        normalized = "invalid"
    message = "k3ls-recovery-v1\0" + user + "\0" + normalized
    return hmac.new(get_encryption_key().encode(), message.encode(), hashlib.sha256).hexdigest()


@frappe.whitelist(methods=["GET"])
def account_security(user=None):
    target = require_user_access(user or frappe.session.user)
    return {
        "username": "Administrator" if target.name == "Administrator" else target.username,
        "remaining": frappe.db.count(CODE_DOCTYPE, {"user": target.name, "used_at": ["is", "not set"], "revoked": 0}),
        "self": target.name == frappe.session.user,
    }


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=900)
def change_password(new_password, confirm_password, current_password, user=None):
    target = require_user_access(user or frappe.session.user)
    lock_user(target.name)
    verify_actor(current_password)
    validate_password(new_password, confirm_password, target.name)
    set_password(target.name, new_password)
    return {"changed": True, "sign_in_again": target.name == frappe.session.user}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=900)
def generate_recovery_codes(current_password, user=None):
    target = require_user_access(user or frappe.session.user)
    lock_user(target.name)
    verify_actor(current_password)
    if not target.enabled:
        frappe.throw(_("Activate the user before generating recovery codes."))
    frappe.db.set_value(CODE_DOCTYPE, {"user": target.name, "revoked": 0}, "revoked", 1)
    codes = [secrets.token_hex(16).upper() for _ in range(CODE_COUNT)]
    created = now_datetime()
    batch = secrets.token_hex(16)
    frappe.db.bulk_insert(CODE_DOCTYPE,
        ["name", "creation", "modified", "owner", "modified_by", "docstatus", "user", "code_hash", "batch", "revoked"],
        [(secrets.token_hex(16), created, created, frappe.session.user, frappe.session.user, 0,
          target.name, code_hash(target.name, code), batch, 0) for code in codes])
    frappe.local.response_headers["Cache-Control"] = "no-store"
    return {"username": "Administrator" if target.name == "Administrator" else target.username,
            "codes": ["-".join(code[index:index + 8] for index in range(0, 32, 8)) for code in codes]}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=900)
@rate_limit(key="username", limit=10, seconds=3600, ip_based=False)
def recover_password(username, token, new_password, confirm_password):
    require_shop()
    user = find_username(username)
    if not user or not user.enabled:
        frappe.throw(_("The username or recovery code is incorrect or already used."), frappe.AuthenticationError)
    lock_user(user.name)
    matches = frappe.db.sql(
        "SELECT name FROM `tabK3LS Recovery Code` WHERE user=%s AND code_hash=%s AND used_at IS NULL AND revoked=0 FOR UPDATE",
        (user.name, code_hash(user.name, token)), as_dict=True)
    if not matches:
        frappe.throw(_("The username or recovery code is incorrect or already used."), frappe.AuthenticationError)
    validate_password(new_password, confirm_password, user.name)
    # The lock and transaction cover both password change and code use.
    set_password(user.name, new_password)
    frappe.db.set_value(CODE_DOCTYPE, matches[0].name, {"used_at": now_datetime()})
    return {"changed": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def email_reset_disabled(**kwargs):
    require_shop()
    frappe.throw(_("Use a recovery code to reset your password."), frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def password_update(new_password, logout_all_sessions=0, key=None, old_password=None):
    require_shop()
    if key or frappe.session.user == "Guest":
        frappe.throw(_("Use a recovery code to reset your password."), frappe.PermissionError)
    return change_password(new_password, new_password, old_password)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=900)
def create_user(username, first_name, new_password, confirm_password, current_password):
    require_shop()
    frappe.only_for("System Manager")
    verify_actor(current_password)
    username = username_value(username)
    if username == "administrator" or frappe.db.exists("User", {"username": username}):
        frappe.throw(_("Choose a different username."))
    if not str(first_name or "").strip():
        frappe.throw(_("Enter the user's name."))
    validate_password(new_password, confirm_password, frappe.session.user)
    user = frappe.get_doc({"doctype": "User", "email": username + "@users.k3ls.invalid", "username": username,
        "first_name": str(first_name).strip(), "enabled": 1, "user_type": "System User",
        "send_welcome_email": 0, "new_password": new_password,
        "roles": [{"role": "Sales User"}, {"role": "Stock User"}, {"role": "K3LS Repair Staff"}]})
    user.insert()
    return {"user": user.name, "username": user.username}


def configure():
    """Install only the recovery table and no-email account settings."""
    require_shop()
    frappe.only_for("System Manager")
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "DocType", CODE_DOCTYPE, force=True)
    settings = frappe.get_single("System Settings")
    for field, value in {"allow_login_using_user_name": 1, "allow_login_using_mobile_number": 0,
        "login_with_email_link": 0, "disable_user_pass_login": 0, "force_user_to_reset_password": 0,
        "enable_password_policy": 1, "minimum_password_score": 3}.items():
        settings.set(field, value)
    settings.save(ignore_permissions=True)
    frappe.db.set_default("suspend_email_queue", 1)
    frappe.db.set_single_value("Website Settings", "disable_signup", 1)
    frappe.db.set_single_value("LDAP Settings", "enabled", 0)
    # Keep TOTP if enabled, but never an email-based second factor.
    if frappe.db.get_single_value("System Settings", "two_factor_method") == "Email":
        frappe.db.set_single_value("System Settings", "two_factor_method", "OTP App")
    frappe.db.sql("UPDATE `tabUser` SET send_welcome_email=0, reset_password_key='', last_reset_password_key_generated_on=NULL")
    for row in frappe.get_all("User", filters={"name": ["not in", ["Guest", "Administrator"]]}, fields=["name", "first_name", "username"]):
        if row.username and re.fullmatch(USERNAME_PATTERN, row.username) and row.username.lower() not in ("administrator", "guest"):
            continue
        base = re.sub(r"[^a-z0-9_.-]", "", (row.first_name or "user").lower())[:30]
        if len(base) < 3 or not re.match(r"[a-z0-9]", base) or base in ("administrator", "guest"):
            base = "user"
        candidate = base
        index = 1
        while frappe.db.exists("User", {"username": candidate, "name": ["!=", row.name]}):
            candidate = base + str(index)
            index += 1
        frappe.db.set_value("User", row.name, "username", candidate)
    from frappe.installer import update_site_config
    update_site_config("mute_emails", 1)
    frappe.conf.mute_emails = 1
    frappe.flags.mute_emails = True
    frappe.db.commit()
    frappe.clear_cache()
    return {"username_login": True, "email_disabled": True, "codes_per_batch": CODE_COUNT}


def provision_owner_recovery_codes():
    """Console-only initial export. Never put account recovery codes in a release."""
    from pathlib import Path
    import os
    require_shop()
    frappe.only_for("Administrator")
    lock_user("Administrator")
    if frappe.db.count(CODE_DOCTYPE, {"user": "Administrator", "used_at": ["is", "not set"], "revoked": 0}):
        return {"created": False, "reason": "An active recovery-code set already exists."}
    codes = [secrets.token_hex(16).upper() for _ in range(CODE_COUNT)]
    created = now_datetime()
    batch = secrets.token_hex(16)
    frappe.db.bulk_insert(CODE_DOCTYPE,
        ["name", "creation", "modified", "owner", "modified_by", "docstatus", "user", "code_hash", "batch", "revoked"],
        [(secrets.token_hex(16), created, created, "Administrator", "Administrator", 0,
          "Administrator", code_hash("Administrator", code), batch, 0) for code in codes])
    folder = Path(frappe.get_site_path("private", "k3ls-recovery"))
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = folder / ("Administrator-" + batch + ".txt")
    file_descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(file_descriptor, "w") as output:
        output.write("K3LS Administrator recovery codes\nEach code works once. Keep this file private.\n\n")
        output.write("\n".join("-".join(code[index:index + 8] for index in range(0, 32, 8)) for code in codes) + "\n")
    frappe.db.commit()
    return {"created": True, "count": CODE_COUNT, "file": str(destination.resolve())}


def security_configuration_snapshot():
    """Console-only rollback copy of settings changed by this security update."""
    require_shop()
    frappe.only_for("Administrator")
    fields = ["allow_login_using_user_name", "allow_login_using_mobile_number", "login_with_email_link",
        "disable_user_pass_login", "force_user_to_reset_password", "enable_password_policy", "minimum_password_score", "two_factor_method"]
    return {
        "system": {field: frappe.db.get_single_value("System Settings", field) for field in fields},
        "signup": frappe.db.get_single_value("Website Settings", "disable_signup"),
        "ldap": frappe.db.get_single_value("LDAP Settings", "enabled"),
        "mute_emails": frappe.conf.get("mute_emails"),
        "suspend_email_queue": frappe.db.get_default("suspend_email_queue"),
        "users": frappe.get_all("User", fields=["name", "username", "send_welcome_email"]),
    }


def restore_security_configuration(snapshot_path):
    """Console-only rollback. Never restore passwords, codes or old reset links."""
    import json
    from pathlib import Path
    from frappe.installer import update_site_config
    frappe.only_for("Administrator")
    path = Path(snapshot_path).resolve(strict=True)
    if not path.is_relative_to(Path("/opt/k3ls/updates")) or path.name != "security-before.json":
        frappe.throw("Invalid security snapshot path.")
    data = json.loads(path.read_text())
    for field, value in data["system"].items():
        frappe.db.set_single_value("System Settings", field, value)
    frappe.db.set_single_value("Website Settings", "disable_signup", data["signup"])
    frappe.db.set_single_value("LDAP Settings", "enabled", data["ldap"])
    update_site_config("mute_emails", data["mute_emails"] if data["mute_emails"] is not None else "None")
    frappe.db.set_default("suspend_email_queue", data["suspend_email_queue"] or 0)
    for user in data["users"]:
        if frappe.db.exists("User", user["name"]):
            frappe.db.set_value("User", user["name"], {"username": user["username"], "send_welcome_email": user["send_welcome_email"]})
    frappe.db.commit()
    frappe.clear_cache()
    return {"security_settings_restored": True}
