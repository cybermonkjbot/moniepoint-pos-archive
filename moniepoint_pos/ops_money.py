"""Verified receipts, payment plans and obligations over the ERPNext ledger."""
from decimal import Decimal
import hashlib

import frappe
from frappe.utils import getdate, now_datetime, today

from moniepoint_pos.operations import access, audit, owner
from moniepoint_pos.pricing import COMPANY, money


def company():
    return frappe.get_cached_doc("Company", COMPANY)


def party_account(kind, party):
    from erpnext.accounts.party import get_party_account
    return get_party_account(kind, party, COMPANY)


def bank(method):
    from moniepoint_pos.checkout import PAYMENT_METHODS
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
    if method not in PAYMENT_METHODS:
        frappe.throw("Choose a supported shop account.")
    account = get_bank_cash_account(method, COMPANY)["account"]
    if frappe.get_cached_value("Account", account, "account_currency") != "NGN":
        frappe.throw("Use an NGN shop account.")
    return account


def journal(rows, reference, opening=False, internal=False, posting_date=None):
    doc = frappe.get_doc(dict(doctype="Journal Entry", voucher_type="Journal Entry", company=COMPANY,
        posting_date=posting_date or today(), is_opening="Yes" if opening else "No", user_remark=reference, accounts=rows))
    if internal:
        doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=internal)
    doc.submit()
    return doc


def jrow(account, debit=0, credit=0, party_type=None, party=None, reference_type=None, reference_name=None):
    return dict(account=account, debit_in_account_currency=float(debit), credit_in_account_currency=float(credit),
        cost_center=company().cost_center, party_type=party_type, party=party,
        reference_type=reference_type, reference_name=reference_name)


def service_bill(supplier, amount, reference, posting_date=None):
    doc = frappe.get_doc(dict(doctype="Purchase Invoice", company=COMPANY, supplier=supplier, currency="NGN",
        posting_date=posting_date or today(), due_date=posting_date or today(), bill_no=reference, bill_date=posting_date or today(), update_stock=0,
        items=[dict(item_code="K3LS-REPAIR", qty=1, rate=amount, description=reference,
            expense_account=company().default_expense_account, cost_center=company().cost_center)], remarks=reference))
    doc.insert()
    doc.submit()
    return doc


def debt_outstanding(doc):
    if doc.status != "Posted":
        return float(doc.amount)
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_on_journal_entry
    party_type, party = ("Customer", doc.customer) if doc.direction == "Customer owes us" else ("Supplier", doc.supplier)
    outstanding, _ = get_outstanding_on_journal_entry(doc.journal, party_type, party)
    return abs(float(outstanding or 0))


def journal_due(name, supplier):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_on_journal_entry
    outstanding, _ = get_outstanding_on_journal_entry(name, "Supplier", supplier)
    return max(0, float(outstanding or 0))


def normalize_reference(values):
    """Close one POS sale before deferred collection so core owns every reversal.

    Payment plans use a real receivable invoice. Do not attach a per-sale plan to
    a later combined balance containing unrelated receipts.
    """
    if values.get("reference_type") != "POS Invoice":
        return values
    invoice = frappe.get_doc("POS Invoice", values.get("reference_name"), for_update=True)
    invoice.check_permission("read")
    if invoice.company != COMPANY or invoice.docstatus != 1 or invoice.is_return:
        frappe.throw("Choose a confirmed K3LS sale.")
    if not invoice.consolidated_invoice:
        access(True)
        merge = frappe.get_doc(dict(doctype="POS Invoice Merge Log", company=COMPANY, customer=invoice.customer,
            posting_date=today(), posting_time=frappe.utils.nowtime(), pos_invoices=[pos_reference(invoice)]))
        merge.insert()
        merge.submit()
        invoice.reload()
    if not invoice.consolidated_invoice:
        frappe.throw("The sale could not be closed. Reopen it before planning payment.")
    return dict(values, reference_type="Sales Invoice", reference_name=invoice.consolidated_invoice)


def pos_reference(invoice):
    return dict(pos_invoice=invoice.name, customer=invoice.customer, posting_date=invoice.posting_date,
        grand_total=invoice.grand_total, is_return=invoice.is_return, return_against=invoice.return_against)


def reserve_bank_reference(doc):
    """Serialize checks on the real account before reserving its unique reference."""
    if doc.method == "Cash":
        return
    account = bank(doc.method)
    frappe.get_doc("Account", account, for_update=True)
    key = hashlib.sha256(frappe.as_json([account, str(doc.bank_reference or "").strip().casefold()]).encode()).hexdigest()
    existing = frappe.db.get_value("K3LS Receipt", {"bank_key": key}, "name")
    if existing and existing != doc.name:
        frappe.throw("This bank reference is already recorded for this account.")
    # Older records may predate the unique identity field. Compare them under
    # the same account lock before reserving a new reference.
    for previous in frappe.get_all("K3LS Receipt", filters={"method": doc.method,
            "status": ["in", ["Verified", "Reversed"]], "name": ["!=", doc.name]}, fields=["bank_reference"]):
        if str(previous.bank_reference or "").strip().casefold() == str(doc.bank_reference or "").strip().casefold():
            frappe.throw("This bank reference is already recorded for this account.")
    doc.bank_key = key


