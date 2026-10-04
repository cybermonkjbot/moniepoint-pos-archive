"""Permission-checked shop workflows and an owner action history."""
from decimal import Decimal
import frappe
from frappe.utils import cint, getdate, now_datetime, today

from moniepoint_pos.operations_schema import SCHEMAS
from moniepoint_pos.pricing import COMPANY

TYPES = {"intake": "K3LS Stock Intake", "inspection": "K3LS Stock Inspection", "movements": "K3LS Stock Movement",
    "counts": "K3LS Stock Count", "requests": "K3LS Shop Request", "returns": "K3LS Return", "trade-ins": "K3LS Trade In",
    "debts": "K3LS Debt", "plans": "K3LS Instalment Plan", "receipts": "K3LS Receipt", "deliveries": "K3LS Delivery",
    "owner-stock": "K3LS Owner Stock", "account-checks": "K3LS Account Check", "audit": "K3LS Shop Audit", "units": "K3LS Stock Unit", "controls": "K3LS Access Review"}
STAFF_FIELDS = {
    "K3LS Stock Unit": {"item", "serial", "intake", "arrival_condition", "final_condition", "inspection", "status", "sale_type", "sale"},
    "K3LS Stock Intake": {"supplier", "source_type", "ownership", "source_phone", "source_address", "source_reference", "received_on", "products", "notes", "evidence", "arrangement"},
    "K3LS Stock Inspection": {"item", "serials", "received_on", "testing", "operating_status", "bios", "no_ram", "no_storage", "broken_screen", "screen", "keyboard", "trackpad", "battery", "speaker", "no_power", "faults", "quantity", "evidence", "notes"},
    "K3LS Stock Movement": {"item", "repair", "quantity", "serials", "movement_type", "from_warehouse", "to_warehouse", "custodian", "phone", "expected_return", "reason", "evidence", "receiving_user"},
    "K3LS Stock Count": {"counted_on", "products", "evidence", "notes"},
    "K3LS Shop Request": {"request_type", "title", "item", "serials", "related_doctype", "related_name", "amount", "paid_by", "category", "reason", "evidence"},
    "K3LS Return": {"invoice_type", "invoice", "item", "sale_line", "quantity", "serials", "decision", "reason", "condition", "evidence"},
    "K3LS Receipt": {"reference_type", "reference_name", "amount", "method", "received_on", "bank_reference", "payer", "evidence", "notes", "checkout_sale"},
    "K3LS Delivery": {"customer", "phone", "related_sale", "pickup", "destination", "rider", "expected_on", "proof", "notes"},
}
LOCKED_STATES = {"Approved", "Posted", "Verified", "Reversed", "Done", "Sent", "Received", "Returned", "Closed", "Delivered", "Dispatched", "Owner direct sale", "Settled", "Reviewed", "Cancelled"}


def owner():
    return "System Manager" in frappe.get_roles()


def access(owner_only=False):
    from moniepoint_pos.shop_ui import enabled
    if frappe.session.user == "Guest" or not enabled():
        frappe.throw("Sign in to the shop.", frappe.PermissionError)
    if owner_only:
        frappe.only_for("System Manager")
    elif not owner() and not set(frappe.get_roles()).intersection({"Sales User", "Sales Manager", "K3LS Repair Staff"}):
        frappe.throw("This account does not have shop access.", frappe.PermissionError)


def dtype(kind):
    if kind not in TYPES:
        frappe.throw("Choose a shop section.")
    return TYPES[kind]


def load(kind, name, modified=None, write=False):
    access()
    doc = frappe.get_doc(dtype(kind), name, for_update=write)
    doc.check_permission("write" if write else "read")
    if not owner() and doc.doctype != "K3LS Stock Unit" and doc.owner != frappe.session.user and not (doc.doctype == "K3LS Stock Movement" and doc.receiving_user == frappe.session.user):
        frappe.throw("Only the owner can change another person's request.", frappe.PermissionError)
    if write and (not modified or str(doc.modified) != str(modified)):
        frappe.throw("This record changed. Close and reopen it before saving.")
    return doc


def allowed_fields(doctype):
    fields = {df["fieldname"] for df in SCHEMAS[doctype]["fields"] if not df.get("read_only") and (owner() or df.get("permlevel", 0) == 0)}
    return fields if owner() else fields.intersection(STAFF_FIELDS.get(doctype, set()))


def safe_values(doctype, values):
    if not isinstance(values, dict):
        frappe.throw("Check the details.")
    allowed = allowed_fields(doctype)
    result = {key: value for key, value in values.items() if key in allowed}
    for df in SCHEMAS[doctype]["fields"]:
        if df["fieldtype"] == "Table" and df["fieldname"] in result:
            rows = result[df["fieldname"]]
            if not isinstance(rows, list) or not rows or len(rows) > 100:
                frappe.throw("Add between 1 and 100 products or payments.")
            permitted = {f["fieldname"] for f in SCHEMAS[df["options"]]["fields"] if not f.get("read_only")}
            if not owner() and df["options"] == "K3LS Intake Product":
                permitted -= {"cost", "delivery_cost", "selling_price", "owner_payout"}
            if any(not isinstance(row, dict) for row in rows):
                frappe.throw("Check each product or payment row.")
            result[df["fieldname"]] = [{key: value for key, value in row.items() if key in permitted or key == "name"} for row in rows]
    return result


