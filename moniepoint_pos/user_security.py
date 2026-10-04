"""Suppress core email flows without replacing Frappe's User model."""

import frappe
from frappe import _

from moniepoint_pos.shop_ui import enabled


class ShopUserSecurity:
    def before_insert(self):
        if enabled() and self.name not in ("Guest", "Administrator"):
            from moniepoint_pos.security import username_value, validate_password
            self.username = username_value(self.username)
            self.email = self.username + "@users.k3ls.invalid"
            validate_password(self.new_password, self.new_password, frappe.session.user)
        super().before_insert()

    def before_validate(self):
        if enabled() and self.name != "Guest":
            from moniepoint_pos.security import username_value
            self.send_welcome_email = 0
            self.flags.no_welcome_mail = True
            if self.name != "Administrator":
                self.username = username_value(self.username)
                if self.username == "administrator" or frappe.db.exists("User", {"username": self.username, "name": ["!=", self.name]}):
                    frappe.throw(_("Choose a different username."))
                if self.is_new() and not self.email:
                    self.email = self.username + "@users.k3ls.invalid"
            if self.new_password and not self.is_new():
                frappe.throw(_("Use Change password or Reset password instead of editing the password field."))
            old = self.get_doc_before_save()
            if old and self.username != old.username and frappe.session.user != "Administrator":
                frappe.only_for("System Manager")
        parent = getattr(super(), "before_validate", None)
        if parent:
            parent()

    def set_new_password(self, new_password=None):
        if not enabled():
            return super().set_new_password(new_password)
        if new_password and not self.flags.in_insert:
            frappe.throw(_("Use Change password or Reset password."))

    def send_password_notification(self, new_password):
        if not enabled():
            return super().send_password_notification(new_password)
        if self.flags.in_insert and new_password:
            from frappe.utils.password import update_password
            update_password(self.name, new_password)

    def _reset_password(self, send_email=False, password_expired=False):
        if not enabled():
            return super()._reset_password(send_email, password_expired)
        frappe.throw(_("Use a recovery code or ask an administrator to reset the password."), frappe.PermissionError)

    def password_reset_mail(self, link):
        if not enabled():
            return super().password_reset_mail(link)

    def send_welcome_mail_to_user(self):
        if not enabled():
            return super().send_welcome_mail_to_user()
