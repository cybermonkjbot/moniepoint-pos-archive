"""Approved returns, exchanges, trade-ins, expenses and deliveries."""
from decimal import Decimal

import frappe
from frappe.utils import getdate, now_datetime, today

from moniepoint_pos.operations import access, audit
from moniepoint_pos.pricing import COMPANY, money
from moniepoint_pos.products import piece_count
from moniepoint_pos.ops_money import company, jrow, journal, party_account, service_bill


def sale_signature(sale):
    # The approval covers these exact prices, quantities, customer and credit terms.
    def number(value):
        return format(Decimal(str(value or 0)).normalize(), "f")
    return frappe.as_json([sale.customer, sale.contact_mobile, str(sale.due_date), sale.currency,
        number(sale.grand_total), number(sale.paid_amount), [(row.item_code, number(row.qty), number(row.rate), number(row.discount_percentage),
        row.get("serial_no"), row.get("serial_and_batch_bundle")) for row in sale.items]])


def validate(doc, old=None):
    if doc.doctype == "K3LS Shop Request":
        doc.amount = float(money(doc.amount or 0, "Amount"))
        if doc.item:
            frappe.get_doc("Item", doc.item).check_permission("read")
        if doc.related_doctype or doc.related_name:
            allowed = {"Item", "Customer", "Supplier", "POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Repair"}
            if doc.related_doctype not in allowed or not doc.related_name:
                frappe.throw("Choose an existing shop product, contact, sale, restock or repair record.")
            source = frappe.get_doc(doc.related_doctype, doc.related_name)
            source.check_permission("read")
            if source.get("company") and source.company != COMPANY:
                frappe.throw("Choose a K3LS record.")
    elif doc.doctype == "K3LS Return":
        invoice = frappe.get_doc(doc.invoice_type, doc.invoice)
        invoice.check_permission("read")
        if invoice.company != COMPANY or invoice.docstatus != 1 or invoice.is_return:
            frappe.throw("Choose the confirmed original K3LS sale.")
        doc.quantity = piece_count(doc.quantity)
        lines = [row for row in invoice.items if row.item_code == doc.item]
        selected = next((row for row in lines if row.name == doc.sale_line), None)
        if invoice.get("is_consolidated"):
            if not selected or not selected.get("pos_invoice") or not selected.get("pos_invoice_item"):
                frappe.throw("Choose the original till sale for this returned product.")
            doc.invoice_type, doc.invoice, doc.sale_line = "POS Invoice", selected.pos_invoice, selected.pos_invoice_item
            invoice = frappe.get_doc("POS Invoice", doc.invoice)
            invoice.check_permission("read")
            selected = next((row for row in invoice.items if row.name == doc.sale_line and row.item_code == doc.item), None)
        if not selected or not doc.quantity or doc.quantity > selected.qty:
            frappe.throw("Return only products and quantities on the original sale.")
        item = frappe.get_cached_doc("Item", doc.item)
        if item.has_serial_no:
            from moniepoint_pos.ops_stock import serials
            returned = serials(doc.serials, doc.quantity, item).splitlines()
            sold = {number.strip() for number in str(selected.serial_no or "").splitlines() if number.strip()}
            if selected.serial_and_batch_bundle:
                bundle = frappe.get_doc("Serial and Batch Bundle", selected.serial_and_batch_bundle)
                if bundle.item_code != item.name:
                    frappe.throw("The original serial records do not match this product.")
                sold = {entry.serial_no for entry in bundle.entries if entry.serial_no}
            if not set(returned).issubset(sold):
                frappe.throw("Return only the serial numbers on this original sale line.")
    elif doc.doctype == "K3LS Trade In":
        doc.credit = float(money(doc.credit, "Trade-in value"))
        invoice = frappe.get_doc(doc.invoice_type, doc.invoice)
        invoice.check_permission("read")
        if invoice.company != COMPANY or invoice.customer != doc.customer or invoice.is_return:
            frappe.throw("Use a K3LS sale for this customer.")
        intake = frappe.get_doc("K3LS Stock Intake", doc.intake)
        if intake.ownership != "K3LS Owned" or intake.source_type != "Trade-in":
            frappe.throw("Choose a shop-owned Trade-in stock intake.")
        if doc.credit <= 0:
            frappe.throw("Add a trade-in value above zero.")
    elif doc.doctype == "K3LS Delivery":
        for key in ("fee", "rider_cost", "other_cost"):
            doc.set(key, float(money(doc.get(key) or 0, key.replace("_", " "))))
        frappe.get_doc("Customer", doc.customer).check_permission("read")
    elif doc.doctype == "K3LS Access Review":
        user = frappe.get_doc("User", doc.user)
        user.check_permission("read")
        if old and old.user != doc.user:
            frappe.throw("Keep the original person linked to this access review.")
        doc.access_before = old.access_before if old else access_snapshot(user)
        if getdate(doc.reviewed_on) > getdate(today()):
            frappe.throw("The access review date cannot be in the future.")