def public(doc):
    doc.apply_fieldlevel_read_permissions()
    data = doc.as_dict()
    if not owner():
        visible = STAFF_FIELDS.get(doc.doctype, set()) | {"name", "doctype", "modified", "creation", "owner", "status"}
        data = {key: value for key, value in data.items() if key in visible}
        for field in SCHEMAS[doc.doctype]["fields"]:
            if field["fieldtype"] == "Table" and field["fieldname"] in data:
                allowed = {df["fieldname"] for df in SCHEMAS[field["options"]]["fields"] if df.get("permlevel", 0) == 0}
                data[field["fieldname"]] = [{key: value for key, value in row.items() if key in allowed or key == "name"} for row in data[field["fieldname"]]]
    return data


@frappe.whitelist(methods=["GET"])
def metadata(kind):
    access()
    name = dtype(kind)
    frappe.has_permission(name, "read", throw=True)
    fields = []
    allowed = allowed_fields(name)
    display = []
    for df in SCHEMAS[name]["fields"]:
        if df.get("hidden") or (not owner() and df.get("permlevel", 0) != 0):
            continue
        field = dict(df)
        if field["fieldtype"] == "Table":
            children = [dict(child, in_list_view=int(child["fieldname"] in {"item", "product_name", "quantity", "warehouse", "counted", "due_date", "amount"}))
                for child in SCHEMAS[field["options"]]["fields"] if not child.get("hidden") and (owner() or child.get("permlevel", 0) == 0)]
            field["fields"] = children
        if owner() or field["fieldname"] in STAFF_FIELDS.get(name, set()) or field["fieldname"] == "status":
            display.append(field)
        if field["fieldname"] in allowed:
            editable = dict(field)
            if field["fieldtype"] == "Table":
                editable["fields"] = [child for child in field["fields"] if not child.get("read_only")]
            fields.append(editable)
    return {"doctype": name, "fields": fields, "display_fields": display, "owner": owner(), "can_create": name not in ("K3LS Shop Audit", "K3LS Owner Stock", "K3LS Stock Unit") and frappe.has_permission(name, "create")}


@frappe.whitelist(methods=["GET"])
def records(kind, search="", status="", start=0, names=None):
    access()
    name = dtype(kind)
    filters = {} if owner() or name in ("K3LS Stock Unit", "K3LS Stock Movement") else {"owner": frappe.session.user}
    if status and status != "All":
        filters["status"] = status
    if names is not None:
        selected = frappe.parse_json(names)
        if not isinstance(selected, list) or len(selected) > 2000 or any(not isinstance(value, str) for value in selected):
            frappe.throw("Reopen the review filter.")
        filters["name"] = ["in", selected or [""]]
    term = str(search or "").strip()[:140]
    meta = frappe.get_meta(name)
    fields = ["name", "modified", "creation", "owner"] + (["status"] if meta.has_field("status") else [])
    candidates = ["title", "supplier", "customer", "item", "repair", "serial", "details", "invoice", "reference_name", "reason", "record_name", "action", "custodian"]
    fields += [key for key in candidates if meta.has_field(key)]
    ors = {key: ["like", "%" + term + "%"] for key in ["name", *candidates] if key == "name" or meta.has_field(key)} if term else None
    rows = frappe.get_list(name, filters=filters, or_filters=ors, fields=fields,
        order_by="creation desc", limit_start=max(cint(start), 0), limit_page_length=51)
    return {"rows": rows[:50], "has_more": len(rows) > 50}


@frappe.whitelist(methods=["GET"])
def source_details(supplier):
    access()
    doc = frappe.get_doc("Supplier", supplier)
    doc.check_permission("read")
    if doc.disabled:
        frappe.throw("Choose an active source.")
    from frappe.utils import strip_html_tags
    return dict(phone=doc.get("mobile_no") or "", address=strip_html_tags(doc.get("primary_address") or ""),
        source_type="Individual seller" if doc.supplier_type == "Individual" else "Business supplier",
        ownership={"Sister owner": "Sister Owned", "External owner": "Third-party Owner"}.get(doc.get("custom_k3ls_source_type"), "K3LS Owned"))


@frappe.whitelist(methods=["GET"])
def intake_product(item):
    access()
    doc = frappe.get_doc("Item", item)
    doc.check_permission("read")
    if doc.disabled or not doc.is_stock_item or doc.stock_uom != "Nos":
        frappe.throw("Choose an active product sold in pieces.")
    result = dict(category=doc.item_group, model=doc.get("custom_k3ls_model"), specifications=doc.get("custom_k3ls_configuration"),
        mode=doc.get("custom_k3ls_mode"), colour=doc.get("custom_k3ls_colour"))
    if owner():
        from moniepoint_pos.pricing import amounts, selling_price, shop_price_list
        prices = amounts(doc, selling_price(doc, shop_price_list()))
        result.update(cost=prices["cost_price"], delivery_cost=prices["delivery_cost"], selling_price=prices["selling_price"])
    return result


