"""Additive shop workflow schema. No balances, stock or client masters are imported."""
import frappe


def field(name, label, kind="Data", options=None, **values):
    return dict(fieldname=name, label=label, fieldtype=kind, **({"options": options} if options else {}), **values)


def link(name, label, target, **values):
    return field(name, label, "Link", target, **values)


def cash(name, label, **values):
    return field(name, label, "Currency", "NGN", **values)


def choice(name, label, options, **values):
    return field(name, label, "Select", "\n".join(options), **values)


def table(name, label, target):
    return field(name, label, "Table", target, reqd=1)


OWNER = "System Manager"
STAFF = ("Sales User", "K3LS Repair Staff")
SCHEMAS = {}


def schema(name, prefix, fields, staff=False, child=False):
    SCHEMAS[name] = dict(prefix=prefix, fields=fields, staff=staff, child=child)


schema("K3LS Intake Product", "", [link("item", "Product", "Item"), field("product_name", "New product name"),
    link("category", "Category", "Item Group"), field("model", "Model"), field("specifications", "Specifications", "Small Text"),
    field("mode", "Mode"), field("colour", "Colour"), field("serials", "Serial numbers", "Small Text"),
    field("quantity", "Pieces", "Int", default=1, reqd=1), cash("cost", "Purchase cost per piece"),
    cash("delivery_cost", "Delivery cost per piece"), cash("selling_price", "Selling price per piece"),
    field("condition", "Condition when received", "Small Text", reqd=1),
    choice("testing", "Testing", ["Not tested", "Partly tested", "Fully tested"], default="Not tested", reqd=1),
    cash("owner_payout", "Owner payout per piece"), link("registered_item", "Registered product", "Item", read_only=1),
    link("owner_stock", "Owner agreement", "K3LS Owner Stock", read_only=1)], child=True)
schema("K3LS Stock Intake", "K3LS-IN-.#####", [link("supplier", "Supplier or owner", "Supplier", reqd=1),
    choice("source_type", "Source", ["Business supplier", "Individual seller", "Customer purchase", "Trade-in", "Opening stock"], reqd=1),
    choice("ownership", "Stock belongs to", ["K3LS Owned", "Sister Owned", "Third-party Owner"], default="K3LS Owned", reqd=1),
    field("source_phone", "Phone"), field("source_address", "Address", "Small Text"), field("source_reference", "Receipt or agreement", reqd=1),
    field("received_on", "Date received", "Date", reqd=1), field("due_date", "Pay by", "Date"),
    choice("arrangement", "Where kept", ["Held at K3LS", "On demand", "Sister space"], default="Held at K3LS"),
    table("products", "Products", "K3LS Intake Product"), field("notes", "Notes", "Small Text"),
    field("evidence", "Receipt or photo", "Attach"), link("purchase_invoice", "Restock bill", "Purchase Invoice", read_only=1),
    link("stock_entry", "Stock record", "Stock Entry", read_only=1),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Posted"], default="Pending", read_only=1),
    link("reviewed_by", "Reviewed by", "User", read_only=1), field("reviewed_at", "Reviewed at", "Datetime", read_only=1),
    field("review_notes", "Decision", "Small Text", read_only=1)], staff=True)
schema("K3LS Owner Stock", "K3LS-OWN-.#####", [link("item", "Product", "Item", reqd=1),
    link("supplier", "Owner", "Supplier", reqd=1), link("intake", "Stock intake", "K3LS Stock Intake"),
    choice("ownership", "Owner type", ["Sister Owned", "Third-party Owner"], reqd=1),
    choice("arrangement", "Where kept", ["Held at K3LS", "On demand", "Sister space"], reqd=1),
    field("phone", "Phone"), field("address", "Address", "Small Text"), field("agreement", "Agreement", reqd=1),
    field("quantity", "Pieces", "Int", reqd=1), cash("payout_per_piece", "Payout per piece", reqd=1),
    field("due_date", "Pay owner by", "Date", reqd=1), choice("status", "Status", ["Available", "Returned", "Owner direct sale", "Closed"], default="Available"),
    cash("amount_due", "Owner amount due", read_only=1), cash("amount_paid", "Owner paid", read_only=1),
    field("closed_on", "Closed on", "Date", read_only=1), field("notes", "Notes", "Small Text")])