def process_return(doc, values):
    source = frappe.get_doc(doc.invoice_type, doc.invoice, for_update=True)
    if doc.decision == "Repair":
        repair = frappe.get_doc(dict(doctype="K3LS Repair", customer=source.customer,
            customer_phone=source.contact_mobile, customer_address=source.address_display or "",
            device=frappe.get_cached_value("Item", doc.item, "item_name"), item=doc.item,
            serial_no=doc.serials, fault_reported=doc.reason, arrival_condition=doc.condition,
            relationship="Returning", received_at=now_datetime(), status="Received"))
        repair.insert()
        doc.repair, doc.status = repair.name, "Done"
        doc.save()
        return
    if doc.decision == "Reject":
        doc.status, doc.review_notes = "Rejected", values.get("reason") or doc.reason
        doc.save()
        return
    from moniepoint_pos.ops_money import bank, normalize_reference, pos_reference
    account = bank(values.get("method"))
    if doc.invoice_type == "POS Invoice":
        normalized = normalize_reference(dict(reference_type="POS Invoice", reference_name=source.name))
        accounting_source = frappe.get_doc("Sales Invoice", normalized["reference_name"], for_update=True)
        source.reload()
    else:
        accounting_source = source
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    credit = make_return_doc(doc.invoice_type, source.name)
    line_field = "pos_invoice_item" if doc.invoice_type == "POS Invoice" else "sales_invoice_item"
    candidates = [row for row in credit.items if row.item_code == doc.item and row.get(line_field) == doc.sale_line]
    if len(candidates) != 1:
        frappe.throw("Choose the exact original sale line in the return form for this repeated product.")
    original_line = candidates[0]
    if doc.quantity > abs(original_line.qty):
        frappe.throw("Some of these pieces were already returned.")
    original_line.qty = -doc.quantity
    original_line.stock_qty = -doc.quantity * (original_line.conversion_factor or 1)
    if doc.serials:
        original_line.serial_no = doc.serials
        original_line.use_serial_batch_fields = 1
    credit.set("items", [original_line])
    credit.custom_k3ls_return_case = doc.name
    if doc.invoice_type == "Sales Invoice":
        credit.update_outstanding_for_self = 1
        credit.is_pos = 0
    credit.set("payments", [])
    credit.paid_amount = credit.base_paid_amount = 0
    credit.change_amount = credit.base_change_amount = 0
    credit.run_method("calculate_taxes_and_totals")
    credit.insert()
    credit.submit()
    credit.reload()
    if doc.invoice_type == "POS Invoice":
        if not credit.consolidated_invoice:
            merge = frappe.get_doc(dict(doctype="POS Invoice Merge Log", company=COMPANY, customer=credit.customer,
                posting_date=today(), posting_time=frappe.utils.nowtime(), pos_invoices=[pos_reference(credit)]))
            merge.insert()
            merge.submit()
            doc.merge_log = merge.name
            credit.reload()
        if not credit.consolidated_invoice:
            frappe.throw("The return could not be linked to its accounting credit.")
        accounting_credit = frappe.get_doc("Sales Invoice", credit.consolidated_invoice, for_update=True)
    else:
        accounting_credit = credit
    if doc.decision in ("Refund", "Exchange"):
        # Return credits first offset the original unpaid receivable. Only the
        # excess credit is paid out, against the return's remaining credit balance.
        accounting_source.reload()
        offset = min(max(0, float(accounting_source.outstanding_amount)), abs(float(accounting_credit.grand_total)))
        if offset:
            receivable = party_account("Customer", source.customer)
            doc.offset_journal = journal([jrow(receivable, debit=offset, party_type="Customer", party=source.customer,
                reference_type="Sales Invoice", reference_name=accounting_credit.name),
                jrow(receivable, credit=offset, party_type="Customer", party=source.customer,
                reference_type="Sales Invoice", reference_name=accounting_source.name)], "Return offset " + doc.name).name
            accounting_credit.reload()
        remaining = max(0, -float(accounting_credit.outstanding_amount))
        if remaining:
            from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
            payment = get_payment_entry("Sales Invoice", accounting_credit.name, bank_account=account, bank_amount=remaining)
            payment.mode_of_payment = values["method"]
            payment.reference_no, payment.reference_date = doc.name, today()
            payment.insert()
            frappe.flags.k3ls_verifying_receipt = doc.name
            try:
                payment.submit()
            finally:
                frappe.flags.k3ls_verifying_receipt = None
            doc.refund_payment = payment.name
    doc.return_invoice, doc.status = credit.name, "Done"
    doc.save()
    # Exchange retains the return plus a separately priced POS replacement sale.
    # Never invent the replacement product or silently charge a difference.