def checkout_signature(sale):
    from moniepoint_pos.ops_cases import sale_signature
    return hashlib.sha256(frappe.as_json([sale.name, sale_signature(sale),
        [(row.name, row.mode_of_payment, format(Decimal(str(row.amount or 0)).normalize(), "f"))
            for row in sale.payments if row.amount]]).encode()).hexdigest()


@frappe.whitelist(methods=["GET"])
def checkout_status(invoice):
    access()
    sale = frappe.get_doc("POS Invoice", invoice)
    sale.check_permission("read")
    if sale.company != COMPANY or sale.docstatus != 0:
        frappe.throw("Choose a saved new sale.")
    signature = checkout_signature(sale)
    results = []
    for row in sale.payments:
        if row.mode_of_payment == "Cash" or row.amount <= 0:
            continue
        receipt = frappe.db.get_value("K3LS Receipt", {"checkout_sale": sale.name, "pos_payment": row.name,
            "checkout_signature": signature, "status": ["in", ["Pending", "Verified"]]}, ["name", "status"], as_dict=True)
        results.append(dict(payment=row.name, method=row.mode_of_payment, amount=row.amount,
            receipt=receipt.name if receipt else None, status=receipt.status if receipt else "Not checked"))
    return results


@frappe.whitelist(methods=["POST"])
def checkout_check(invoice, payment, bank_reference, evidence):
    access()
    sale = frappe.get_doc("POS Invoice", invoice, for_update=True)
    sale.check_permission("write")
    if sale.company != COMPANY or sale.docstatus != 0 or sale.is_return:
        frappe.throw("Save the new sale before checking its bank payment.")
    if not owner() and sale.owner != frappe.session.user:
        frappe.throw("Choose your own checkout.", frappe.PermissionError)
    row = next((line for line in sale.payments if line.name == payment), None)
    if not row or row.mode_of_payment == "Cash" or row.amount <= 0:
        frappe.throw("Choose a bank payment on this sale.")
    if not str(bank_reference or "").strip() or not evidence:
        frappe.throw("Add the bank reference and payment evidence.")
    signature = checkout_signature(sale)
    existing = frappe.db.get_value("K3LS Receipt", {"checkout_sale": sale.name, "pos_payment": row.name,
        "checkout_signature": signature, "status": ["in", ["Pending", "Verified"]]}, "name")
    if existing:
        return {"name": existing, "status": frappe.db.get_value("K3LS Receipt", existing, "status")}
    frappe.flags.k3ls_workflow = True
    receipt = frappe.get_doc(dict(doctype="K3LS Receipt", reference_type="POS Invoice", reference_name=sale.name,
        checkout_sale=sale.name, checkout_signature=signature, pos_payment=row.name, amount=row.amount,
        method=row.mode_of_payment, received_on=sale.posting_date, bank_reference=str(bank_reference).strip(),
        payer=sale.customer, evidence=evidence))
    receipt.insert()
    if owner():
        verify_receipt(receipt)
    return {"name": receipt.name, "status": receipt.status}


def validate_checkout(doc, method=None):
    if doc.company != COMPANY or doc.doctype != "POS Invoice" or doc.is_return or not frappe.db.get_default("k3ls_operations_revision"):
        return
    signature = checkout_signature(doc)
    for row in doc.payments:
        if row.mode_of_payment == "Cash" or row.amount <= 0:
            continue
        if not frappe.db.exists("K3LS Receipt", {"checkout_sale": doc.name, "pos_payment": row.name,
            "checkout_signature": signature, "amount": row.amount, "method": row.mode_of_payment, "status": "Verified"}):
            frappe.throw("Ask the owner to verify each bank payment before finishing this sale.")


def guard_payment_cancel(doc, method=None):
    if doc.company != COMPANY or not frappe.db.exists("DocType", "K3LS Receipt"):
        return
    receipts = frappe.db.sql("SELECT name FROM `tabK3LS Receipt` WHERE status='Verified' AND voucher_type=%s "
        "AND FIND_IN_SET(%s, voucher)>0", (doc.doctype, doc.name), as_dict=True)
    if any(row.name != frappe.flags.get("k3ls_reversing_receipt") for row in receipts):
        frappe.throw("Reverse this payment from Payments to check so its balance and instalment stay linked.")
    if doc.doctype == "Payment Entry" and frappe.db.exists("K3LS Return", {"refund_payment": doc.name, "status": "Done"}):
        frappe.throw("Keep the linked refund payment. Record its correction with the owner.")
    if doc.doctype == "Journal Entry" and (frappe.db.exists("K3LS Return", {"offset_journal": doc.name, "status": "Done"})
            or frappe.db.exists("K3LS Trade In", {"journal": doc.name, "status": "Done"})):
        frappe.throw("Keep the linked return or trade-in settlement. Record its correction with the owner.")


