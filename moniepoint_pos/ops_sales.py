"""Sale safeguards shared by POS and ordinary invoice paths."""
from decimal import Decimal

import frappe

from moniepoint_pos.pricing import COMPANY


def prepare_return_credit(doc, method=None):
    if doc.company != COMPANY or not doc.get("is_consolidated") or not doc.is_return or not doc.get("custom_k3ls_return_case"):
        return
    if not frappe.flags.get("k3ls_workflow"):
        frappe.throw("Confirm this credit from its approved return.", frappe.PermissionError)
    case = frappe.get_doc("K3LS Return", doc.custom_k3ls_return_case)
    if case.status != "Approved":
        frappe.throw("Approve the customer's return first.")
    doc.update_outstanding_for_self = 1
    doc.is_pos = 0
    doc.set("payments", [])
    doc.paid_amount = doc.base_paid_amount = doc.change_amount = doc.base_change_amount = 0


def units_for(row, item):
    if not item.has_serial_no or not frappe.db.exists("DocType", "K3LS Stock Unit"):
        return []
    numbers = [number.strip() for number in str(row.get("serial_no") or "").splitlines() if number.strip()]
    if row.get("serial_and_batch_bundle"):
        bundle = frappe.get_doc("Serial and Batch Bundle", row.serial_and_batch_bundle)
        if bundle.item_code != item.name:
            frappe.throw("The selected serial records do not belong to this product.")
        numbers = [entry.serial_no for entry in bundle.entries if entry.serial_no]
    if len(numbers) != len(set(numbers)) or len(numbers) != abs(int(row.stock_qty)):
        frappe.throw("Choose one serial number for each device sold.")
    result = []
    for number in sorted(numbers):
        name = frappe.db.get_value("K3LS Stock Unit", {"item": item.name, "serial": number}, "name")
        if name:
            result.append(frappe.get_doc("K3LS Stock Unit", name, for_update=True))
        elif item.get("custom_k3ls_inspection_required"):
            frappe.throw("Check this device's serial and condition before selling it.")
    return result


def validate_owner_line(row, item):
    agreement_name = item.get("custom_k3ls_owner_stock")
    if not agreement_name:
        frappe.throw("Register this product's owner agreement before selling it.")
    agreement = frappe.get_doc("K3LS Owner Stock", agreement_name, for_update=True)
    if agreement.item != item.name or agreement.status != "Available" or not agreement.agreement or not agreement.payout_per_piece:
        frappe.throw("This owner's agreement is not ready for a sale.")
    if agreement.arrangement == "On demand":
        frappe.throw("Receive the owner's product before selling it.")
    if not item.is_customer_provided_item:
        frappe.throw("Owner stock must use its separate zero-value custody product.")
    row.custom_k3ls_owner_stock = agreement.name
    row.custom_k3ls_owner_due = agreement.payout_per_piece
    row.custom_k3ls_owner_due_date = agreement.due_date
    stock_qty = Decimal(str(row.stock_qty or 0))
    if stock_qty <= 0 or Decimal(str(row.base_net_amount or 0)) / stock_qty < Decimal(str(agreement.payout_per_piece)):
        frappe.throw("Selling price cannot be below the agreed owner payout.")