def settle_trade_in(doc):
    invoice = frappe.get_doc(doc.invoice_type, doc.invoice, for_update=True)
    if invoice.docstatus != 1:
        frappe.throw("Confirm the sale before settling this trade-in.")
    intake = frappe.get_doc("K3LS Stock Intake", doc.intake)
    if intake.status != "Posted" or not intake.purchase_invoice:
        frappe.throw("Register the received trade-in stock first.")
    purchase = frappe.get_doc("Purchase Invoice", intake.purchase_invoice, for_update=True)
    # POS invoices do not post GL until consolidation. Use a matching Sales Invoice
    # to keep the credit allocation in the supported receivable ledger.
    if doc.invoice_type == "POS Invoice":
        from moniepoint_pos.ops_money import normalize_reference
        target_name = normalize_reference(dict(reference_type="POS Invoice", reference_name=invoice.name))["reference_name"]
    else:
        target_name = invoice.name
    target = frappe.get_doc("Sales Invoice", target_name, for_update=True)
    if doc.credit > target.outstanding_amount or doc.credit > purchase.outstanding_amount:
        frappe.throw("Trade-in value exceeds the unpaid sale or purchase balance.")
    voucher = journal([jrow(party_account("Supplier", purchase.supplier), debit=doc.credit, party_type="Supplier", party=purchase.supplier,
            reference_type="Purchase Invoice", reference_name=purchase.name),
        jrow(party_account("Customer", invoice.customer), credit=doc.credit, party_type="Customer", party=invoice.customer,
            reference_type="Sales Invoice", reference_name=target_name)], "Trade-in settlement " + doc.name)
    doc.journal, doc.status = voucher.name, "Done"
    doc.save()


def expense(doc):
    if not doc.amount or not doc.evidence or not doc.paid_by:
        frappe.throw("Add the expense amount, receipt and who must be paid.")
    account = company().custom_k3ls_reimbursement_account
    if not account:
        frappe.throw("Configure the shop expense payable account.")
    voucher = journal([jrow(company().default_expense_account, debit=doc.amount), jrow(account, credit=doc.amount)], "Approved expense " + doc.name)
    doc.expense_journal, doc.payable_account = voucher.name, account
    doc.action_reference, doc.status = voucher.name, "Done"
    doc.save()