def guard_payment_submit(doc, method=None):
    if doc.company != COMPANY or not frappe.db.get_default("k3ls_operations_revision") or frappe.flags.get("k3ls_verifying_receipt"):
        return
    if doc.payment_type not in ("Pay", "Receive"):
        return
    if doc.references:
        frappe.throw("Record this collection or supplier payment in Payments to check, then verify its evidence.")


def guard_invoice_cancel(doc, method=None):
    if doc.company != COMPANY or not frappe.db.exists("DocType", "K3LS Return"):
        return
    if doc.get("custom_k3ls_return_case") and frappe.db.get_value("K3LS Return", doc.custom_k3ls_return_case, "status") == "Done":
        frappe.throw("This invoice belongs to a completed return. Its stock, refund and settlement must be corrected together.")
    if frappe.db.exists("K3LS Return", {"invoice_type": doc.doctype, "invoice": doc.name, "status": "Done"}):
        frappe.throw("This sale has completed returns. Keep the original sale and its linked credits.")


def balance(reference_type, reference_name, write=False):
    if reference_type not in ("POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Debt", "K3LS Owner Stock", "K3LS Delivery", "K3LS Shop Request"):
        frappe.throw("Choose a supported balance record.")
    doc = frappe.get_doc(reference_type, reference_name, for_update=write)
    doc.check_permission("read")
    if reference_type in ("POS Invoice", "Sales Invoice", "Purchase Invoice"):
        if doc.company != COMPANY or doc.docstatus != 1 or doc.is_return:
            frappe.throw("Choose a confirmed K3LS sale or restock bill.")
        if reference_type == "POS Invoice" and doc.consolidated_invoice:
            # Core maintains collections against the combined invoice after close.
            return dict(type="Sales Invoice", name=doc.consolidated_invoice, original=doc.name, merged=True,
                **{key: value for key, value in balance("Sales Invoice", doc.consolidated_invoice, write).items() if key not in ("type", "name")})
        return dict(type=reference_type, name=doc.name, amount=float(doc.outstanding_amount), total=float(doc.grand_total),
            party=doc.get("supplier") or doc.customer, direction="Pay" if reference_type == "Purchase Invoice" else "Receive",
            due_date=str(doc.due_date) if doc.due_date else None, modified=str(doc.modified), currency=doc.currency)
    if reference_type == "K3LS Debt":
        if doc.status != "Posted":
            frappe.throw("Post this opening debt before taking payment.")
        return dict(type=reference_type, name=doc.name, amount=debt_outstanding(doc), total=float(doc.amount), party=doc.customer or doc.supplier,
            direction="Receive" if doc.direction == "Customer owes us" else "Pay", due_date=str(doc.due_date), currency="NGN")
    if reference_type == "K3LS Owner Stock":
        amounts = [(row, journal_due(row.journal, doc.supplier)) for row in frappe.get_all("K3LS Owner Sale",
            filters={"owner_stock": doc.name, "status": "Posted", "amount": [">", 0]}, fields=["journal", "due_date"])]
        amount = sum(value for row, value in amounts)
        due = min((str(row.due_date or doc.due_date) for row, value in amounts if value and (row.due_date or doc.due_date)), default=None)
        return dict(type=reference_type, name=doc.name, amount=amount,
            total=float(doc.amount_due or 0), party=doc.supplier, direction="Pay", due_date=due, currency="NGN")
    if reference_type == "K3LS Delivery":
        if not doc.invoice:
            frappe.throw("Confirm the delivery charge first.")
        return balance("Sales Invoice", doc.invoice, write)
    if doc.request_type != "Expense" or doc.status != "Done" or not doc.expense_journal:
        frappe.throw("Record the approved expense before reimbursement.")
    paid = sum(float(row.amount) for row in frappe.get_all("K3LS Receipt", filters={"reference_type": reference_type,
        "reference_name": doc.name, "status": "Verified"}, fields=["amount"]))
    return dict(type=reference_type, name=doc.name, amount=max(0, float(doc.amount) - paid), total=float(doc.amount),
        party=doc.paid_by, direction="Pay", due_date=today(), currency="NGN")