@frappe.whitelist(methods=["POST"])
def add_source(name, phone, address, city, source_type="Supplier", customer=None):
    access(True)
    if source_type not in ("Supplier", "Individual seller", "Sister owner", "External owner"):
        frappe.throw("Choose a source type.")
    if not all(str(value or "").strip() for value in (name, phone, address, city)):
        frappe.throw("Add the source name, phone, address and town.")
    if customer:
        contact = frappe.get_doc("Customer", customer, for_update=True)
        contact.check_permission("write")
        contact.custom_k3ls_contact_role = "Both"
        contact.save()
    supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=str(name).strip(),
        supplier_type="Individual" if source_type == "Individual seller" else "Company", supplier_group="All Supplier Groups",
        custom_k3ls_source_type=source_type, country="Nigeria"))
    supplier.insert()
    person = frappe.get_doc(dict(doctype="Contact", first_name=str(name).strip(),
        phone_nos=[dict(phone=str(phone).strip(), is_primary_mobile_no=1)],
        links=[dict(link_doctype="Supplier", link_name=supplier.name)]))
    person.insert()
    location = frappe.get_doc(dict(doctype="Address", address_title=str(name).strip(), address_type="Billing",
        address_line1=str(address).strip(), city=str(city).strip(), country="Nigeria", is_primary_address=1,
        links=[dict(link_doctype="Supplier", link_name=supplier.name)]))
    location.insert()
    supplier.supplier_primary_contact, supplier.supplier_primary_address = person.name, location.name
    from frappe.contacts.doctype.address.address import get_address_display
    supplier.mobile_no, supplier.primary_address = str(phone).strip(), get_address_display(location.name)
    supplier.save()
    return dict(name=supplier.name, phone=str(phone).strip(), address=str(address).strip(), source_type=source_type)


@frappe.whitelist(methods=["GET"])
def details(kind, name):
    doc = load(kind, name)
    result = {"doc": public(doc), "owner": owner(), "editable": doc.doctype not in ("K3LS Shop Audit", "K3LS Owner Stock", "K3LS Stock Unit") and doc.get("status") not in LOCKED_STATES}
    if owner():
        from moniepoint_pos.ops_money import balance, plan_summary
        if doc.doctype == "K3LS Owner Stock" or (doc.doctype == "K3LS Debt" and doc.status == "Posted") or (doc.doctype == "K3LS Delivery" and doc.invoice) or (doc.doctype == "K3LS Shop Request" and doc.request_type == "Expense" and doc.status == "Done"):
            result["balance"] = balance(doc.doctype, doc.name)
        if doc.doctype == "K3LS Instalment Plan":
            result["plan"] = plan_summary(doc)
    return result


@frappe.whitelist(methods=["POST"])
def save(kind, values, name=None, modified=None, request_key=None):
    access()
    doctype = dtype(kind)
    if doctype in ("K3LS Shop Audit", "K3LS Owner Stock", "K3LS Stock Unit"):
        frappe.throw("This record is created by its shop workflow.")
    parsed = frappe.parse_json(values)
    if not isinstance(parsed, dict):
        frappe.throw("Check the details.")
    if name:
        doc = load(kind, name, modified, write=True)
        if doc.get("status") in LOCKED_STATES:
            frappe.throw("This record is already confirmed. Create a correction request instead.")
    else:
        frappe.has_permission(doctype, "create", throw=True)
        key = str(request_key or "").strip()
        if not key or len(key) > 100:
            frappe.throw("Reopen this form before saving.")
        existing = frappe.db.get_value(doctype, {"request_key": key, "owner": frappe.session.user}, "name")
        if existing:
            return details(kind, existing)
        doc = frappe.new_doc(doctype)
        doc.request_key = key
    frappe.flags.k3ls_workflow = True
    if not name and doctype in ("K3LS Receipt", "K3LS Instalment Plan") and owner():
        from moniepoint_pos.ops_money import normalize_reference
        parsed = normalize_reference(parsed)
    doc.update(safe_values(doctype, parsed))
    doc.flags.k3ls_operation = True
    doc.save()
    return details(kind, doc.name)


@frappe.whitelist(methods=["POST"])
def action(kind, name, modified, action, values=None):
    access()
    doc = load(kind, name, modified, write=True)
    values = frappe.parse_json(values) or {}
    if not isinstance(values, dict):
        frappe.throw("Check the action details.")
    if not owner() and doc.owner != frappe.session.user and action != "received":
        frappe.throw("Only confirm receipt of stock assigned to this account.", frappe.PermissionError)
    frappe.flags.k3ls_workflow = True
    frappe.flags.k3ls_workflow_action = action
    doc.flags.k3ls_operation = True
    if action == "revise":
        access(True)
        if doc.status not in ("Approved", "Rejected") or not values.get("reason"):
            frappe.throw("Choose an unposted reviewed record and add a correction reason.")
        doc.status = "Pending"
        for field in ("reviewed_by", "reviewed_at", "supervisor"):
            if doc.meta.has_field(field):
                doc.set(field, None)
        doc.save()
        audit(doc, "Returned for correction", reason=values["reason"])
    elif action in ("approve", "reject") and doc.doctype != "K3LS Receipt":
        access(True)
        if doc.get("status") != "Pending":
            frappe.throw("This request was already reviewed.")
        if action == "reject" and not str(values.get("reason") or "").strip():
            frappe.throw("Add a reason for rejecting this request.")
        doc.status = "Approved" if action == "approve" else "Rejected"
        for key, value in {"reviewed_by": frappe.session.user, "reviewed_at": now_datetime(), "review_notes": values.get("reason"),
                           "decision": values.get("reason"), "supervisor": frappe.session.user}.items():
            if doc.meta.has_field(key) and not (doc.doctype == "K3LS Return" and key == "decision"):
                doc.set(key, value)
        doc.save()
        audit(doc, action, reason=values.get("reason"))
    else:
        from moniepoint_pos import ops_stock, ops_money, ops_cases
        module = ops_stock if kind in ("intake", "inspection", "movements", "counts", "owner-stock") else ops_money if kind in ("debts", "plans", "receipts", "account-checks") else ops_cases
        module.perform(doc, action, values)
    return details(kind, doc.name)


