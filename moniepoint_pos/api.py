"""Server-only terminal requests. Provider outcomes never post invoice payments."""
from decimal import Decimal
from uuid import uuid4
from urllib.parse import quote

import frappe
import requests
from frappe.utils import now_datetime

BASE_URL = "https://api.pos.moniepoint.com"


def _operator():
    frappe.only_for("System Manager")
    if frappe.request and frappe.request.method != "POST":
        frappe.throw("Use POST for this operation.", frappe.PermissionError)


def _settings():
    settings = frappe.get_single("Moniepoint Settings")
    if not settings.enabled:
        frappe.throw("Moniepoint integration is disabled.")
    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw("Configure the Moniepoint API key first.")
    return settings, {"Authorization": f"Bearer {key}", "Accept": "application/json"}


@frappe.whitelist()
def check_credentials():
    _operator()
    _, headers = _settings()
    try:
        response = requests.get(f"{BASE_URL}/v1/introspect", headers=headers, timeout=(5, 20), allow_redirects=False)
        if response.status_code != 200:
            frappe.throw("Moniepoint could not verify the credentials.")
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        frappe.throw("Moniepoint could not verify the credentials. Check access and retry.")
    if not isinstance(result, dict):
        frappe.throw("Moniepoint returned an invalid credential response.")
    return {key: result.get(key) for key in ("scopes", "businesses", "environment", "authMethod")}


@frappe.whitelist()
def request_payment(invoice, terminal):
    _operator()
    settings, headers = _settings()
    if not settings.contract_confirmed or settings.amount_units not in ("Kobo", "Naira"):
        frappe.throw("Confirm the API amount units with Moniepoint before requesting payment.")
    doc = frappe.get_doc("POS Invoice", invoice)
    doc.check_permission("write")
    # Serialize requests for this invoice, including concurrent operator clicks.
    frappe.db.sql("SELECT name FROM `tabPOS Invoice` WHERE name=%s FOR UPDATE", (doc.name,))
    device = frappe.get_doc("Moniepoint Terminal", terminal)
    device.check_permission("read")
    if doc.docstatus != 0 or doc.is_return or doc.currency != "NGN":
        frappe.throw("Use a saved, non-return NGN draft POS Invoice.")
    if not device.enabled or device.company != doc.company or device.pos_profile != doc.pos_profile:
        frappe.throw("This terminal is not enabled for the invoice company and POS Profile.")
    existing = frappe.db.get_value("Moniepoint Transaction", {"invoice": doc.name}, "name")
    if existing:
        frappe.throw(f"A payment request already exists: {existing}. Check its result before another charge.")
    rows = [row for row in doc.payments if row.mode_of_payment == device.mode_of_payment and row.amount > 0]
    if len(rows) != 1:
        frappe.throw("Set one positive payment row for the terminal's Mode of Payment.")
    amount = Decimal(str(rows[0].amount))
    total = Decimal(str(doc.rounded_total or doc.grand_total))
    if amount > total or amount <= 0:
        frappe.throw("Terminal payment must be positive and no greater than the invoice total.")
    scaled = amount * (100 if settings.amount_units == "Kobo" else 1)
    if scaled != scaled.to_integral_value() or scaled < 100 or scaled > 9223372036854775807:
        frappe.throw("Amount is outside the API integer limits for the configured units.")
    reference = f"erp-{uuid4().hex}"
    transaction = frappe.get_doc({
        "doctype": "Moniepoint Transaction", "invoice": doc.name, "terminal": device.name,
        "merchant_reference": reference, "request_amount": int(scaled),
        "amount_units": settings.amount_units, "payment_method": device.payment_method,
        "state": "Unknown",
    }).insert()
    # Persist before the network side effect. A crash/timeout must not allow a second charge.
    frappe.db.commit()
    try:
        response = requests.post(f"{BASE_URL}/v1/transactions", headers=headers, json={
            "terminalSerial": device.terminal_serial, "amount": int(scaled),
            "merchantReference": reference, "transactionType": "PURCHASE",
            "paymentMethod": device.payment_method,
        }, timeout=(5, 20), allow_redirects=False)
        state = "Accepted" if response.status_code == 202 else "Unknown"
    except requests.RequestException:
        state = "Unknown"
    transaction.db_set("state", state)
    return {"transaction": transaction.name, "merchant_reference": reference, "state": state}


@frappe.whitelist()
def check_payment(transaction):
    _operator()
    _, headers = _settings()
    record = frappe.get_doc("Moniepoint Transaction", transaction)
    record.check_permission("write")
    invoice = frappe.get_doc("POS Invoice", record.invoice)
    invoice.check_permission("read")
    device = frappe.get_doc("Moniepoint Terminal", record.terminal)
    try:
        response = requests.get(
            f"{BASE_URL}/v1/transactions/merchants/{quote(record.merchant_reference, safe='')}",
            headers=headers, timeout=(5, 20), allow_redirects=False,
        )
        if response.status_code == 404:
            return {"transaction": record.name, "state": "Unresolved"}
        if response.status_code != 200:
            frappe.throw("Could not retrieve the payment result. Do not retry the charge.")
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        frappe.throw("Could not retrieve the payment result. Do not retry the charge.")
    if not isinstance(result, dict) or any((
        result.get("merchantReference") != record.merchant_reference,
        result.get("terminalSerial") != device.terminal_serial,
        result.get("requestAmount") != record.request_amount,
        result.get("requestPaymentMethod") != record.payment_method,
        result.get("transactionType") != "PURCHASE",
    )):
        frappe.throw("The provider result does not match this payment request.")
    status = result.get("processingStatus")
    if status not in {"PENDING", "PROCESSED", "COMPLETED", "CANCELLED", "SUCCESSFUL", "FAILED", "REJECTED", "EXPIRED"}:
        frappe.throw("Moniepoint returned an unrecognized processing status.")
    actual = result.get("actualAmount")
    if actual is not None and (type(actual) is not int or actual < 0):
        frappe.throw("Moniepoint returned an invalid amount.")
    values = {"processing_status": status, "response_code": str(result.get("responseCode") or "")[:140],
              "last_checked": now_datetime()}
    if actual is not None:
        values["actual_amount"] = actual
    record.db_set(values)
    return {"transaction": record.name, "processing_status": status,
            "response_code": values["response_code"], "actual_amount": actual,
            "invoice_payment_posted": False}