def validate(doc, old=None):
    if doc.doctype == "K3LS Debt":
        doc.amount = float(money(doc.amount, "Original amount"))
        if not doc.amount:
            frappe.throw("The original amount must be above zero.")
        if (doc.direction == "Customer owes us" and (not doc.customer or doc.supplier)) or (doc.direction == "We owe supplier" and (not doc.supplier or doc.customer)):
            frappe.throw("Choose only the customer or supplier for this balance.")
        if getdate(doc.incurred_on) > getdate(today()):
            frappe.throw("The original debt date cannot be in the future.")
    elif doc.doctype == "K3LS Instalment Plan":
        if old and (doc.reference_type, doc.reference_name) != (old.reference_type, old.reference_name):
            frappe.throw("Keep the original balance linked to this payment plan.")
        target = balance(doc.reference_type, doc.reference_name, write=True)
        if target.get("merged") and not old:
            frappe.throw("Use the combined sale invoice shown in Money owed after the till closes.")
        if doc.is_new() and frappe.db.exists(doc.doctype, {"reference_type": doc.reference_type, "reference_name": doc.reference_name, "status": "Active"}):
            frappe.throw("This balance already has an active payment plan.")
        previous = {row.name: row for row in old.instalments} if old else {}
        old_names = set(previous)
        retained = set()
        for row in doc.instalments:
            row.amount = float(money(row.amount, "Instalment amount"))
            if not row.amount:
                frappe.throw("Each instalment needs an amount above zero.")
            if row.name in previous:
                retained.add(row.name)
                earlier = previous[row.name]
                if str(row.due_date) != str(earlier.due_date) or row.amount != earlier.amount:
                    frappe.throw("Keep the original amount and date. Use a revised promise date instead.")
                if not frappe.flags.get("k3ls_receipt_allocation"):
                    row.paid = earlier.paid
        if old_names - retained:
            frappe.throw("Keep the original instalments in the payment history.")
        planned = sum(Decimal(str(row.amount)) - Decimal(str(row.paid or 0)) for row in doc.instalments)
        if planned > Decimal(str(target["amount"])) and not frappe.flags.get("k3ls_receipt_allocation"):
            frappe.throw("The unpaid instalments cannot exceed the unpaid balance.")
    elif doc.doctype == "K3LS Receipt":
        if old and any(doc.get(key) != old.get(key) for key in ("reference_type", "reference_name", "amount", "method", "received_on", "bank_reference", "plan", "instalment")):
            frappe.throw("Keep the payment details unchanged. Reject this receipt and add a replacement.")
        doc.amount = float(money(doc.amount, "Payment amount"))
        if not doc.amount:
            frappe.throw("Enter a payment above zero.")
        bank(doc.method) if owner() else None
        if getdate(doc.received_on) > getdate(today()):
            frappe.throw("Payment date cannot be in the future.")
        if not old and not doc.checkout_sale:
            # Read permission protects direct submissions to someone else's balance.
            target = balance(doc.reference_type, doc.reference_name)
            if target.get("merged"):
                frappe.throw("Use the combined invoice in Money owed for this payment.")
            if doc.amount > target["amount"]:
                frappe.throw("Payment is more than the unpaid balance.")
        if not owner() and doc.reference_type not in ("POS Invoice", "Sales Invoice"):
            frappe.throw("Only the owner can record supplier, expense and stock-owner payments.", frappe.PermissionError)
        if doc.plan:
            plan = frappe.get_doc("K3LS Instalment Plan", doc.plan)
            if plan.reference_type != doc.reference_type or plan.reference_name != doc.reference_name:
                frappe.throw("Choose the plan for this same balance record.")
            if not any(row.name == doc.instalment for row in plan.instalments):
                frappe.throw("Choose an instalment from this plan.")
    elif doc.doctype == "K3LS Account Check":
        if old and old.status == "Reviewed" and (doc.actual_balance != old.actual_balance or doc.checked_on != old.checked_on or doc.account != old.account or doc.check_type != old.check_type):
            frappe.throw("Keep the reviewed balance. Add a new account check.")
        if getdate(doc.checked_on) > getdate(today()):
            frappe.throw("Use today or an earlier review date.")
        from moniepoint_pos.accounts import visible_accounts
        if doc.account not in visible_accounts():
            frappe.throw("Choose a shop cash or bank account.")
        actual = Decimal(str(doc.actual_balance or 0))
        if not actual.is_finite():
            frappe.throw("Enter a valid actual balance.")
        ledger = frappe.get_list("GL Entry", filters={"company": COMPANY, "account": doc.account, "is_cancelled": 0,
            "posting_date": ["<=", doc.checked_on]}, fields=[{"SUM": "debit_in_account_currency", "as": "debit"},
            {"SUM": "credit_in_account_currency", "as": "credit"}], order_by=None)
        if not frappe.has_permission("GL Entry", "read"):
            frappe.throw("Account review needs ledger access.", frappe.PermissionError)
        if not old:
            doc.expected_balance = float((ledger[0].debit or 0) - (ledger[0].credit or 0)) if ledger else 0
        else:
            doc.expected_balance = old.expected_balance
        doc.difference = float(actual) - doc.expected_balance