def validate_sale(doc, method=None):
    if doc.company != COMPANY or (doc.doctype == "Sales Invoice" and doc.is_consolidated):
        return
    if not frappe.db.exists("DocType", "K3LS Return"):
        return
    if doc.is_return:
        if not frappe.flags.get("k3ls_workflow"):
            frappe.throw("Confirm this return from its approved Returns record.", frappe.PermissionError)
        case_name = doc.get("custom_k3ls_return_case")
        if not case_name:
            frappe.throw("Record and approve the customer's return in Returns first.")
        case = frappe.get_doc("K3LS Return", case_name)
        if case.status != "Approved" or case.invoice_type != doc.doctype or case.invoice != doc.return_against:
            frappe.throw("This return does not match its approved case.")
        product_lines = [row for row in doc.items if row.item_code and row.qty]
        field = "pos_invoice_item" if doc.doctype == "POS Invoice" else "sales_invoice_item"
        if len(product_lines) != 1 or product_lines[0].item_code != case.item or product_lines[0].get(field) != case.sale_line or Decimal(str(product_lines[0].qty)) != -Decimal(str(case.quantity)):
            frappe.throw("The returned product, original line and pieces must match the approved return.")
        return
    if doc.doctype == "POS Invoice" and Decimal(str(doc.grand_total or 0)) > Decimal(str(doc.paid_amount or 0)) and "System Manager" not in frappe.get_roles():
        from moniepoint_pos.ops_cases import sale_signature
        request = frappe.get_doc("K3LS Shop Request", doc.custom_k3ls_shop_request) if doc.get("custom_k3ls_shop_request") else None
        if not request or request.status != "Done" or request.request_type != "Credit sale" or request.related_doctype != doc.doctype or request.related_name != doc.name or request.approved_sale != sale_signature(doc):
            frappe.throw("Ask the owner to approve this sale's current customer, products and part payment.")
    for row in doc.items:
        item = frappe.get_cached_doc("Item", row.item_code)
        row.custom_k3ls_owner_stock = None
        row.custom_k3ls_owner_due = 0
        row.custom_k3ls_owner_due_date = None
        if not item.is_stock_item:
            continue
        units = units_for(row, item)
        if any(unit.status != "Ready" for unit in units):
            frappe.throw("A selected device is not ready to sell. Finish its stock check first.")
        if item.get("custom_k3ls_inspection_required") and not units:
            frappe.throw("Finish the product inspection before selling this stock.")
        if item.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner"):
            validate_owner_line(row, item)
        if doc.doctype == "Sales Invoice" and not doc.get("custom_k3ls_repair"):
            if not row.get("pos_invoice") and "System Manager" not in frappe.get_roles():
                frappe.throw("Sell products through POS.")


def snapshot_owner_return(doc, method=None):
    if not doc.is_return or not doc.return_against or doc.company != COMPANY or doc.get("is_consolidated"):
        return
    original = frappe.get_doc(doc.doctype, doc.return_against)
    for row in doc.items:
        source_name = row.get("pos_invoice_item" if doc.doctype == "POS Invoice" else "sales_invoice_item")
        sources = [source for source in original.items if source.item_code == row.item_code and (not source_name or source.name == source_name)]
        if len(sources) != 1:
            frappe.throw("Choose the original product line for this return.")
        row.custom_k3ls_owner_stock = sources[0].get("custom_k3ls_owner_stock")
        row.custom_k3ls_owner_due = sources[0].get("custom_k3ls_owner_due") or 0
        row.custom_k3ls_owner_due_date = sources[0].get("custom_k3ls_owner_due_date")


def update_units(doc, method=None):
    if doc.company != COMPANY or doc.get("is_consolidated") or not frappe.db.exists("DocType", "K3LS Stock Unit"):
        return
    frappe.flags.k3ls_workflow = True
    for row in doc.items:
        item = frappe.get_cached_doc("Item", row.item_code)
        if method == "on_cancel":
            units = [frappe.get_doc("K3LS Stock Unit", name, for_update=True) for name in (doc.flags.get("k3ls_cancel_units") or {}).get(row.name, [])]
        else:
            units = units_for(row, item)
        for unit in units:
            unit.flags.ignore_permissions = True
            if method == "on_cancel":
                if doc.is_return:
                    unit.status, unit.sale_type, unit.sale = "Sold", doc.doctype, doc.return_against
                else:
                    unit.status, unit.sale_type, unit.sale = "Ready", None, None
            elif doc.is_return:
                unit.status, unit.sale_type, unit.sale = "Needs inspection", doc.doctype, doc.return_against
                # Returned devices need condition verification before resale.
            else:
                unit.status, unit.sale_type, unit.sale = "Sold", doc.doctype, doc.name
            unit.save(ignore_permissions=True)


def remember_units(doc, method=None):
    if doc.company != COMPANY or doc.get("is_consolidated") or not frappe.db.exists("DocType", "K3LS Stock Unit"):
        return
    doc.flags.k3ls_cancel_units = {row.name: [unit.name for unit in units_for(row, frappe.get_cached_doc("Item", row.item_code))] for row in doc.items}