def validate(doc, method=None):
    if doc.doctype not in SCHEMAS or SCHEMAS[doc.doctype]["child"]:
        return
    if doc.doctype == "K3LS Shop Audit":
        if not frappe.flags.get("k3ls_audit_write") or not doc.is_new():
            frappe.throw("Action history cannot be changed.", frappe.PermissionError)
        return
    access()
    old = doc.get_doc_before_save()
    if not frappe.flags.get("k3ls_workflow"):
        frappe.throw("Use the shop screen to save this record.", frappe.PermissionError)
    receiver = doc.doctype == "K3LS Stock Movement" and doc.receiving_user == frappe.session.user and frappe.flags.get("k3ls_workflow_action") == "received"
    if old and not owner() and old.owner != frappe.session.user and not doc.flags.ignore_permissions and not receiver:
        frappe.throw("Only the owner can change this record.", frappe.PermissionError)
    if old:
        doc.request_key = old.request_key
    else:
        doc.request_key = doc.get("request_key") or frappe.generate_hash(length=32)
    from moniepoint_pos import ops_stock, ops_money, ops_cases
    module = ops_stock if doc.doctype in {TYPES[x] for x in ("intake", "inspection", "movements", "counts", "owner-stock")} else ops_money if doc.doctype in {TYPES[x] for x in ("debts", "plans", "receipts", "account-checks")} else ops_cases
    module.validate(doc, old)


def history(doc, method=None):
    if doc.doctype in SCHEMAS and not SCHEMAS[doc.doctype]["child"] and doc.doctype != "K3LS Shop Audit":
        old = doc.get_doc_before_save()
        audit(doc, "Created" if not old else "Updated", old.as_dict() if old else None)


def audit(doc, action, before=None, reason=None, approval=None):
    if not frappe.db.exists("DocType", "K3LS Shop Audit"):
        return
    entry = frappe.get_doc(dict(doctype="K3LS Shop Audit", actor=frappe.session.user,
        action=action, record_type=doc.doctype, record_name=doc.name,
        before_value=frappe.as_json(before) if before else None, after_value=frappe.as_json(doc.as_dict()),
        reason=reason, approval=approval))
    previous = frappe.flags.get("k3ls_audit_write")
    frappe.flags.k3ls_audit_write = True
    try:
        entry.insert(ignore_permissions=True)
    finally:
        frappe.flags.k3ls_audit_write = previous


def no_delete(doc, method=None):
    frappe.throw("Keep this shop record. Use a reversal or correction request.", frappe.PermissionError)


def query_conditions(user=None):
    user = user or frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return ""
    return "owner=" + frappe.db.escape(user)


def movement_query_conditions(user=None):
    user = user or frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return ""
    escaped = frappe.db.escape(user)
    return f"(`tabK3LS Stock Movement`.owner={escaped} OR `tabK3LS Stock Movement`.receiving_user={escaped})"


def has_permission(doc, user=None, permission_type=None, **kwargs):
    """Apply the same row boundary to direct REST/document access as the shop UI."""
    user = user or frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return True
    if user == "Guest" or not SCHEMAS.get(doc.doctype, {}).get("staff"):
        return False
    if doc.doctype == "K3LS Stock Unit":
        return kwargs.get("ptype", permission_type) in ("read", "select")
    if doc.owner == user or doc.is_new():
        return True
    if doc.doctype == "K3LS Stock Movement" and doc.receiving_user == user and kwargs.get("ptype", permission_type) in ("read", "write"):
        return True
    return False


def configure_navigation():
    for title in ("K3LS Shop", "K3LS Owner"):
        if not frappe.db.exists("Workspace Sidebar", title):
            continue
        sidebar = frappe.get_doc("Workspace Sidebar", title)
        links = [("Receive stock", "intake", "package-plus"), ("Stock movements", "movements", "arrow-right-left"), ("Requests", "requests", "clipboard-check"), ("Returns", "returns", "undo-2")]
        if title == "K3LS Owner":
            links += [("Money we owe", "payables", "wallet"), ("Owner review", "review", "shield-check")]
        for label, route, icon in links:
            if not any(row.link_to == "shop-operations" and row.label == label for row in sidebar.items):
                sidebar.append("items", dict(type="Link", label=label, link_type="Page", link_to="shop-operations", icon=icon,
                    route_options=frappe.as_json({"section": route, "sidebar": title})))
        sidebar.save()