def payment_entry(reference_type, reference_name, amount, method, receipt):
    if reference_type == "Journal Entry":
        source = frappe.get_doc("Journal Entry", reference_name)
        source.check_permission("read")
        parties = [row for row in source.accounts if row.party_type in ("Customer", "Supplier") and row.party]
        if len(parties) != 1:
            frappe.throw("Choose an obligation journal with one customer or supplier balance.")
        line = parties[0]
        receive = line.party_type == "Customer"
        account = bank(method)
        payment = frappe.get_doc(dict(doctype="Payment Entry", company=COMPANY, payment_type="Receive" if receive else "Pay",
            party_type=line.party_type, party=line.party, paid_from=line.account if receive else account,
            paid_to=account if receive else line.account, paid_amount=amount, received_amount=amount,
            paid_from_account_currency="NGN", paid_to_account_currency="NGN", source_exchange_rate=1, target_exchange_rate=1,
            references=[dict(reference_doctype="Journal Entry", reference_name=source.name, total_amount=abs(line.debit_in_account_currency or line.credit_in_account_currency), allocated_amount=amount)],
            cost_center=company().cost_center))
    else:
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
        payment = get_payment_entry(reference_type, reference_name, bank_account=bank(method), bank_amount=amount)
    if payment.paid_from_account_currency != "NGN" or payment.paid_to_account_currency != "NGN" or payment.deductions:
        frappe.throw("This payment needs the original accounting form for currencies or deductions.")
    payment.mode_of_payment = method
    payment.reference_no, payment.reference_date = receipt.bank_reference, receipt.received_on
    payment.posting_date = receipt.received_on
    payment.paid_amount = payment.received_amount = amount
    if len(payment.references) != 1:
        frappe.throw("Review this payment in its original accounting form.")
    payment.references[0].allocated_amount = amount
    payment.setup_party_account_field()
    payment.set_amounts()
    payment.insert()
    frappe.flags.k3ls_verifying_receipt = receipt.name
    try:
        payment.submit()
    finally:
        frappe.flags.k3ls_verifying_receipt = None
    return payment


def verify_receipt(doc):
    if doc.status != "Pending" or doc.reversal_of:
        frappe.throw("Choose an unverified payment without a reversal link.")
    if not doc.evidence:
        frappe.throw("Attach the payment evidence before verification.")
    reserve_bank_reference(doc)
    if doc.checkout_sale:
        sale = frappe.get_doc("POS Invoice", doc.checkout_sale, for_update=True)
        sale.check_permission("read")
        if sale.docstatus != 0 or sale.company != COMPANY or doc.checkout_signature != checkout_signature(sale):
            frappe.throw("The checkout changed. Reject this payment check and request a new one.")
        if not any(row.name == doc.pos_payment and row.mode_of_payment == doc.method and float(row.amount) == float(doc.amount) for row in sale.payments):
            frappe.throw("This bank payment no longer matches the checkout.")
        doc.status, doc.verified_by, doc.verified_at = "Verified", frappe.session.user, now_datetime()
        doc.save()
        return
    target = balance(doc.reference_type, doc.reference_name, write=True)
    if target.get("merged"):
        frappe.throw("The till closed. Reject this pending receipt and record it against the combined invoice.")
    if doc.amount > target["amount"] or target["currency"] != "NGN":
        frappe.throw("The unpaid balance changed or uses another currency. Reopen it before payment.")
    if doc.plan:
        plan = frappe.get_doc("K3LS Instalment Plan", doc.plan, for_update=True)
        instalment = next((row for row in plan.instalments if row.name == doc.instalment), None)
        if not instalment or doc.amount > instalment.amount - (instalment.paid or 0):
            frappe.throw("This instalment balance changed. Reopen the payment plan.")
    elif frappe.db.exists("K3LS Instalment Plan", {"reference_type": doc.reference_type, "reference_name": doc.reference_name, "status": "Active"}):
        frappe.throw("Record this payment from the active plan and choose its instalment.")
    if doc.reference_type == "POS Invoice":
        frappe.throw("Recreate this pending receipt from Money owed to use the accounting collection flow.")
    elif target["type"] in ("Sales Invoice", "Purchase Invoice"):
        payment = payment_entry(target["type"], target["name"], doc.amount, doc.method, doc)
        doc.voucher_type, doc.voucher = "Payment Entry", payment.name
    elif doc.reference_type == "K3LS Owner Stock":
        agreement = frappe.get_doc("K3LS Owner Stock", doc.reference_name, for_update=True)
        # Allocate against the owner's original accrual journals, not unallocated supplier advances.
        allocations = frappe.get_all("K3LS Owner Sale", filters={"owner_stock": agreement.name, "status": "Posted"},
            fields=["name", "journal", "amount", "paid"], order_by="creation asc")
        left, references = Decimal(str(doc.amount)), []
        for row in allocations:
            if left <= 0:
                break
            sale = frappe.get_doc("K3LS Owner Sale", row.name, for_update=True)
            available = Decimal(str(journal_due(sale.journal, agreement.supplier))) if sale.amount > 0 else Decimal(0)
            part = min(left, available)
            if part <= 0:
                continue
            payment = payment_entry("Journal Entry", sale.journal, float(part), doc.method, doc)
            sale.paid = float(Decimal(str(sale.paid or 0)) + part)
            sale.flags.k3ls_operation = True
            sale.save()
            references.append(payment.name)
            left -= part
        if left:
            frappe.throw("Resolve the owner's settlement journals before paying this balance.")
        agreement.amount_paid = float(Decimal(str(agreement.amount_paid or 0)) + Decimal(str(doc.amount)))
        agreement.flags.k3ls_operation = True
        agreement.save()
        doc.voucher_type, doc.voucher = "Payment Entry", ",".join(references)
    else:
        source = frappe.get_doc(doc.reference_type, doc.reference_name)
        if source.doctype == "K3LS Debt":
            payment = payment_entry("Journal Entry", source.journal, doc.amount, doc.method, doc)
            doc.voucher_type, doc.voucher = "Payment Entry", payment.name
        else:
            payment = journal([jrow(source.payable_account, debit=doc.amount), jrow(bank(doc.method), credit=doc.amount)],
                "Reimbursement " + doc.name, posting_date=doc.received_on)
            doc.voucher_type, doc.voucher = "Journal Entry", payment.name
    if doc.plan:
        instalment.paid = float(Decimal(str(instalment.paid or 0)) + Decimal(str(doc.amount)))
        plan.flags.k3ls_operation = True
        frappe.flags.k3ls_receipt_allocation = True
        try:
            plan.save()
        finally:
            frappe.flags.k3ls_receipt_allocation = False
    doc.status, doc.verified_by, doc.verified_at = "Verified", frappe.session.user, now_datetime()
    doc.save()