schema("K3LS Stock Inspection", "K3LS-CHK-.#####", [link("item", "Product", "Item", reqd=1),
    field("serials", "Serial numbers", "Small Text"), field("received_on", "Date received", "Date", reqd=1),
    choice("testing", "Testing on arrival", ["Not tested", "Partly tested", "Fully tested"], reqd=1),
    choice("operating_status", "Condition on arrival", ["Unable to assess", "Working", "Working with faults", "Not working"], reqd=1),
    *[field(key, label, "Check") for key, label in [("bios", "BIOS issue"), ("no_ram", "No RAM"), ("no_storage", "No storage"),
      ("broken_screen", "Broken screen"), ("screen", "Screen not working"), ("keyboard", "Keyboard"), ("trackpad", "Trackpad"),
      ("battery", "Battery"), ("speaker", "Speakers"), ("no_power", "No power")]],
    field("faults", "Other faults", "Small Text"), field("quantity", "Pieces checked", "Int", default=1, reqd=1),
    link("inspected_by", "Checked by", "User", read_only=1), field("fix_date", "Date fixed", "Date"),
    cash("parts_cost", "Parts cost"), cash("labour_cost", "Labour cost"), cash("other_cost", "Other cost"),
    cash("total_cost", "Total fixing cost", read_only=1), link("repairer", "Repairer", "Supplier"),
    field("work_done", "Work done", "Small Text"), field("evidence", "Work evidence", "Attach"),
    field("final_condition", "Condition now", "Small Text"), field("verified_on", "Date verified", "Date"),
    link("verified_by", "Verified by", "User", read_only=1),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Posted"], default="Pending", read_only=1),
    link("expense_bill", "Repair bill", "Purchase Invoice", read_only=1), field("notes", "Notes", "Small Text")], staff=True)
