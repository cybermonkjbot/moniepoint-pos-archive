"""One shop-list search, using Frappe's permission-aware list and count queries."""
import re
from datetime import date, timedelta

import frappe
from frappe.desk import reportview
from frappe.model import get_permitted_fields
from frappe.types.filter import Filters
from frappe.utils import getdate, today


STATUS_ALIASES = {
    "partly paid": "Partly Paid", "part paid": "Partly Paid", "partially paid": "Partly Paid",
    "not finished": "Draft", "draft": "Draft", "confirmed": "Submitted", "submitted": "Submitted",
    "unpaid": "Unpaid", "paid": "Paid", "overdue": "Overdue", "cancelled": "Cancelled",
    "canceled": "Cancelled", "return": "Return", "debit note issued": "Debit Note Issued",
}

LISTS = {
    "Item": {"title": "products", "text": ["name", "item_code", "item_name", "item_group", "custom_k3ls_serial"], "date": "custom_k3ls_acquired_on", "check": "disabled", "invert": True},
    "Customer": {"title": "customers", "text": ["name", "customer_name", "mobile_no", "email_id"], "check": "disabled", "invert": True},
    "Supplier": {"title": "suppliers", "text": ["name", "supplier_name", "mobile_no", "email_id"], "check": "disabled", "invert": True},
    "K3LS Repair": {"title": "repairs", "text": ["name", "customer", "customer_phone", "device", "serial_no"], "date": "received_at", "status": "status"},
    "Purchase Invoice": {"title": "restock", "text": ["name", "supplier_name", "supplier", "bill_no"], "date": "posting_date", "status": "status"},
    "POS Invoice": {"title": "sales", "text": ["name", "customer", "customer_name", "contact_mobile"], "date": "posting_date", "status": "status"},
    "Sales Invoice": {"title": "invoices", "text": ["name", "customer", "customer_name", "contact_mobile"], "date": "posting_date", "status": "status"},
    "Payment Entry": {"title": "payments", "text": ["name", "party", "party_name", "reference_no", "mode_of_payment"], "date": "posting_date", "status": "status", "select": ["payment_type"]},
    "POS Profile": {"title": "checkout settings", "text": ["name", "warehouse"], "check": "disabled", "invert": True},
    "User": {"title": "users", "text": ["username", "full_name", "first_name", "last_name", "phone", "mobile_no"], "check": "enabled"},
    "Moniepoint Terminal": {"title": "terminals", "text": ["name", "terminal_serial", "pos_profile"], "check": "enabled"},
    "Moniepoint Transaction": {"title": "payment requests", "text": ["name", "merchant_reference", "invoice", "terminal"], "date": "creation", "status": "state"},
}


def search_terms(doctype, text):
    settings = LISTS[doctype]
    meta = frappe.get_meta(doctype)
    permitted = set(get_permitted_fields(doctype, ignore_virtual=True))
    text = " ".join(str(text or "").split())[:200]
    filters, alternatives, labels = [], [], []
    current = getdate(today())
    ranges = {
        "today": (current, current),
        "yesterday": (current - timedelta(days=1), current - timedelta(days=1)),
        "this week": (current - timedelta(days=current.weekday()), current),
        "this month": (current.replace(day=1), current),
    }
    date_field = settings.get("date")
    if date_field in permitted:
        match = re.search(r"(?<!\S)(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}|today|yesterday|this week|this month)(?!\S)", text, re.I)
        if match:
            value = match.group().casefold()
            if value in ranges:
                first, last = ranges[value]
                labels.append(value.capitalize())
            else:
                parts = [int(part) for part in re.split(r"[/.\-]", value)]
                year, month, day = parts if re.match(r"\d{4}-", value) else (parts[2], parts[1], parts[0])
                try:
                    first = last = date(year, month, day)
                except ValueError:
                    frappe.throw("Use a valid date, such as 03/10/2026.")
                labels.append(first.strftime("%d %b %Y"))
            df = meta.get_field(date_field)
            if date_field == "creation" or df.fieldtype == "Datetime":
                filters.extend([[doctype, date_field, ">=", str(first)], [doctype, date_field, "<", str(last + timedelta(days=1))]])
            else:
                filters.append([doctype, date_field, "between", [str(first), str(last)]])
            text = (text[:match.start()] + " " + text[match.end():]).strip()

    choices = {}
    status_field = settings.get("status")
    for field in [status_field, *settings.get("select", [])]:
        df = meta.get_field(field) if field in permitted else None
        if not df or df.fieldtype != "Select":
            continue
        for option in (df.options or "").splitlines():
            if option:
                choices[option.casefold()] = (field, option, option)
        if field == status_field:
            for phrase, value in STATUS_ALIASES.items():
                if value in (df.options or "").splitlines():
                    choices[phrase] = (field, value, "Not finished" if value == "Draft" else "Confirmed" if value == "Submitted" else value)
            for phrase, value in {"checking": "Diagnosing", "ready": "Ready for collection"}.items():
                if value in (df.options or "").splitlines():
                    choices[phrase] = (field, value, phrase.capitalize())
        if field == "payment_type":
            for phrase, value in {"money in": "Receive", "money out": "Pay", "move between accounts": "Internal Transfer"}.items():
                choices[phrase] = (field, value, phrase.capitalize())
    check = settings.get("check")
    if check in permitted:
        for phrase, active in {"active": True, "enabled": True, "inactive": False, "disabled": False}.items():
            choices[phrase] = (check, int(not active if settings.get("invert") else active), "Active" if active else "Inactive")
    for phrase in sorted(choices, key=len, reverse=True):
        if text.casefold() == phrase or text.casefold().endswith(" " + phrase):
            field, value, label = choices[phrase]
            filters.append([doctype, field, "=", value])
            labels.append(label)
            text = text[:-len(phrase)].strip()
            break
    if text:
        # Values stay query parameters. Escape LIKE wildcards so search text is literal.
        pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        alternatives = [[doctype, field, "like", pattern]
            for field in settings["text"] if field in permitted]
    return filters, alternatives, labels


def apply_search():
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        frappe.throw("Shop search is unavailable.", frappe.PermissionError)
    args = reportview.get_form_params()
    if args.doctype not in LISTS:
        frappe.throw("Choose a shop list.", frappe.PermissionError)
    frappe.has_permission(args.doctype, "read", throw=True)
    filters, alternatives, labels = search_terms(args.doctype, args.pop("shop_search", ""))
    # Existing advanced filters remain AND constraints. Do not overwrite them.
    args.filters = [list(item) for item in Filters(args.filters or [], doctype=args.doctype)] + filters
    if alternatives:
        if args.or_filters:
            frappe.throw("Clear the advanced search before using this search.")
        args.or_filters = alternatives
    frappe.local.form_dict = args
    return labels


@frappe.whitelist(methods=["GET", "POST"])
@frappe.read_only()
def search():
    labels = apply_search()
    result = reportview.get()
    if not result:
        result = {"keys": [], "values": [], "user_info": {}}
    result["search_labels"] = labels
    return result


@frappe.whitelist(methods=["GET", "POST"])
@frappe.read_only()
def count():
    apply_search()
    return reportview.get_count()