def plan_summary(doc):
    target = balance(doc.reference_type, doc.reference_name)
    scheduled = sum(float(row.amount) - float(row.paid or 0) for row in doc.instalments)
    return dict(balance=target, unscheduled=max(0, target["amount"] - scheduled), overdue=[row.name for row in doc.instalments
        if getdate(row.promise_date or row.due_date) < getdate(today()) and row.amount > (row.paid or 0)],
        next_due=min((str(row.promise_date or row.due_date) for row in doc.instalments if row.amount > (row.paid or 0)), default=None))


def perform(doc, action, values):
    access(True)
    if action == "post" and doc.doctype == "K3LS Debt":
        if doc.status != "Approved" or not doc.evidence:
            frappe.throw("Approve this debt and attach its original evidence first.")
        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
        opening = get_difference_account("Opening Stock", COMPANY)
        if not opening:
            frappe.throw("Configure the opening balance account first.")
        receive = doc.direction == "Customer owes us"
        party_type, party = ("Customer", doc.customer) if receive else ("Supplier", doc.supplier)
        amount = doc.amount
        rows = [jrow(party_account(party_type, party), debit=amount if receive else 0, credit=0 if receive else amount, party_type=party_type, party=party),
                jrow(opening, debit=0 if receive else amount, credit=amount if receive else 0)]
        doc.journal = journal(rows, "Opening obligation " + doc.name, opening=True, posting_date=doc.incurred_on).name
        doc.status = "Posted"
        doc.save()
    elif action == "verify" and doc.doctype == "K3LS Receipt":
        verify_receipt(doc)
    elif action == "reject" and doc.doctype == "K3LS Receipt":
        if doc.status != "Pending" or not values.get("reason"):
            frappe.throw("Choose a pending receipt and add the rejection reason.")
        doc.status, doc.notes = "Rejected", values["reason"]
        doc.save()
    elif action == "reverse" and doc.doctype == "K3LS Receipt":
        if doc.status != "Verified" or not values.get("reason"):
            frappe.throw("Choose a verified receipt and add a reversal reason.")
        if doc.checkout_sale:
            sale = frappe.get_doc("POS Invoice", doc.checkout_sale, for_update=True)
            if sale.docstatus == 1:
                frappe.throw("Return or cancel the sale before reversing its checkout payment check.")
        elif doc.voucher_type == "POS Invoice":
            frappe.throw("Use the original till accounting flow for this legacy receipt. New receipts use reversible accounting payments.")
        else:
            frappe.flags.k3ls_reversing_receipt = doc.name
            for name in doc.voucher.split(","):
                voucher = frappe.get_doc(doc.voucher_type, name, for_update=True)
                voucher.check_permission("cancel")
                voucher.cancel()
        if doc.reference_type == "K3LS Owner Stock":
            agreement = frappe.get_doc("K3LS Owner Stock", doc.reference_name, for_update=True)
            agreement.amount_paid -= doc.amount
            agreement.flags.k3ls_operation = True
            agreement.save()
            # The payment documents retain exact journal allocations.
            for name in doc.voucher.split(","):
                payment = frappe.get_doc("Payment Entry", name)
                for ref in payment.references:
                    sale_name = frappe.db.get_value("K3LS Owner Sale", {"journal": ref.reference_name}, "name")
                    if sale_name:
                        sale = frappe.get_doc("K3LS Owner Sale", sale_name, for_update=True)
                        sale.paid -= ref.allocated_amount
                        sale.flags.k3ls_operation = True
                        sale.save()
        if doc.plan:
            plan = frappe.get_doc("K3LS Instalment Plan", doc.plan, for_update=True)
            row = next(row for row in plan.instalments if row.name == doc.instalment)
            row.paid -= doc.amount
            plan.flags.k3ls_operation = True
            frappe.flags.k3ls_receipt_allocation = True
            try:
                plan.save()
            finally:
                frappe.flags.k3ls_receipt_allocation = False
        doc.status, doc.notes = "Reversed", values["reason"]
        doc.save()
    elif action == "matched" and doc.doctype == "K3LS Receipt":
        if doc.status != "Verified":
            frappe.throw("Verify this receipt first.")
        doc.matched_on = values.get("date") or today()
        if getdate(doc.matched_on) < getdate(doc.received_on) or getdate(doc.matched_on) > getdate(today()):
            frappe.throw("Choose a bank-match date between the payment date and today.")
        doc.save()
    elif action == "reviewed" and doc.doctype == "K3LS Account Check":
        if doc.status != "Open":
            frappe.throw("This account check is already reviewed.")
        if doc.difference and not doc.notes:
            frappe.throw("Add a reason for the balance difference.")
        if doc.check_type == "Opening balance":
            if not doc.evidence or not doc.notes:
                frappe.throw("Attach the opening statement or cash count and add its source.")
            frappe.get_doc("Account", doc.account, for_update=True)
            if frappe.db.exists("GL Entry", {"company": COMPANY, "account": doc.account, "is_cancelled": 0}):
                frappe.throw("This account already has transactions. Use a balance check instead of replacing its opening balance.")
            from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
            opening = get_difference_account("Opening Stock", COMPANY)
            if not opening:
                frappe.throw("Configure the opening balance account first.")
            if doc.actual_balance:
                amount = Decimal(str(doc.actual_balance))
                voucher = frappe.get_doc(dict(doctype="Journal Entry", voucher_type="Journal Entry", company=COMPANY,
                    posting_date=doc.checked_on, is_opening="Yes", user_remark="Opening account balance " + doc.name,
                    accounts=[jrow(doc.account, debit=max(0, amount), credit=max(0, -amount)),
                        jrow(opening, debit=max(0, -amount), credit=max(0, amount))]))
                voucher.insert()
                voucher.submit()
                doc.opening_journal = voucher.name
        doc.status = "Reviewed"
        doc.save()
    elif action == "contact" and doc.doctype == "K3LS Instalment Plan":
        doc.last_contacted, doc.next_follow_up, doc.contact_notes = today(), values.get("next_follow_up"), values.get("notes")
        if values.get("instalment"):
            row = next((r for r in doc.instalments if r.name == values["instalment"]), None)
            if not row:
                frappe.throw("Choose an instalment in this plan.")
            row.promise_date = values.get("promise_date")
        doc.save()
    elif action == "close" and doc.doctype == "K3LS Instalment Plan":
        if balance(doc.reference_type, doc.reference_name)["amount"]:
            frappe.throw("Finish payment before closing this plan.")
        doc.status = "Closed"
        doc.save()
    else:
        frappe.throw("Choose a supported money action.")
    audit(doc, action, reason=values.get("reason"))