@frappe.whitelist(methods=["GET"])
def inventory(search="", start=0, item=None, names=None):
    """Operational stock/custody only. Never send valuations to staff."""
    access()
    filters = {"disabled": 0, "is_stock_item": 1}
    if item:
        filters["name"] = item
    elif names is not None:
        selected = frappe.parse_json(names)
        if not isinstance(selected, list) or len(selected) > 2000 or any(not isinstance(value, str) for value in selected):
            frappe.throw("Reopen the inventory filter.")
        filters["name"] = ["in", selected or [""]]
    term = "%" + str(search or "").strip()[:140] + "%"
    rows = frappe.get_list("Item", filters=filters, or_filters={field: ["like", term] for field in ("name", "item_name", "custom_k3ls_model", "custom_k3ls_configuration")} if search else None,
        fields=["name", "item_name", "custom_k3ls_model", "custom_k3ls_configuration", "custom_k3ls_colour", "custom_k3ls_ownership", "custom_k3ls_final_condition", "custom_k3ls_owner"],
        order_by="item_name asc, name asc", limit_start=max(cint(start), 0), limit_page_length=51)
    from moniepoint_pos.products import stock_state
    for row in rows[:50]:
        locations = frappe.get_all("Bin", filters={"item_code": row.name}, fields=["warehouse"])
        row.locations = []
        for location in locations:
            place = frappe.get_doc("Warehouse", location.warehouse)
            if place.company != COMPANY or not place.has_permission("read"):
                continue
            row.locations.append(dict(warehouse=place.name, pieces=stock_state(row.name, place.name)["quantity"]))
        movements = frappe.get_all("K3LS Stock Movement", filters={"item": row.name}, fields=["name", "status", "custodian", "phone", "to_warehouse", "expected_return", "received_at"], order_by="creation desc", limit_page_length=10)
        row.movements = [dict(entry, overdue=bool(entry.expected_return and entry.status in ("Sent", "Received") and getdate(entry.expected_return) < getdate(today()))) for entry in movements]
        row.units = frappe.get_list("K3LS Stock Unit", filters={"item": row.name}, fields=["name", "serial", "status", "final_condition"], limit_page_length=100)
    return {"rows": rows[:50], "has_more": len(rows) > 50}


@frappe.whitelist(methods=["GET"])
def sale_lines(invoice_type, invoice):
    access()
    if invoice_type not in ("POS Invoice", "Sales Invoice"):
        frappe.throw("Choose the original sale.")
    sale = frappe.get_doc(invoice_type, invoice)
    sale.check_permission("read")
    if sale.company != COMPANY or sale.docstatus != 1 or sale.is_return:
        frappe.throw("Choose a confirmed K3LS sale.")
    return [dict(name=row.name, item=row.item_code, title=row.item_name, quantity=row.qty, serials=row.get("serial_no"),
        invoice_type="POS Invoice" if sale.get("is_consolidated") else invoice_type,
        invoice=row.get("pos_invoice") if sale.get("is_consolidated") else invoice,
        sale_line=row.get("pos_invoice_item") if sale.get("is_consolidated") else row.name) for row in sale.items]