def request_action(doc, values):
    if doc.request_type == "Expense":
        expense(doc)
        return
    if doc.request_type == "Credit sale":
        if doc.related_doctype not in ("POS Invoice", "Sales Invoice"):
            frappe.throw("Choose the draft sale needing credit approval.")
        sale = frappe.get_doc(doc.related_doctype, doc.related_name, for_update=True)
        if sale.docstatus != 0 or sale.company != COMPANY or sale.customer == "K3LS Walk-in Customer":
            frappe.throw("Choose a draft sale with a named customer.")
        sale.custom_k3ls_credit_approved, sale.custom_k3ls_credit_approver, sale.custom_k3ls_shop_request = 1, frappe.session.user, doc.name
        sale.save()
        doc.approved_sale = sale_signature(sale)
        doc.action_reference, doc.status = sale.name, "Done"
        doc.save()
        return
    if doc.request_type in ("Write-off", "Missing stock"):
        from moniepoint_pos.products import lock_stock, set_stock, shop_warehouse, stock, stock_state
        if not doc.item:
            frappe.throw("Choose the affected product.")
        item = frappe.get_doc("Item", doc.item, for_update=True)
        item.check_permission("write")
        if not item.is_stock_item or item.disabled or item.stock_uom != "Nos" or item.has_batch_no:
            frappe.throw("Choose an active, piece-counted product without batches.")
        if item.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner") or item.is_customer_provided_item:
            frappe.throw("Resolve missing owner stock with its owner before changing its stock.")
        if item.has_serial_no:
            from moniepoint_pos.ops_stock import serials, stock_entry
            location = shop_warehouse()
            lock_stock(item.name, location)
            current = stock_state(item.name, location, locked=True)
            if current["pending_sales"]:
                frappe.throw("Close the till before removing missing or written-off devices.")
            remaining = piece_count(values.get("quantity"))
            removed = piece_count(current["quantity"] - remaining) if remaining < current["quantity"] else 0
            if not removed or not doc.evidence:
                frappe.throw("Reduce the stock count and attach evidence before removing devices.")
            numbers = serials(values.get("serials") or doc.serials, removed, item)
            units = []
            for number in numbers.splitlines():
                actual = frappe.get_doc("Serial No", number, for_update=True)
                if actual.item_code != item.name or actual.warehouse != location:
                    frappe.throw("Remove only serial numbers currently in this shop's stock.")
                name = frappe.db.get_value("K3LS Stock Unit", {"item": item.name, "serial": number}, "name")
                if name:
                    unit = frappe.get_doc("K3LS Stock Unit", name, for_update=True)
                    if unit.status not in ("Ready", "Needs inspection"):
                        frappe.throw("This device is no longer available for a stock write-off.")
                    units.append(unit)
            entry = stock_entry([dict(item_code=item.name, qty=removed, s_warehouse=location,
                serial_no=numbers, use_serial_batch_fields=1)], "Material Issue", doc.request_type + " " + doc.name)
            for unit in units:
                unit.status = "Written off" if doc.request_type == "Write-off" else "Missing"
                unit.save()
            doc.serials, doc.action_reference, doc.status = numbers, entry.name, "Done"
            doc.save()
            return
        state = stock(doc.item)
        qty = piece_count(values.get("quantity"))
        if qty >= state["quantity"]:
            frappe.throw("A write-off must reduce stock.")
        result = set_stock(doc.item, state["modified"], state["stock_token"], qty, doc.reason)
        doc.action_reference, doc.status = result["stock_record"], "Done"
        doc.save()
        return
    if doc.request_type == "Price change":
        from moniepoint_pos.pricing import prices, save_prices
        current = prices(doc.item)
        result = save_prices(doc.item, current["modified"], current["cost_price"] or 0, current["delivery_cost"], values.get("selling_price"),
            current["price_name"], current["price_modified"], current["repair_cost"])
        doc.action_reference, doc.status = result["item"], "Done"
        doc.save()
        return
    if doc.request_type == "Refund":
        frappe.throw("Open Returns to record the original sale, returned stock and refund together.")
    source = frappe.get_doc(doc.related_doctype, doc.related_name, for_update=True)
    source.check_permission("write")
    before = source.as_dict()
    if doc.request_type == "Cancel":
        if source.docstatus != 1:
            frappe.throw("Choose a confirmed record to cancel.")
        source.check_permission("cancel")
        source.cancel()
    elif doc.request_type == "Delete":
        if source.doctype not in ("Item", "Customer", "Supplier"):
            frappe.throw("Keep transaction records. Use cancellation or reversal instead.")
        source.disabled = 1
        source.save()
    elif doc.request_type == "Correction":
        changes = values.get("changes") or {}
        allowed = {"Item": {"item_name", "custom_k3ls_model", "custom_k3ls_configuration", "custom_k3ls_mode", "custom_k3ls_colour"},
            "Customer": {"customer_name", "customer_details"}, "Supplier": {"supplier_name", "supplier_details"},
            "K3LS Repair": {"device", "configuration", "colour", "notes"}}
        if not isinstance(changes, dict) or not changes or not set(changes).issubset(allowed.get(source.doctype, set())):
            frappe.throw("Use a product, contact or repair detail correction. Financial corrections need reversal and replacement.")
        source.update(changes)
        source.save()
    else:
        frappe.throw("Choose a supported request action.")
    audit(source, doc.request_type, before=before, reason=doc.reason, approval=doc.name)
    doc.action_reference, doc.status = source.name, "Done"
    doc.save()