@frappe.whitelist(methods=["GET"])
def overview():
    access(True)
    rows = []
    for name in ("POS Invoice", "Sales Invoice", "Purchase Invoice"):
        filters = dict(company=COMPANY, docstatus=1, is_return=0, outstanding_amount=[">", 0])
        if name == "POS Invoice":
            filters["consolidated_invoice"] = ["is", "not set"]
        for record in frappe.get_list(name, filters=filters, fields=["name", "due_date", "outstanding_amount", "currency", "supplier" if name == "Purchase Invoice" else "customer"], limit_page_length=0):
            rows.append(dict(type=name, name=record.name, party=record.get("supplier") or record.customer, amount=float(record.outstanding_amount),
                due_date=str(record.due_date) if record.due_date else None, direction="Pay" if name == "Purchase Invoice" else "Receive", currency=record.currency))
    for name in ("K3LS Debt", "K3LS Owner Stock"):
        for record in frappe.get_list(name, filters={"status": "Posted"} if name == "K3LS Debt" else {}, fields=["name"], limit_page_length=0):
            target = balance(name, record.name)
            if target["amount"]:
                rows.append(target)
    for record in frappe.get_list("K3LS Shop Request", filters={"status": "Done", "request_type": "Expense"}, fields=["name"], limit_page_length=0):
        target = balance("K3LS Shop Request", record.name)
        if target["amount"]:
            rows.append(target)
    plans = {(row.reference_type, row.reference_name): row.name for row in frappe.get_list("K3LS Instalment Plan", filters={"status": "Active"}, fields=["name", "reference_type", "reference_name"], limit_page_length=0)}
    scheduled = {}
    if plans:
        for payment in frappe.get_all("K3LS Instalment", filters={"parent": ["in", list(plans.values())]}, fields=["parent", "amount", "paid"]):
            scheduled[payment.parent] = scheduled.get(payment.parent, Decimal(0)) + Decimal(str(payment.amount or 0)) - Decimal(str(payment.paid or 0))
    for row in rows:
        row["overdue"] = bool(row["due_date"] and getdate(row["due_date"]) < getdate(today()))
        row["plan"] = plans.get((row["type"], row["name"]))
        row["unplanned_amount"] = max(0, float(Decimal(str(row["amount"])) - scheduled.get(row["plan"], Decimal(0))))
    return dict(rows=rows, totals={direction: sum(row["amount"] for row in rows if row["direction"] == direction and row["currency"] == "NGN") for direction in ("Pay", "Receive")}, as_of=today())