@frappe.whitelist(methods=["GET"])
def review():
    access()
    from moniepoint_pos.ops_money import overview, plan_summary
    groups = []
    def group(title, metrics):
        groups.append(dict(title=title, metrics=[dict(title=label, value=value, section=section, currency=currency)
            for label, value, section, currency in metrics]))
    def rows(kind, fields, filters=None):
        return frappe.get_list(dtype(kind), filters=filters or {}, fields=fields, limit_page_length=0)
    movements = rows("movements", ["name", "movement_type", "expected_return", "status", "repair"], {"status": ["in", ["Sent", "Received"]]})
    counts = rows("counts", ["name"], {"status": ["in", ["Pending", "Approved"]]})
    count_lines = frappe.get_all("K3LS Count Product", filters={"parent": ["in", [row.name for row in counts]]}, fields=["parent", "expected", "counted"]) if counts else []
    repairs = frappe.get_list("K3LS Repair", filters={"status": ["not in", ["Collected", "Cancelled"]]}, fields=["name", "status", "follow_up_date"], limit_page_length=0)
    group("Stock and repairs", [("Missing pieces", sum(max(0, row.expected - row.counted) for row in count_lines), "counts", None),
        ("Count differences", sum(row.expected != row.counted for row in count_lines), "counts", None),
        ("Overdue agent stock", sum(row.movement_type == "With agent" and bool(row.expected_return) and getdate(row.expected_return) < getdate(today()) for row in movements), "movements", None),
        ("Stock with repairers", sum(row.movement_type == "With repairer" for row in movements), "movements", None),
        ("Open repairs", len(repairs), "repairs", None),
        ("Pending requests", len(rows("requests", ["name"], {"status": "Pending"})), "requests", None)])
    receipts = rows("receipts", ["name", "status", "method", "bank_reference", "matched_on", "reference_type"])
    group("Payment review", [("Waiting for verification", sum(row.status == "Pending" for row in receipts), "receipts", None),
        ("Bank payments not matched", sum(row.status == "Verified" and row.method != "Cash" and not row.matched_on for row in receipts), "receipts", None),
        ("Missing payment references", sum(row.status in ("Pending", "Verified") and not row.bank_reference for row in receipts), "receipts", None),
        ("Rejected payments", sum(row.status == "Rejected" for row in receipts), "receipts", None)])
    reports = []
    drilldowns = {
        "Missing pieces": [row.parent for row in count_lines if row.expected > row.counted],
        "Count differences": [row.parent for row in count_lines if row.expected != row.counted],
        "Overdue agent stock": [row.name for row in movements if row.movement_type == "With agent" and row.expected_return and getdate(row.expected_return) < getdate(today())],
        "Stock with repairers": [row.name for row in movements if row.movement_type == "With repairer"],
        "Waiting for verification": [row.name for row in receipts if row.status == "Pending"],
        "Bank payments not matched": [row.name for row in receipts if row.status == "Verified" and row.method != "Cash" and not row.matched_on],
        "Missing payment references": [row.name for row in receipts if row.status in ("Pending", "Verified") and not row.bank_reference],
        "Rejected payments": [row.name for row in receipts if row.status == "Rejected"],
        "Pending requests": [row.name for row in rows("requests", ["name"], {"status": "Pending"})],
    }
    if owner():
        money = overview()
        balances = money["rows"]
        payable = [row for row in balances if row["direction"] == "Pay"]
        receivable = [row for row in balances if row["direction"] == "Receive"]
        group("Money owed", [("Customers owe", money["totals"]["Receive"], "receivables", "NGN"),
            ("Overdue customer balances", sum(row["amount"] for row in receivable if row["overdue"]), "receivables", "NGN"),
            ("Overdue customers", len({row["party"] for row in receivable if row["overdue"]}), "receivables", None)])
        plan_rows = rows("plans", ["name", "next_follow_up"], {"status": "Active"})
        summaries = [plan_summary(frappe.get_doc(dtype("plans"), row.name)) for row in plan_rows]
        group("Payment plans", [("Overdue instalments", sum(len(summary["overdue"]) for summary in summaries), "plans", None),
            ("Outside payment plans", sum(row["unplanned_amount"] for row in balances), "unplanned", "NGN"),
            ("Follow-ups due", sum(bool(row.next_follow_up) and getdate(row.next_follow_up) <= getdate(today()) for row in plan_rows), "plans", None)])
        group("Money we owe", [("Supplier and other bills", money["totals"]["Pay"], "payables", "NGN"),
            ("Overdue bills", sum(row["amount"] for row in payable if row["overdue"]), "payables", "NGN"),
            ("Overdue suppliers", len({row["party"] for row in payable if row["overdue"]}), "payables", None),
            ("Supplier payments to check", sum(row.status == "Pending" and row.reference_type in ("Purchase Invoice", "K3LS Debt") for row in receipts), "receipts", None)])
        overdue_bills = {row["name"] for row in payable if row["overdue"] and row["type"] == "Purchase Invoice"}
        overdue_intakes = rows("intake", ["name", "purchase_invoice"], {"status": "Posted"})
        overdue_intakes = [row for row in overdue_intakes if row.purchase_invoice in overdue_bills]
        intake_pieces = frappe.get_all("K3LS Intake Product", filters={"parent": ["in", [row.name for row in overdue_intakes]]}, fields=["quantity"]) if overdue_intakes else []
        group("Restock follow-up", [("Overdue supplier pieces", sum(row.quantity for row in intake_pieces), "intake", None)])
        drilldowns["Overdue supplier pieces"] = [row.name for row in overdue_intakes]
        agreements = rows("owner-stock", ["name", "item", "ownership", "agreement", "due_date", "supplier"], {"status": "Available"})
        from moniepoint_pos.products import stock_state, shop_warehouse
        place = shop_warehouse()
        group("Owner stock", [("Sister-owned pieces", sum(max(0, stock_state(row.item, place)["quantity"]) for row in agreements if row.ownership == "Sister Owned"), "owner-stock", None),
            ("Other-owner pieces", sum(max(0, stock_state(row.item, place)["quantity"]) for row in agreements if row.ownership == "Third-party Owner"), "owner-stock", None),
            ("Owner payouts due", sum(row["amount"] for row in payable if row["type"] == "K3LS Owner Stock"), "owner-stock", "NGN"),
            ("Overdue owner payouts", sum(row["amount"] for row in payable if row["type"] == "K3LS Owner Stock" and row["overdue"]), "owner-stock", "NGN"),
            ("Missing owner payout dates", sum(not row.due_date for row in agreements), "owner-stock", None),
            ("Incomplete owner agreements", sum(not row.agreement or not row.supplier for row in agreements), "owner-stock", None),
            ("Owner payments to check", sum(row.status == "Pending" and row.reference_type == "K3LS Owner Stock" for row in receipts), "receipts", None)])
        delivery_names = rows("deliveries", ["name", "invoice"], {"status": ["in", ["Dispatched", "Delivered"]]})
        group("Deliveries and access", [("Unpaid delivery charges", sum(row["amount"] for row in receivable if row["name"] in {delivery.invoice for delivery in delivery_names}), "deliveries", "NGN"),
            ("Access reviews due", len(rows("controls", ["name"], {"next_review": ["<=", today()], "status": "Done"})), "controls", None)])
        missing_ownership = frappe.get_list("Item", filters={"disabled": 0, "custom_k3ls_ownership": ["in", ["Sister Owned", "Third-party Owner"]],
            "custom_k3ls_owner_stock": ["is", "not set"]}, fields=["name", "item_name"], limit_page_length=0)
        owner_income = Decimal(0)
        for parent, child in (("POS Invoice", "POS Invoice Item"), ("Sales Invoice", "Sales Invoice Item")):
            filters = {"company": COMPANY, "docstatus": 1}
            if parent == "Sales Invoice":
                filters["is_consolidated"] = 0
            sales = frappe.get_list(parent, filters=filters, pluck="name", limit_page_length=0)
            if sales:
                lines = frappe.get_all(child, filters={"parent": ["in", sales], "custom_k3ls_owner_stock": ["is", "set"]},
                    fields=["base_net_amount", "stock_qty", "custom_k3ls_owner_due"])
                owner_income += sum((Decimal(str(row.base_net_amount or 0)) - Decimal(str(row.stock_qty or 0)) * Decimal(str(row.custom_k3ls_owner_due or 0)) for row in lines), Decimal(0))
        group("Owner controls", [("Third-party gross margin to date", float(owner_income), "owner-stock", "NGN"),
            ("Products missing owner agreements", len(missing_ownership), "inventory", None)])
        sales_exceptions = []
        for parent in ("POS Invoice", "Sales Invoice"):
            filters = {"company": COMPANY, "docstatus": 1, "is_return": 0}
            if parent == "Sales Invoice":
                filters["is_consolidated"] = 0
            for sale in frappe.get_list(parent, filters=filters, fields=["name", "customer", "contact_mobile", "outstanding_amount", "due_date"], limit_page_length=0):
                if sale.outstanding_amount > 0 and (sale.customer == "K3LS Walk-in Customer" or not sale.contact_mobile or not sale.due_date):
                    sales_exceptions.append(dict(type=parent, name=sale.name))
        group("Sales review", [("Incomplete unpaid sale details", len(sales_exceptions), "receivables", None)])
        drilldowns.update({
            "Customers owe": [row["name"] for row in receivable],
            "Overdue customer balances": [row["name"] for row in receivable if row["overdue"]],
            "Overdue customers": [row["name"] for row in receivable if row["overdue"]],
            "Supplier and other bills": [row["name"] for row in payable],
            "Overdue bills": [row["name"] for row in payable if row["overdue"]],
            "Overdue suppliers": [row["name"] for row in payable if row["overdue"]],
            "Overdue instalments": [row.name for row, summary in zip(plan_rows, summaries) if summary["overdue"]],
            "Follow-ups due": [row.name for row in plan_rows if row.next_follow_up and getdate(row.next_follow_up) <= getdate(today())],
            "Outside payment plans": [row["name"] for row in balances if row["unplanned_amount"]],
            "Supplier payments to check": [row.name for row in receipts if row.status == "Pending" and row.reference_type in ("Purchase Invoice", "K3LS Debt")],
            "Sister-owned pieces": [row.name for row in agreements if row.ownership == "Sister Owned"],
            "Other-owner pieces": [row.name for row in agreements if row.ownership == "Third-party Owner"],
            "Owner payouts due": [row["name"] for row in payable if row["type"] == "K3LS Owner Stock"],
            "Overdue owner payouts": [row["name"] for row in payable if row["type"] == "K3LS Owner Stock" and row["overdue"]],
            "Missing owner payout dates": [row.name for row in agreements if not row.due_date],
            "Incomplete owner agreements": [row.name for row in agreements if not row.agreement or not row.supplier],
            "Owner payments to check": [row.name for row in receipts if row.status == "Pending" and row.reference_type == "K3LS Owner Stock"],
            "Unpaid delivery charges": [row.name for row in delivery_names if any(balance["name"] == row.invoice for balance in receivable)],
            "Access reviews due": [row.name for row in rows("controls", ["name"], {"next_review": ["<=", today()], "status": "Done"})],
            "Products missing owner agreements": [row.name for row in missing_ownership],
            "Incomplete unpaid sale details": [row["name"] for row in sales_exceptions],
        })
        reports = [dict(title=title, name=name) for title, name in [("Stock report", "Stock Balance"), ("Stock history", "Stock Ledger"),
            ("Customer balances", "Accounts Receivable"), ("Supplier balances", "Accounts Payable"), ("Profit report", "Profit and Loss Statement"),
            ("Sales report", "Sales Register"), ("Restock report", "Purchase Register")]]
    for category in groups:
        for metric in category["metrics"]:
            if metric["title"] in drilldowns:
                metric["names"] = sorted(set(drilldowns[metric["title"]]))
    return dict(groups=groups, reports=reports, owner=owner(), as_of=today())


