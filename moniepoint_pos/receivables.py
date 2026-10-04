"""Unpaid customer invoices, without double-counting consolidated POS sales."""
import frappe
import math
from frappe.utils import flt, cint, now_datetime, today

COMPANY = "K3LS LIMITED"


def filters(doctype, customer=None):
    result = {"company": COMPANY, "docstatus": 1, "is_return": 0, "outstanding_amount": [">", 0]}
    if doctype == "POS Invoice":
        result["consolidated_invoice"] = ["is", "not set"]
    if customer:
        result["customer"] = customer
    return result


@frappe.whitelist(methods=["GET"])
def overview():
    frappe.only_for("System Manager")
    customers = {}
    for doctype in ("POS Invoice", "Sales Invoice"):
        # Permission filtering is retained on the aggregate query.
        rows = frappe.get_list(doctype, filters=filters(doctype),
            fields=["customer", "customer_name", "currency", {"SUM": "outstanding_amount", "as": "owed"},
                {"COUNT": "name", "as": "invoices"}, {"MIN": "due_date", "as": "first_due"}],
            group_by="customer, customer_name, currency", order_by=None, limit_page_length=0)
        for row in rows:
            key = (row.customer, row.currency)
            entry = customers.setdefault(key, {"customer": row.customer, "customer_name": row.customer_name,
                "currency": row.currency, "owed": 0, "invoices": 0, "first_due": None})
            entry["owed"] += flt(row.owed)
            entry["invoices"] += cint(row.invoices)
            if row.first_due and (not entry["first_due"] or str(row.first_due) < str(entry["first_due"])):
                entry["first_due"] = row.first_due
    rows = sorted(customers.values(), key=lambda row: (row["currency"], -row["owed"], row["customer"]))
    for row in rows:
        row["overdue"] = bool(row["first_due"] and str(row["first_due"]) < today())
    return {"customers": rows, "as_of": today(), "updated_at": now_datetime().isoformat()}


@frappe.whitelist(methods=["GET"])
def invoices(customer):
    frappe.only_for("System Manager")
    frappe.get_doc("Customer", customer).check_permission("read")
    rows = []
    for doctype in ("POS Invoice", "Sales Invoice"):
        records = frappe.get_list(doctype, filters=filters(doctype, customer),
            fields=["name", "posting_date", "due_date", "currency", "grand_total", "outstanding_amount",
                "contact_mobile"] + (["custom_k3ls_repair"] if doctype == "Sales Invoice" else []),
            order_by="due_date asc, posting_date asc", limit_page_length=0)
        for row in records:
            row.doctype = doctype
            row.kind = "Repair" if row.get("custom_k3ls_repair") else "Sale"
            row.overdue = bool(row.due_date and str(row.due_date) < today())
            rows.append(row)
    return sorted(rows, key=lambda row: (str(row.due_date or "9999"), row.name))


@frappe.whitelist(methods=["GET"])
def payment_options(doctype, name):
    doc = bill(doctype, name)
    profile = frappe.get_cached_doc("POS Profile", "K3LS Shop")
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_mode_of_payments_info
    modes = get_mode_of_payments_info([row.mode_of_payment for row in profile.payments], COMPANY)
    return {"amount": doc.outstanding_amount, "currency": doc.currency, "modified": str(doc.modified),
        "methods": list(modes), "can_collect": not doc.get("consolidated_invoice")}


def bill(doctype, name, write=False):
    frappe.only_for("System Manager")
    if doctype not in ("POS Invoice", "Sales Invoice"):
        frappe.throw("Choose a sale or repair invoice.")
    doc = frappe.get_doc(doctype, name, for_update=write)
    doc.check_permission("read")
    if write:
        doc.check_permission("write")
    if doc.company != COMPANY or doc.docstatus != 1 or doc.is_return:
        frappe.throw("Choose a confirmed K3LS customer invoice.")
    if flt(doc.outstanding_amount) <= 0:
        frappe.throw("This invoice is already paid.")
    return doc


@frappe.whitelist(methods=["POST"])
def prepare_payment(doctype, name, amount, mode, modified, expected_outstanding):
    if frappe.db.get_default("k3ls_operations_revision") == "20261004-9":
        frappe.throw("Record this payment in Money owed, then verify its evidence in Owner review.")
    # Read current values under the lock, not an older transaction snapshot.
    doc = bill(doctype, name, write=True)
    if str(doc.modified) != str(modified):
        frappe.throw("This invoice changed. Reopen the payment before recording it.")
    # Core POS collection updates the balance without changing modified.
    # Check the displayed balance under the lock to reject repeated requests.
    precision = doc.precision("outstanding_amount")
    expected = flt(expected_outstanding, precision)
    if not math.isfinite(expected) or expected != flt(doc.outstanding_amount, precision):
        frappe.throw("The balance changed. Reopen the payment before recording it.")
    amount = flt(amount, doc.precision("outstanding_amount"))
    if not math.isfinite(amount) or amount <= 0 or amount > flt(doc.outstanding_amount):
        frappe.throw("Enter an amount above 0, no more than the unpaid balance.")
    options = payment_options(doctype, name)
    if mode not in options["methods"]:
        frappe.throw("Choose a shop payment method.")
    if doc.currency != "NGN":
        frappe.throw("Use the invoice's payment form for other currencies.")
    if doctype == "POS Invoice":
        if doc.consolidated_invoice:
            frappe.throw("The till has closed. Take payment against its combined invoice.")
        # ERPNext's supported collection path updates the receipt and unpaid balance.
        doc.update_payments([{"mode_of_payment": mode, "amount": amount}])
        return {"recorded": True}
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
    account = get_bank_cash_account(mode, COMPANY)["account"]
    payment = get_payment_entry("Sales Invoice", name, bank_account=account, bank_amount=amount)
    if (payment.paid_from_account_currency != "NGN" or payment.paid_to_account_currency != "NGN"
            or payment.deductions or len(payment.references) != 1):
        frappe.throw("This invoice needs discounts, payment dates or currency matching. Use its payment form.")
    payment.mode_of_payment = mode
    payment.paid_amount = payment.received_amount = amount
    for row in payment.references:
        row.allocated_amount = amount
    payment.setup_party_account_field()
    payment.set_amounts()
    # Return an unsaved payment for review. Nothing is posted here.
    return {"payment": payment.as_dict(), "recorded": False}


def configure():
    frappe.only_for("System Manager")
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-money-owed", force=True)
    sidebar = frappe.get_doc("Workspace Sidebar", "K3LS Owner")
    if not any(row.label == "Money owed" for row in sidebar.items):
        sidebar.append("items", {"type": "Link", "label": "Money owed", "link_type": "Page",
            "link_to": "shop-money-owed", "icon": "hand-coins"})
    item = next(row for row in sidebar.items if row.label == "Money owed")
    sidebar.items.remove(item)
    sidebar.items.insert(1, item)
    sidebar.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"page": "shop-money-owed", "payments_posted": False}