def owner_sale(doc, method=None):
    """Accrue once on the original sale, never on its POS consolidation."""
    if doc.company != COMPANY or doc.get("is_consolidated") or not frappe.db.exists("DocType", "K3LS Owner Sale"):
        return
    frappe.flags.k3ls_workflow = True
    totals = {}
    for row in doc.items:
        if row.get("custom_k3ls_owner_stock"):
            key = row.custom_k3ls_owner_stock
            totals[key] = totals.get(key, Decimal(0)) + Decimal(str(row.stock_qty)) * Decimal(str(row.custom_k3ls_owner_due))
    for name, amount in sorted(totals.items()):
        if not amount:
            continue
        key = hashlib.sha256(frappe.as_json([doc.doctype, doc.name, name]).encode()).hexdigest()
        if frappe.db.exists("K3LS Owner Sale", {"sale_key": key}):
            continue
        agreement = frappe.get_doc("K3LS Owner Stock", name, for_update=True)
        if amount < 0:
            if agreement.amount_due + float(amount) < agreement.amount_paid:
                frappe.throw("Reverse owner payouts before returning these products.")
        # Triggered by a permitted POS submit. Do not require cashier access to
        # confidential payable accounts, nor accept an account from the client.
        account = frappe.db.get_value("Party Account", {"parenttype": "Supplier", "parent": agreement.supplier, "company": COMPANY}, "account") or company().default_payable_account
        cost = company().default_expense_account
        rows = [jrow(cost, debit=max(0, amount), credit=max(0, -amount))]
        if amount >= 0:
            rows.append(jrow(account, credit=amount, party_type="Supplier", party=agreement.supplier))
        else:
            # A return offsets the exact original unpaid supplier accrual.
            left = -amount
            original_sales = frappe.get_all("K3LS Owner Sale", filters={"invoice_type": doc.doctype, "invoice": doc.return_against,
                "owner_stock": name, "status": "Posted"}, fields=["journal", "amount", "paid"])
            for original in original_sales:
                chunk = min(left, Decimal(str(journal_due(original.journal, agreement.supplier)))) if original.amount > 0 else Decimal(0)
                if chunk > 0:
                    rows.append(jrow(account, debit=chunk, party_type="Supplier", party=agreement.supplier,
                        reference_type="Journal Entry", reference_name=original.journal))
                    left -= chunk
            if left:
                frappe.throw("Reverse owner payouts before this product return.")
        voucher = journal(rows,
            "Owner stock sale " + key, internal=True)
        line = frappe.get_doc(dict(doctype="K3LS Owner Sale", owner_stock=name, invoice_type=doc.doctype, invoice=doc.name,
            amount=float(amount), paid=0, journal=voucher.name, sale_key=key, status="Posted",
            due_date=next((row.get("custom_k3ls_owner_due_date") for row in doc.items if row.get("custom_k3ls_owner_stock") == name), agreement.due_date)))
        line.flags.k3ls_operation = True
        line.insert(ignore_permissions=True)
        agreement.flags.k3ls_operation = True
        agreement.flags.ignore_permissions = True
        agreement.amount_due = float(Decimal(str(agreement.amount_due or 0)) + amount)
        agreement.save(ignore_permissions=True)


def cancel_owner_sale(doc, method=None):
    if doc.company != COMPANY or doc.get("is_consolidated") or not frappe.db.exists("DocType", "K3LS Owner Sale"):
        return
    frappe.flags.k3ls_workflow = True
    for row in frappe.get_all("K3LS Owner Sale", filters={"invoice_type": doc.doctype, "invoice": doc.name, "status": "Posted"}, fields=["name"]):
        line = frappe.get_doc("K3LS Owner Sale", row.name, for_update=True)
        agreement = frappe.get_doc("K3LS Owner Stock", line.owner_stock, for_update=True)
        if line.paid or (line.amount > 0 and round(journal_due(line.journal, agreement.supplier), 2) != round(line.amount, 2)):
            frappe.throw("Reverse owner payments before cancelling this sale.")
        voucher = frappe.get_doc("Journal Entry", line.journal)
        voucher.flags.ignore_permissions = True
        voucher.cancel()
        agreement = frappe.get_doc("K3LS Owner Stock", line.owner_stock, for_update=True)
        agreement.amount_due -= line.amount
        agreement.flags.k3ls_operation = True
        agreement.save(ignore_permissions=True)
        line.status = "Cancelled"
        line.flags.k3ls_operation = True
        line.save(ignore_permissions=True)