@frappe.whitelist(methods=["GET"])
def export_review():
    access(True)
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Section", "Measure", "Value", "Currency"])
    data = review()
    for group in data["groups"]:
        for metric in group["metrics"]:
            writer.writerow([data["as_of"], group["title"], metric["title"], metric["value"], metric["currency"] or ""])
    return {"csv": output.getvalue()}


def configuration_snapshot():
    """Installer rollback saves navigation and settings, not business records."""
    frappe.only_for("Administrator")
    properties = []
    for name in ("custom_k3ls_final_condition", "custom_k3ls_inspection_required"):
        properties.append(dict(field_name=name, existing=frappe.get_all("Property Setter", filters={"doc_type": "Item", "field_name": name, "property": "read_only"}, fields=["*"])))
    return {"revision": frappe.db.get_default("k3ls_operations_revision"), "properties": properties,
        "sidebars": [frappe.get_doc("Workspace Sidebar", name).as_dict() for name in ("K3LS Shop", "K3LS Owner") if frappe.db.exists("Workspace Sidebar", name)]}


def restore_configuration(snapshot_path):
    import json
    from pathlib import Path
    frappe.only_for("Administrator")
    path = Path(snapshot_path).resolve(strict=True)
    if not path.is_relative_to(Path("/opt/k3ls/updates").resolve()) or path.name != "operations-before.json":
        frappe.throw("Choose the saved workflow settings snapshot.")
    data = json.loads(path.read_text())
    for property in data.get("properties", []):
        for name in frappe.get_all("Property Setter", filters={"doc_type": "Item", "field_name": property["field_name"], "property": "read_only"}, pluck="name"):
            frappe.delete_doc("Property Setter", name)
        for previous in property["existing"]:
            frappe.get_doc(previous).insert(ignore_permissions=True)
    for previous in data["sidebars"]:
        sidebar = frappe.get_doc("Workspace Sidebar", previous["name"])
        sidebar.set("items", previous["items"])
        sidebar.save()
    frappe.db.set_default("k3ls_operations_revision", data["revision"] or "")
    frappe.clear_cache()
    frappe.db.commit()