schema("K3LS Stock Movement", "K3LS-MOV-.#####", [link("item", "Product", "Item", reqd=1),
    field("quantity", "Pieces", "Int", default=1, reqd=1), field("serials", "Serial numbers", "Small Text"),
    choice("movement_type", "Movement", ["Transfer", "With repairer", "With agent", "Return to shop", "Return to owner"], reqd=1),
    link("from_warehouse", "From", "Warehouse", reqd=1), link("to_warehouse", "To", "Warehouse", reqd=1),
    field("custodian", "Person holding stock", reqd=1), field("phone", "Phone"), field("expected_return", "Return by", "Date"),
    field("reason", "Reason", "Small Text", reqd=1), field("evidence", "Handover photo", "Attach"),
    link("released_by", "Released by", "User", read_only=1), link("received_by", "Received by", "User", read_only=1),
    field("received_at", "Received at", "Datetime", read_only=1), field("returned_at", "Returned at", "Datetime", read_only=1),
    link("return_movement", "Return record", "K3LS Stock Movement", read_only=1),
    link("stock_entry", "Stock record", "Stock Entry", read_only=1),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Sent", "Received", "Returned", "Settled"], default="Pending", read_only=1)], staff=True)
schema("K3LS Count Product", "", [link("item", "Product", "Item", reqd=1), link("warehouse", "Expected location", "Warehouse", reqd=1),
    field("physical_location", "Found at"), field("expected", "Expected pieces", "Int", read_only=1), field("counted", "Pieces counted", "Int", reqd=1),
    field("stock_token", "Stock version", "Data", hidden=1, read_only=1), field("serials", "Serial numbers found", "Small Text"),
    field("condition", "Condition", "Small Text"), field("note", "Difference or damage", "Small Text"),
    link("adjustment", "Stock correction", "Stock Reconciliation", read_only=1)], child=True)
schema("K3LS Stock Count", "K3LS-CNT-.#####", [field("counted_on", "Date counted", "Date", reqd=1),
    table("products", "Products counted", "K3LS Count Product"), field("evidence", "Count evidence", "Attach"),
    field("notes", "Notes", "Small Text"), link("supervisor", "Approved by", "User", read_only=1),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Posted"], default="Pending", read_only=1)], staff=True)
schema("K3LS Shop Request", "K3LS-REQ-.#####", [choice("request_type", "Request", ["Expense", "Correction", "Cancel", "Write-off", "Missing stock", "Price change", "Refund", "Delete"], reqd=1),
    field("title", "Details", reqd=1), link("item", "Product", "Item"),
    choice("related_doctype", "For", ["", "Item", "Customer", "Supplier", "POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Repair"]),
    field("related_name", "Record", "Dynamic Link", "related_doctype"),
    cash("amount", "Amount"), field("paid_by", "Already paid by"), field("category", "Expense category"), field("reason", "Reason", "Small Text", reqd=1),
    field("evidence", "Receipt or photo", "Attach"), choice("status", "Status", ["Pending", "Approved", "Rejected", "Done"], default="Pending", read_only=1),
    link("reviewed_by", "Reviewed by", "User", read_only=1), field("reviewed_at", "Reviewed at", "Datetime", read_only=1),
    field("decision", "Decision", "Small Text", read_only=1), field("action_reference", "Action record", read_only=1)], staff=True)
schema("K3LS Shop Audit", "K3LS-AUD-.########", [link("actor", "By", "User", read_only=1), field("action", "Action", read_only=1),
    field("record_type", "Record type", read_only=1), field("record_name", "Record", read_only=1),
    field("before_value", "Before", "Long Text", read_only=1), field("after_value", "After", "Long Text", read_only=1),
    field("reason", "Reason", "Small Text", read_only=1), field("approval", "Approval record", read_only=1)])
schema("K3LS Return", "K3LS-RET-.#####", [choice("invoice_type", "Sale type", ["POS Invoice", "Sales Invoice"], reqd=1),
    field("invoice", "Original sale", "Dynamic Link", "invoice_type", reqd=1), link("item", "Product", "Item", reqd=1),
    field("sale_line", "Original product line", reqd=1),
    field("quantity", "Pieces", "Int", default=1, reqd=1), field("serials", "Serial numbers", "Small Text"),
    choice("decision", "Requested outcome", ["Refund", "Exchange", "Repair", "Reject"], reqd=1),
    field("reason", "Reason", "Small Text", reqd=1), field("condition", "Condition returned", "Small Text", reqd=1),
    field("evidence", "Photo or receipt", "Attach"), choice("status", "Status", ["Pending", "Approved", "Rejected", "Done"], default="Pending", read_only=1),
    field("return_invoice", "Return invoice", read_only=1), link("repair", "Repair", "K3LS Repair", read_only=1),
    field("review_notes", "Decision notes", "Small Text", read_only=1)], staff=True)
schema("K3LS Trade In", "K3LS-SWP-.#####", [choice("invoice_type", "Sale type", ["POS Invoice", "Sales Invoice"], reqd=1),
    field("invoice", "Sale", "Dynamic Link", "invoice_type", reqd=1), link("customer", "Customer", "Customer", reqd=1),
    link("intake", "Received stock", "K3LS Stock Intake", reqd=1), cash("credit", "Trade-in value", reqd=1),
    field("agreement", "Agreement", reqd=1), field("evidence", "Evidence", "Attach"),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Done"], default="Pending", read_only=1),
    link("journal", "Settlement", "Journal Entry", read_only=1), field("notes", "Notes", "Small Text")])
schema("K3LS Debt", "K3LS-DEBT-.#####", [choice("direction", "Balance", ["Customer owes us", "We owe supplier"], reqd=1),
    link("customer", "Customer", "Customer"), link("supplier", "Supplier", "Supplier"), field("details", "What is owed for", reqd=1),
    field("incurred_on", "Original date", "Date", reqd=1), field("due_date", "Pay by", "Date", reqd=1), cash("amount", "Original amount", reqd=1),
    field("source_reference", "Original reference", reqd=1), field("evidence", "Evidence", "Attach"),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Posted"], default="Pending", read_only=1),
    link("journal", "Accounting record", "Journal Entry", read_only=1), field("notes", "Notes", "Small Text")])
schema("K3LS Instalment", "", [field("due_date", "Original due date", "Date", reqd=1), cash("amount", "Agreed amount", reqd=1),
    field("promise_date", "Revised promise date", "Date"), cash("paid", "Verified paid", read_only=1), field("notes", "Notes", "Small Text")], child=True)
schema("K3LS Instalment Plan", "K3LS-PLAN-.#####", [choice("reference_type", "Balance type", ["POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Debt", "K3LS Owner Stock"], reqd=1),
    field("reference_name", "Balance record", "Dynamic Link", "reference_type", reqd=1), table("instalments", "Payments", "K3LS Instalment"),
    field("agreement", "Payment agreement", "Small Text", reqd=1), link("collection_owner", "Handled by", "User"),
    field("last_contacted", "Last contacted", "Date"), field("next_follow_up", "Follow up on", "Date"), field("contact_notes", "Contact notes", "Small Text"),
    field("picked_up_on", "Picked up or delivered", "Date"),
    choice("status", "Status", ["Active", "Closed"], default="Active", read_only=1)])
schema("K3LS Receipt", "K3LS-PAY-.#####", [choice("reference_type", "For", ["POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Debt", "K3LS Owner Stock", "K3LS Delivery", "K3LS Shop Request"], reqd=1),
    field("reference_name", "Record", "Dynamic Link", "reference_type", reqd=1),
    cash("amount", "Amount", reqd=1), choice("method", "Account", ["Cash", "Moniepoint MFB", "FCMB", "UBA"], reqd=1),
    field("received_on", "Date", "Date", reqd=1), field("bank_reference", "Payment reference", reqd=1), field("payer", "Paid by"),
    field("evidence", "Receipt or evidence", "Attach"), link("plan", "Payment plan", "K3LS Instalment Plan"), field("instalment", "Instalment ID"),
    link("reversal_of", "Reverse receipt", "K3LS Receipt"),
    choice("status", "Status", ["Pending", "Verified", "Rejected", "Reversed"], default="Pending", read_only=1),
    link("verified_by", "Verified by", "User", read_only=1), field("verified_at", "Verified at", "Datetime", read_only=1),
    field("matched_on", "Bank matched date", "Date"), field("voucher_type", "Payment record type", read_only=1), field("voucher", "Payment record", read_only=1),
    field("notes", "Notes", "Small Text")], staff=True)
schema("K3LS Delivery", "K3LS-DEL-.#####", [link("customer", "Customer", "Customer", reqd=1), field("phone", "Phone", reqd=1),
    field("related_sale", "Sale or repair"), field("pickup", "Pickup", "Small Text", reqd=1), field("destination", "Deliver to", "Small Text", reqd=1),
    field("rider", "Rider", reqd=1), link("rider_supplier", "Rider payment supplier", "Supplier"), field("expected_on", "Deliver by", "Datetime", reqd=1),
    cash("fee", "Delivery charge"), cash("rider_cost", "Rider cost"), cash("other_cost", "Fuel or other cost"),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Dispatched", "Delivered", "Cancelled"], default="Pending", read_only=1),
    field("delivered_at", "Delivered at", "Datetime", read_only=1), field("proof", "Delivery proof", "Attach"),
    link("invoice", "Delivery bill", "Sales Invoice", read_only=1), link("cost_bill", "Rider bill", "Purchase Invoice", read_only=1),
    field("notes", "Notes", "Small Text")], staff=True)
schema("K3LS Account Check", "K3LS-BANK-.#####", [link("account", "Account", "Account", reqd=1),
    field("checked_on", "Date checked", "Date", reqd=1), cash("actual_balance", "Actual balance", reqd=1),
    cash("expected_balance", "Recorded balance", read_only=1), cash("difference", "Difference", read_only=1),
    field("evidence", "Statement or count", "Attach"), field("notes", "Reason or notes", "Small Text"),
    choice("status", "Status", ["Open", "Reviewed"], default="Open", read_only=1)])

schema("K3LS Owner Sale", "K3LS-OS-.#####", [link("owner_stock", "Owner agreement", "K3LS Owner Stock", reqd=1),
    choice("invoice_type", "Sale type", ["POS Invoice", "Sales Invoice"], reqd=1), field("invoice", "Sale", "Dynamic Link", "invoice_type", reqd=1),
    cash("amount", "Owner amount", reqd=1), cash("paid", "Owner paid", read_only=1),
    link("journal", "Settlement", "Journal Entry", read_only=1), field("sale_key", "Sale identity", unique=1, read_only=1),
    choice("status", "Status", ["Posted", "Cancelled"], default="Posted", read_only=1)])

schema("K3LS Stock Unit", "K3LS-UNIT-.#####", [link("item", "Product", "Item", read_only=1),
    field("serial", "Serial number", unique=1, read_only=1), link("intake", "Received stock", "K3LS Stock Intake", read_only=1),
    field("arrival_condition", "Condition when received", "Small Text", read_only=1),
    field("final_condition", "Condition now", "Small Text", read_only=1),
    choice("status", "Status", ["Needs inspection", "Ready", "Sold", "Returned to owner"], default="Needs inspection", read_only=1),
    cash("purchase_cost", "Purchase cost", read_only=1), cash("delivery_cost", "Delivery cost", read_only=1),
    cash("repair_cost", "Fixing cost", read_only=1), field("cost_known", "Cost recorded", "Check", read_only=1, permlevel=1),
    link("inspection", "Last check", "K3LS Stock Inspection", read_only=1), field("sale_type", "Sale type", read_only=1),
    field("sale", "Sale", read_only=1)], staff=True)

schema("K3LS Access Review", "K3LS-ACCESS-.#####", [link("user", "User", "User", reqd=1),
    field("reviewed_on", "Reviewed on", "Date", reqd=1), field("next_review", "Review again on", "Date"),
    choice("outcome", "Decision", ["Keep access", "Change access", "Disable access"], reqd=1),
    field("notes", "Review notes", "Small Text", reqd=1), field("evidence", "Evidence", "Attach"),
    choice("status", "Status", ["Pending", "Approved", "Rejected", "Done"], default="Pending", read_only=1)])

# Server actions protect records; financial fields also stay out of staff APIs and forms.
for _name, _definition in SCHEMAS.items():
    if not _definition["child"] and _name != "K3LS Shop Audit":
        _definition["fields"].append(field("request_key", "Request identity", unique=1, hidden=1, read_only=1))
    for _field in _definition["fields"]:
        if _field["fieldtype"] == "Currency" and _name not in ("K3LS Receipt", "K3LS Shop Request"):
            _field["permlevel"] = 1
        if _name == "K3LS Intake Product" and _field["fieldname"] in ("owner_stock",):
            _field["permlevel"] = 1
SCHEMAS["K3LS Shop Request"]["fields"][0]["options"] += "\nCredit sale"
SCHEMAS["K3LS Shop Request"]["fields"] += [link("expense_journal", "Expense record", "Journal Entry", read_only=1),
    link("payable_account", "Reimbursement account", "Account", read_only=1, permlevel=1)]
SCHEMAS["K3LS Stock Movement"]["fields"].append(link("return_record", "Return stock record", "Stock Entry", read_only=1))
SCHEMAS["K3LS Stock Movement"]["fields"].append(link("receiving_user", "Receiving user", "User"))
SCHEMAS["K3LS Stock Movement"]["fields"] += [link("agent_customer", "Agent customer", "Customer", permlevel=1),
    cash("agreed_amount", "Amount due from agent", permlevel=1), field("settle_by", "Agent pays by", "Date", permlevel=1),
    link("agent_invoice", "Agent sale", "Sales Invoice", read_only=1, permlevel=1)]
SCHEMAS["K3LS Shop Request"]["fields"].append(field("approved_sale", "Approved sale details", "Long Text", hidden=1, read_only=1))
SCHEMAS["K3LS Shop Request"]["fields"].append(field("serials", "Affected serial numbers", "Small Text"))
SCHEMAS["K3LS Owner Stock"]["fields"].append(link("receipt_record", "Received stock record", "Stock Entry", read_only=1))
SCHEMAS["K3LS Owner Stock"]["fields"].append(field("closed_quantity", "Pieces returned or sold by owner", "Int", read_only=1, default=0))
SCHEMAS["K3LS Owner Sale"]["fields"].append(field("due_date", "Original payout date", "Date", read_only=1))
SCHEMAS["K3LS Receipt"]["fields"].append(field("pos_payment", "Till payment identity", hidden=1, read_only=1))
SCHEMAS["K3LS Receipt"]["fields"] += [field("bank_key", "Bank reference identity", unique=1, hidden=1, read_only=1),
    field("checkout_signature", "Checkout details", "Long Text", hidden=1, read_only=1),
    link("checkout_sale", "Checkout sale", "POS Invoice", read_only=1)]
SCHEMAS["K3LS Return"]["fields"] += [link("refund_payment", "Refund payment", "Payment Entry", read_only=1),
    link("offset_journal", "Balance offset", "Journal Entry", read_only=1),
    link("merge_log", "Return accounting", "POS Invoice Merge Log", read_only=1)]
SCHEMAS["K3LS Stock Movement"]["fields"].append(link("repair", "Customer repair", "K3LS Repair"))
SCHEMAS["K3LS Stock Movement"]["fields"][0]["reqd"] = 0
for _df in SCHEMAS["K3LS Stock Movement"]["fields"]:
    if _df["fieldname"] in ("from_warehouse", "to_warehouse"):
        _df["reqd"] = 0
SCHEMAS["K3LS Account Check"]["fields"] += [choice("check_type", "Review", ["Balance check", "Opening balance"], default="Balance check", reqd=1),
    link("opening_journal", "Opening balance record", "Journal Entry", read_only=1)]
SCHEMAS["K3LS Access Review"]["fields"] += [field("access_before", "Previous access", "Long Text", hidden=1, read_only=1),
    field("access_after", "Reviewed access", "Long Text", hidden=1, read_only=1)]
for _df in SCHEMAS["K3LS Stock Unit"]["fields"]:
    if _df["fieldname"] == "status":
        _df["options"] += "\nWritten off\nMissing"
for _df in SCHEMAS["K3LS Receipt"]["fields"]:
    if _df["fieldname"] == "voucher":
        _df["fieldtype"] = "Small Text"


def configure():
    frappe.only_for("System Manager")
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    # Deferred shop-to-shop links avoid cycles between intake and owner agreements.
    deferred = []
    for name, definition in sorted(SCHEMAS.items(), key=lambda entry: not entry[1]["child"]):
        permissions = [{"role": OWNER, "read": 1, "write": 1, "create": 1, "report": 1, "export": 1},
            {"role": OWNER, "permlevel": 1, "read": 1, "write": 1}]
        if name == "K3LS Shop Audit":
            permissions = [{"role": OWNER, "read": 1, "report": 1, "export": 1}]
        elif definition["staff"]:
            permissions += [{"role": role, "read": 1, "write": int(name != "K3LS Stock Unit"), "create": int(name != "K3LS Stock Unit")} for role in STAFF]
        initial = []
        for df in definition["fields"]:
            if df["fieldtype"] == "Link" and df.get("options") in SCHEMAS and not frappe.db.exists("DocType", df["options"]):
                deferred.append((name, dict(df)))
                initial.append(dict(df, fieldtype="Data", options=None))
            else:
                initial.append(dict(df))
        if frappe.db.exists("DocType", name):
            doc = frappe.get_doc("DocType", name)
            if not doc.custom or doc.module != "Moniepoint POS" or bool(doc.istable) != definition["child"]:
                frappe.throw(f"{name} already exists outside the shop. It was not changed.")
            existing = {df.fieldname: df for df in doc.fields}
            for df in initial:
                if df["fieldname"] in existing:
                    existing[df["fieldname"]].update(df)
                else:
                    doc.append("fields", df)
            doc.set("permissions", [] if definition["child"] else permissions)
            doc.save()
        else:
            frappe.get_doc(dict(doctype="DocType", name=name, module="Moniepoint POS", custom=1,
                istable=int(definition["child"]), autoname=definition["prefix"] or None,
                track_changes=int(not definition["child"]), allow_rename=0,
                fields=initial, permissions=[] if definition["child"] else permissions)).insert()
    for name, original in deferred:
        doc = frappe.get_doc("DocType", name)
        doc.get("fields", {"fieldname": original["fieldname"]})[0].update(original)
        doc.save()
    create_custom_fields({
        "Item": [field("custom_k3ls_inspection_required", "Needs inspection", "Check", read_only=1),
                 link("custom_k3ls_owner_stock", "Owner agreement", "K3LS Owner Stock", read_only=1, permlevel=1)],
        "Supplier": [choice("custom_k3ls_source_type", "Source type", ["Supplier", "Individual seller", "Sister owner", "External owner"])],
        "Customer": [choice("custom_k3ls_contact_role", "Buys or sells", ["Buyer", "Seller", "Both"], default="Buyer"),
                     field("custom_k3ls_identity_ref", "Business or identity reference")],
        **{name: [link("custom_k3ls_owner_stock", "Owner agreement", "K3LS Owner Stock", read_only=1, hidden=1, permlevel=1),
                  cash("custom_k3ls_owner_due", "Owner due per piece", read_only=1, hidden=1, permlevel=1),
                  field("custom_k3ls_owner_due_date", "Original owner payout date", "Date", read_only=1, hidden=1, permlevel=1)]
           for name in ("POS Invoice Item", "Sales Invoice Item")},
        "Company": [link("custom_k3ls_reimbursement_account", "Shop reimbursements", "Account", read_only=1)],
        "K3LS Repair": [link("custom_k3ls_cost_bill", "Repairer bill", "Purchase Invoice", read_only=1, permlevel=1)],
        **{name: [field("custom_k3ls_credit_approved", "Credit approved", "Check", read_only=1),
                  link("custom_k3ls_credit_approver", "Credit approved by", "User", read_only=1),
                  link("custom_k3ls_shop_request", "Shop approval", "K3LS Shop Request", read_only=1),
                  link("custom_k3ls_return_case", "Return case", "K3LS Return", read_only=1)]
           for name in ("POS Invoice", "Sales Invoice")}})
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    for doctype, name in (("Item", "custom_k3ls_final_condition"), ("Item", "custom_k3ls_inspection_required")):
        make_property_setter(doctype, name, "read_only", 1, "Check")
    company = frappe.get_doc("Company", "K3LS LIMITED")
    if not company.custom_k3ls_reimbursement_account:
        parent = frappe.db.get_value("Account", {"company": company.name, "is_group": 1, "root_type": "Liability"}, "name")
        if not parent:
            frappe.throw("Set up the company's liability accounts first.")
        account_name = f"Shop reimbursements - {company.abbr}"
        if not frappe.db.exists("Account", account_name):
            account = frappe.get_doc(dict(doctype="Account", company=company.name, account_name="Shop reimbursements", parent_account=parent,
                root_type="Liability", report_type="Balance Sheet", account_currency="NGN", is_group=0)).insert()
        else:
            account = frappe.get_doc("Account", account_name)
            if account.company != company.name or account.root_type != "Liability" or account.is_group:
                frappe.throw("The shop reimbursement account needs owner review.")
        company.custom_k3ls_reimbursement_account = account.name
        company.save()
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-operations", force=True)
    from moniepoint_pos.operations import configure_navigation
    configure_navigation()
    frappe.db.set_default("k3ls_operations_revision", "20261004-9")
    frappe.clear_cache()
    frappe.db.commit()
    return {"workflow_types": list(SCHEMAS), "records_imported": False, "stock_posted": False}


def setup():
    """Apply the product and workflow metadata without a build or business import."""
    frappe.only_for("System Manager")
    from moniepoint_pos import products
    products.configure()
    return configure()