def post_delivery(doc):
    if doc.related_sale:
        links = [name for name in ("POS Invoice", "Sales Invoice", "K3LS Repair") if frappe.db.exists(name, doc.related_sale)]
        if len(links) != 1:
            frappe.throw("Choose an existing sale or repair for this delivery.")
        source = frappe.get_doc(links[0], doc.related_sale)
        source.check_permission("read")
        if source.customer != doc.customer:
            frappe.throw("The delivery customer must match its sale or repair.")
    invoice = frappe.get_doc(dict(doctype="Sales Invoice", company=COMPANY, customer=doc.customer, currency="NGN", due_date=today(),
        items=[dict(item_code="K3LS-DISPATCH", qty=1, rate=doc.fee, description="Delivery " + doc.name,
            income_account=company().default_income_account, cost_center=company().cost_center)]))
    if doc.fee:
        invoice.insert()
        invoice.submit()
        doc.invoice = invoice.name
    total_cost = doc.rider_cost + doc.other_cost
    if total_cost:
        if not doc.rider_supplier:
            frappe.throw("Add the supplier who receives the rider costs.")
        doc.cost_bill = service_bill(doc.rider_supplier, total_cost, "Delivery costs " + doc.name).name
    doc.status = "Dispatched"
    doc.save()


def perform(doc, action, values):
    access(True)
    if action == "post":
        if doc.status != "Approved":
            frappe.throw("Approve this record before confirming it.")
        functions = {"K3LS Return": lambda record: process_return(record, values), "K3LS Trade In": settle_trade_in,
            "K3LS Shop Request": lambda record: request_action(record, values), "K3LS Delivery": post_delivery,
            "K3LS Access Review": complete_access_review}
        if doc.doctype not in functions:
            frappe.throw("Choose a supported action.")
        functions[doc.doctype](doc)
    elif action == "delivered" and doc.doctype == "K3LS Delivery":
        if doc.status != "Dispatched" or not values.get("proof"):
            frappe.throw("Add delivery proof for a dispatched job.")
        doc.proof, doc.delivered_at, doc.status = values["proof"], now_datetime(), "Delivered"
        doc.save()
    elif action == "cancel-delivery" and doc.doctype == "K3LS Delivery":
        if doc.status not in ("Pending", "Approved", "Dispatched") or not str(values.get("reason") or "").strip():
            frappe.throw("Choose an unfinished delivery and add a cancellation reason.")
        for doctype, name in (("Sales Invoice", doc.invoice), ("Purchase Invoice", doc.cost_bill)):
            if not name:
                continue
            bill = frappe.get_doc(doctype, name, for_update=True)
            if bill.docstatus == 1:
                if Decimal(str(bill.outstanding_amount or 0)) != Decimal(str(bill.grand_total or 0)):
                    frappe.throw("Reverse this delivery's receipts and rider payments before cancelling it.")
                bill.check_permission("cancel")
                bill.cancel()
        doc.status, doc.notes = "Cancelled", values["reason"]
        doc.save()
    else:
        frappe.throw("Choose a supported action.")
    audit(doc, action, reason=values.get("reason"))


def complete_access_review(doc):
    user = frappe.get_doc("User", doc.user)
    if doc.outcome == "Disable access":
        if user.name in ("Administrator", "Guest", frappe.session.user):
            frappe.throw("Keep the administrator and current owner access. Review another user.")
        user.check_permission("write")
        user.enabled = 0
        user.save()
    elif doc.outcome == "Change access":
        if access_snapshot(user) == doc.access_before:
            frappe.throw("Change this person's access in Users before confirming the review.")
    doc.access_after = access_snapshot(user)
    doc.status = "Done"
    doc.save()


def access_snapshot(user):
    return frappe.as_json({"enabled": int(bool(user.enabled)), "roles": sorted(row.role for row in user.roles),
        "role_profile": user.role_profile_name or "", "user_type": user.user_type})