def configuration_status():
    frappe.only_for("System Manager")
    missing = []
    for name, definition in SCHEMAS.items():
        if not frappe.db.exists("DocType", name):
            missing.append(name)
            continue
        meta = frappe.get_meta(name, cached=False)
        for field in definition["fields"]:
            actual = meta.get_field(field["fieldname"])
            if not actual or actual.fieldtype != field["fieldtype"] or actual.permlevel != field.get("permlevel", 0) or (field.get("options") and actual.options != field["options"]):
                missing.append(name + "." + field["fieldname"])
        if not definition["child"]:
            expected_roles = {"System Manager"} | (set(("Sales User", "K3LS Repair Staff")) if definition["staff"] else set())
            actual_roles = {row.role for row in meta.permissions if row.permlevel == 0 and row.read}
            if actual_roles != expected_roles:
                missing.append(name + ".permissions")
            if definition["staff"] and any(row.role != "System Manager" and row.permlevel > 0 and (row.read or row.write) for row in meta.permissions):
                missing.append(name + ".financial_permissions")
    if not frappe.db.exists("Page", "shop-operations"):
        missing.append("shop-operations")
    else:
        page = frappe.get_doc("Page", "shop-operations")
        if {row.role for row in page.roles} != {"System Manager", "Sales User", "K3LS Repair Staff"}:
            missing.append("shop-operations.roles")
    for sidebar_name in ("K3LS Shop", "K3LS Owner"):
        if not frappe.db.exists("Workspace Sidebar", sidebar_name):
            missing.append(sidebar_name)
            continue
        sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
        labels = {row.label for row in sidebar.items if row.link_to == "shop-operations"}
        expected = {"Receive stock", "Stock movements", "Requests", "Returns"}
        if sidebar_name == "K3LS Owner":
            expected |= {"Money we owe", "Owner review"}
        missing.extend(sidebar_name + "." + label for label in sorted(expected - labels))
    for doctype, fields in {
        "Item": ["custom_k3ls_mode", "custom_k3ls_repair_cost", "custom_k3ls_inspection_required", "custom_k3ls_owner_stock"],
        "POS Invoice Item": ["custom_k3ls_unit_cost", "custom_k3ls_owner_due", "custom_k3ls_owner_due_date"],
        "Sales Invoice Item": ["custom_k3ls_unit_cost", "custom_k3ls_owner_due", "custom_k3ls_owner_due_date"],
        "K3LS Repair": ["custom_k3ls_cost_bill"],
    }.items():
        meta = frappe.get_meta(doctype, cached=False)
        missing.extend(doctype + "." + field for field in fields if not meta.has_field(field))
    return {"revision": frappe.db.get_default("k3ls_operations_revision"),
        "ready": frappe.db.get_default("k3ls_operations_revision") == "20261004-9" and not missing,
        "workflow_types": len(SCHEMAS), "missing": missing}


@frappe.whitelist(methods=["GET"])
def dashboard():
    access()
    counts = {}
    for kind, name in TYPES.items():
        if kind == "audit" or not frappe.has_permission(name, "read"):
            continue
        filters = {} if owner() else {"owner": frappe.session.user}
        if frappe.get_meta(name).has_field("status"):
            filters["status"] = ["in", ["Pending", "Open", "Active", "Sent", "Dispatched"]]
        rows = frappe.get_list(name, filters=filters, fields=[{"COUNT": "name", "as": "count"}], order_by=None)
        counts[kind] = cint(rows[0].count) if rows else 0
    if owner():
        from moniepoint_pos.ops_money import overview
        counts["money"] = overview()
    return {"counts": counts, "owner": owner(), "as_of": today()}
