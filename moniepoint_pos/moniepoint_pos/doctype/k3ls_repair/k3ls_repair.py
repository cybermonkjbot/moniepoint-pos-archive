"""Repair intake and progress. Billing stays in ERPNext's invoice ledger."""
import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_datetime


class K3LSRepair(Document):
    def validate(self):
        if self.is_new():
            self.received_by = frappe.session.user
            if self.status not in ("Received", "Diagnosing"):
                frappe.throw("Save the device details before changing the repair status.")
        self.total_cost = sum(flt(self.get(field)) for field in ("parts_cost", "labour_cost", "other_cost"))
        if any(flt(self.get(field)) < 0 for field in ("parts_cost", "labour_cost", "other_cost", "customer_charge")):
            frappe.throw("Repair charges and costs cannot be negative.")
        if self.quote_approved and not self.approval_reference:
            frappe.throw("Add the customer's price approval reference.")
        if self.status == "In repair" and not self.quote_approved:
            frappe.throw("Confirm the customer approved the price before starting repairs.")
        if self.status in ("Ready for collection", "Collected") and not (self.work_done and self.final_condition and self.fixed_at):
            frappe.throw("Add the work done, condition now and repair date before marking it ready.")
        if self.status == "Collected" and not self.collected_at:
            frappe.throw("Record the collection date.")
        for field in ("fixed_at", "collected_at"):
            if self.get(field) and get_datetime(self.get(field)) < get_datetime(self.received_at):
                frappe.throw("Repair and collection dates cannot be before the device was received.")
        old = self.get_doc_before_save()
        if old:
            self.received_by = old.received_by
            if old.status in ("Collected", "Cancelled") and old.status != self.status:
                frappe.only_for("System Manager")
        if old and old.status != self.status and self.status in ("Collected", "Cancelled"):
            frappe.only_for("System Manager")
        if self.sales_invoice:
            invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
            if invoice.customer != self.customer or invoice.company != "K3LS LIMITED":
                frappe.throw("Choose a K3LS invoice for this customer.")
            if invoice.custom_k3ls_repair != self.name:
                frappe.throw("Choose an invoice linked to this repair.")
            if flt(invoice.grand_total) != flt(self.customer_charge):
                frappe.throw("The repair price must match the invoice total.")

    @frappe.whitelist(methods=["POST"])
    def create_invoice(self):
        frappe.only_for("System Manager")
        self.check_permission("write")
        if self.is_new():
            frappe.throw("Save the repair before creating an invoice.")
        # Serialize requests so a double-click cannot create two repair invoices.
        frappe.db.sql("select name from `tabK3LS Repair` where name=%s for update", self.name)
        self.reload()
        if self.sales_invoice:
            return self.sales_invoice
        if not self.quote_approved or not self.approval_reference or flt(self.customer_charge) <= 0:
            frappe.throw("Enter a price above 0 and record the customer's approval first.")
        company = frappe.get_doc("Company", "K3LS LIMITED")
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice", "company": company.name, "customer": self.customer,
            "currency": "NGN", "due_date": self.payment_due_date or frappe.utils.today(),
            "custom_k3ls_repair": self.name,
            "items": [{"item_code": "K3LS-REPAIR", "qty": 1, "rate": self.customer_charge,
                "description": f"Repair {self.name}: {frappe.utils.escape_html(self.device)}",
                "income_account": company.default_income_account, "cost_center": company.cost_center}],
        }).insert()
        self.sales_invoice = invoice.name
        self.save()
        return invoice.name
