"""Repair-specific screens over the existing repair and invoice records."""
import frappe
from frappe.utils import cint, now_datetime, strip_html_tags

DOCTYPE = "K3LS Repair"
STATES = ("Received", "Diagnosing", "Awaiting approval", "In repair", "Ready for collection", "Collected", "Cancelled")
INTAKE = ("customer", "customer_phone", "customer_address", "relationship", "device", "serial_no",
    "configuration", "colour", "accessories_received", "fault_reported", "arrival_condition", "intake_evidence")
PROGRESS = ("assigned_to", "expected_ready_date", "diagnosis", "work_done", "final_condition", "notes", "follow_up_date", "item")
PRICE = ("customer_charge", "quote_approved", "approval_reference", "parts_cost", "labour_cost",
    "other_cost", "payment_due_date", "agreement_reference", "external_repairer")


def owner():
    return "System Manager" in frappe.get_roles()


@frappe.whitelist(methods=["GET"])
def overview(status="Active", search="", start=0):
    filters = {}
    if status == "Active":
        filters["status"] = ["not in", ["Collected", "Cancelled"]]
    elif status != "All":
        if status not in STATES:
            frappe.throw("Choose a repair status.")
        filters["status"] = status
    term = f"%{str(search).strip()[:100]}%"
    rows = frappe.get_list(DOCTYPE, filters=filters,
        or_filters={field: ["like", term] for field in ("name", "device", "customer", "customer_phone", "serial_no")} if search else None,
        fields=["name", "device", "customer", "customer_phone", "status", "received_at", "expected_ready_date"],
        order_by="received_at desc, name desc", limit_start=max(cint(start), 0), limit_page_length=51)
    counts = frappe.get_list(DOCTYPE, fields=["status", {"COUNT": "name", "as": "count"}], group_by="status", order_by=None, limit_page_length=20)
    return {"repairs": rows[:50], "has_more": len(rows) > 50, "counts": {row.status: row.count for row in counts},
        "can_create": frappe.has_permission(DOCTYPE, "create"), "can_bill": owner()}


def load(name, write=False, modified=None):
    doc = frappe.get_doc(DOCTYPE, name, for_update=write)
    doc.check_permission("write" if write else "read")
    if write:
        if not modified or str(doc.modified) != str(modified):
            frappe.throw("This repair changed in another window. Close and reopen it before saving.")
    return doc


def result(doc):
    invoice = None
    if owner() and doc.sales_invoice:
        bill = frappe.get_doc("Sales Invoice", doc.sales_invoice)
        if bill.has_permission("read"):
            invoice = {"name": bill.name, "docstatus": bill.docstatus, "total": bill.grand_total,
                "outstanding": bill.outstanding_amount, "currency": bill.currency, "status": bill.status}
    can_write = doc.has_permission("write")
    doc.apply_fieldlevel_read_permissions()
    return {"repair": doc.as_dict(), "invoice": invoice, "can_write": can_write, "can_bill": owner()}


@frappe.whitelist(methods=["GET"])
def details(name):
    return result(load(name))


@frappe.whitelist(methods=["GET"])
def customer_details(name):
    frappe.has_permission(DOCTYPE, "create", throw=True)
    customer = frappe.get_doc("Customer", name)
    customer.check_permission("read")
    if customer.disabled or customer.name == "K3LS Walk-in Customer":
        frappe.throw("Choose an active named customer.")
    customer.apply_fieldlevel_read_permissions()
    previous = frappe.get_list(DOCTYPE, filters={"customer": name}, fields=["name"], limit_page_length=1)
    return {"phone": customer.get("mobile_no") or "",
        "address": strip_html_tags(customer.get("primary_address") or ""), "returning": bool(previous)}


@frappe.whitelist(methods=["POST"])
def save(values, name=None, modified=None, section="intake"):
    values = frappe.parse_json(values)
    if not isinstance(values, dict):
        frappe.throw("Check the repair details.")
    if section not in ("intake", "progress", "price"):
        frappe.throw("Choose the repair section.")
    if section == "price":
        frappe.only_for("System Manager")
    if name:
        doc = load(name, write=True, modified=modified)
        if doc.status in ("Collected", "Cancelled"):
            frappe.throw("This repair is closed. Open its full record to make corrections.")
    else:
        if section != "intake":
            frappe.throw("Add the device and customer first.")
        frappe.has_permission(DOCTYPE, "create", throw=True)
        doc = frappe.new_doc(DOCTYPE)
        doc.received_at = now_datetime()
        doc.status = "Received"
    allowed = INTAKE if section == "intake" else PROGRESS if section == "progress" else PRICE
    doc.update({field: values[field] for field in allowed if field in values})
    if doc.customer == "K3LS Walk-in Customer":
        frappe.throw("Choose the customer's name for this repair.")
    doc.save()
    return result(doc)


@frappe.whitelist(methods=["POST"])
def advance(name, modified, action, values=None):
    doc = load(name, write=True, modified=modified)
    values = frappe.parse_json(values) or {}
    transitions = {"check": (("Received",), "Diagnosing"),
        "approval": (("Diagnosing",), "Awaiting approval"),
        "start": (("Diagnosing", "Awaiting approval"), "In repair"),
        "ready": (("In repair",), "Ready for collection"),
        "collect": (("Ready for collection",), "Collected")}
    if action not in transitions or doc.status not in transitions[action][0]:
        frappe.throw("Reopen the repair to see its next step.")
    if action == "collect":
        frappe.only_for("System Manager")
        if frappe.db.exists("DocType", "K3LS Stock Movement") and frappe.db.exists("K3LS Stock Movement", {"repair": doc.name, "status": ["in", ["Sent", "Received"]]}):
            frappe.throw("Record the device's return from its repairer before collection.")
    if action == "approval":
        doc.diagnosis = values.get("diagnosis") or doc.diagnosis
        if not doc.diagnosis:
            frappe.throw("Add the problem found before asking for approval.")
    if action == "ready":
        doc.work_done = values.get("work_done")
        doc.final_condition = values.get("final_condition")
        doc.fixed_at = now_datetime()
    if action == "collect":
        doc.collected_at = now_datetime()
    doc.status = transitions[action][1]
    doc.save()
    return result(doc)


@frappe.whitelist(methods=["POST"])
def invoice(name, modified):
    frappe.only_for("System Manager")
    doc = load(name, write=True, modified=modified)
    doc.create_invoice()
    bill = frappe.get_doc("Sales Invoice", doc.sales_invoice)
    if bill.docstatus == 0:
        bill.submit()
    if doc.total_cost and not doc.get("custom_k3ls_cost_bill"):
        if not doc.external_repairer:
            frappe.throw("Add the repairer supplier before recording the repair costs.")
        from moniepoint_pos.ops_money import service_bill
        doc.custom_k3ls_cost_bill = service_bill(doc.external_repairer, doc.total_cost, "Repair costs " + doc.name).name
        doc.save()
    return result(doc)


def configure():
    frappe.only_for("System Manager")
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-repairs", force=True)
    sidebar = frappe.get_doc("Workspace Sidebar", "K3LS Shop")
    for row in sidebar.items:
        if row.label == "Repairs":
            row.link_type = "Page"
            row.link_to = "shop-repairs"
    sidebar.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"page": "shop-repairs", "repairs_created": False}
