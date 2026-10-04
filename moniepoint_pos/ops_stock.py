"""Intake, inspection and custody backed by ERPNext stock and purchase documents."""
from decimal import Decimal

import frappe
from frappe.utils import getdate, now_datetime, nowtime, today

from moniepoint_pos.pricing import COMPANY, money, shop_price_list
from moniepoint_pos.products import lock_stock, piece_count, shop_warehouse, stock_state
from moniepoint_pos.operations import access, audit


def serials(value, qty, item):
    values = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if len(values) != len(set(values)):
        frappe.throw("A serial number is repeated.")
    if item.has_serial_no and len(values) != qty:
        frappe.throw("Add one serial number per piece, each on its own line.")
    if values and not item.has_serial_no:
        frappe.throw("Choose a serial-tracked product for these serial numbers.")
    if item.has_batch_no:
        frappe.throw("Use the original stock form for batch-tracked products.")
    return "\n".join(values)


def warehouse(name):
    doc = frappe.get_doc("Warehouse", name)
    doc.check_permission("read")
    if doc.company != COMPANY or doc.is_group or doc.disabled:
        frappe.throw("Choose an active K3LS stock location.")
    return doc


def validate(doc, old=None):
    if doc.doctype == "K3LS Stock Intake":
        for row in doc.products:
            row.quantity = piece_count(row.quantity)
            if not row.quantity or not (row.item or row.product_name):
                frappe.throw("Each stock line needs a product and at least one piece.")
            for key in ("cost", "delivery_cost", "selling_price", "owner_payout"):
                row.set(key, float(money(row.get(key) or 0, key.replace("_", " "))))
        if doc.ownership != "K3LS Owned" and any(row.cost or row.delivery_cost for row in doc.products):
            frappe.throw("Other-owner stock has an agreed payout, not a K3LS purchase cost.")
        if getdate(doc.received_on) > getdate(today()):
            frappe.throw("Date received cannot be in the future.")
    elif doc.doctype == "K3LS Stock Inspection":
        item = frappe.get_doc("Item", doc.item)
        item.check_permission("read")
        doc.quantity = piece_count(doc.quantity)
        if not doc.quantity:
            frappe.throw("Add the number of pieces checked.")
        doc.total_cost = float(sum(money(doc.get(key) or 0, key.replace("_", " ")) for key in ("parts_cost", "labour_cost", "other_cost")))
        if item.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner") and doc.total_cost:
            frappe.throw("Owner-stock checks cannot charge K3LS fixing costs. Record the owner's agreed repair separately.")
        if doc.testing == "Not tested" and doc.operating_status != "Unable to assess":
            frappe.throw("Untested stock must say Unable to assess.")
        if doc.operating_status == "Working" and any(doc.get(key) for key in ("bios", "no_ram", "no_storage", "broken_screen", "screen", "keyboard", "trackpad", "battery", "speaker", "no_power")):
            frappe.throw("Select Working with faults when a fault is recorded.")
        if not old:
            doc.inspected_by = frappe.session.user
        if doc.total_cost and not doc.fix_date:
            frappe.throw("Add the date fixed for these costs.")
        if doc.fix_date and getdate(doc.fix_date) < getdate(doc.received_on):
            frappe.throw("Fixing cannot happen before arrival.")
        if doc.verified_on and (getdate(doc.verified_on) < getdate(doc.fix_date or doc.received_on) or getdate(doc.verified_on) > getdate(today())):
            frappe.throw("Check the final verification date.")
    elif doc.doctype == "K3LS Stock Movement":
        doc.quantity = piece_count(doc.quantity)
        if doc.repair:
            repair = frappe.get_doc("K3LS Repair", doc.repair)
            repair.check_permission("read")
            if doc.item or doc.quantity != 1 or doc.movement_type != "With repairer" or repair.status in ("Collected", "Cancelled"):
                frappe.throw("Send one open customer repair, without a shop-stock product.")
            if not doc.expected_return or not doc.phone:
                frappe.throw("Add the repairer's phone and return date.")
            return
        if not doc.item or not doc.quantity or not doc.from_warehouse or not doc.to_warehouse or doc.from_warehouse == doc.to_warehouse:
            frappe.throw("Choose different stock locations and at least one piece.")
        warehouse(doc.from_warehouse)
        warehouse(doc.to_warehouse)
        if doc.movement_type == "With agent":
            doc.agreed_amount = float(money(doc.agreed_amount or 0, "Agent amount"))
            if not doc.agent_customer or not doc.agreed_amount or not doc.settle_by:
                if frappe.flags.get("k3ls_workflow_action") in ("approve", "post"):
                    frappe.throw("Add the agent customer, amount and payment date before approving this handover.")
        if doc.movement_type in ("With repairer", "With agent") and not doc.expected_return:
            frappe.throw("Add the expected return date.")
    elif doc.doctype == "K3LS Stock Count":
        seen = set()
        old_rows = {row.name: row for row in old.products} if old else {}
        for row in doc.products:
            key = (row.item, row.warehouse)
            if key in seen:
                frappe.throw("Count each product/location once.")
            seen.add(key)
            warehouse(row.warehouse)
            frappe.get_doc("Item", row.item).check_permission("read")
            row.counted = piece_count(row.counted)
            previous = old_rows.get(row.name)
            if previous and (previous.item, previous.warehouse) == key:
                row.expected, row.stock_token = previous.expected, previous.stock_token
            else:
                state = stock_state(row.item, row.warehouse)
                row.expected, row.stock_token = state["quantity"], state["stock_token"]
            if row.expected != row.counted and not row.note:
                frappe.throw("Add a reason for each count difference.")
    elif doc.doctype == "K3LS Owner Stock":
        doc.quantity = piece_count(doc.quantity)
        doc.payout_per_piece = float(money(doc.payout_per_piece, "Owner payout"))
        if not doc.quantity or not doc.payout_per_piece or not doc.agreement or not doc.due_date:
            frappe.throw("Add pieces, payout, due date and an owner agreement.")


def settle_agent(doc, values):
    if doc.status not in ("Sent", "Received") or doc.movement_type != "With agent":
        frappe.throw("Choose stock currently with an agent.")
    if not doc.agent_customer or not doc.agreed_amount or not doc.settle_by:
        frappe.throw("Add the agent customer, amount and payment due date before approving dispatch.")
    item = frappe.get_doc("Item", doc.item)
    if item.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner"):
        frappe.throw("Owner stock is sold through its POS agreement, not through an agent invoice.")
    bill = frappe.get_doc(dict(doctype="Sales Invoice", company=COMPANY, customer=doc.agent_customer, currency="NGN",
        update_stock=1, due_date=doc.settle_by, custom_k3ls_condition=values.get("condition"),
        items=[dict(item_code=doc.item, qty=doc.quantity, warehouse=doc.to_warehouse, rate=doc.agreed_amount / doc.quantity,
            serial_no=serials(doc.serials, doc.quantity, item), use_serial_batch_fields=int(bool(item.has_serial_no)))],
        remarks="Agent settlement " + doc.name))
    submit(bill)
    doc.agent_invoice, doc.status = bill.name, "Settled"
    doc.save()


def submit(doc):
    doc.insert()
    doc.submit()
    return doc


def stock_entry(items, purpose, reference, posting_date=None):
    company = frappe.get_doc("Company", COMPANY)
    entry = frappe.get_doc(dict(doctype="Stock Entry", company=COMPANY, purpose=purpose, stock_entry_type=purpose,
        posting_date=posting_date or today(), posting_time=nowtime(), set_posting_time=1,
        items=items, remarks=reference, cost_center=company.cost_center))
    return submit(entry)


def product(row, intake):
    if row.item:
        item = frappe.get_doc("Item", row.item, for_update=True)
        item.check_permission("write")
        if item.disabled or not item.is_stock_item or item.stock_uom != "Nos":
            frappe.throw("Choose an active stock product sold in pieces.")
        actual_ownership = item.get("custom_k3ls_ownership") or "K3LS Owned"
        if actual_ownership != intake.ownership:
            frappe.throw("Use a separate product for a different stock owner.")
        if intake.ownership != "K3LS Owned" and item.get("custom_k3ls_owner_stock"):
            frappe.throw("Register a separate product for each owner-stock agreement.")
        return item
    from frappe.model.naming import make_autoname
    code = make_autoname("K3LS-PROD-.#####")
    item = frappe.get_doc(dict(doctype="Item", item_code=code, item_name=row.product_name,
        item_group=row.category or "Accessories", stock_uom="Nos", is_stock_item=1, is_sales_item=1, is_purchase_item=int(intake.ownership == "K3LS Owned"),
        has_serial_no=int(bool(row.serials)), has_batch_no=0, custom_k3ls_model=row.model,
        custom_k3ls_configuration=row.specifications, custom_k3ls_colour=row.colour, custom_k3ls_mode=row.mode,
        custom_k3ls_ownership=intake.ownership, custom_k3ls_owner=intake.supplier,
        is_customer_provided_item=int(intake.ownership != "K3LS Owned")))
    item.insert()
    return item


def price(item, value):
    if value <= 0:
        frappe.throw("Add a selling price above zero.")
    from moniepoint_pos.pricing import selling_price
    name = shop_price_list()
    current = selling_price(item, name)
    record = frappe.get_doc("Item Price", current.name) if current else frappe.get_doc(dict(doctype="Item Price", item_code=item.name, price_list=name, currency="NGN", uom="Nos"))
    record.price_list_rate = value
    record.save()


def post_intake(doc):
    if not doc.evidence:
        frappe.throw("Attach the source receipt or stock evidence before registering it.")
    if not doc.source_phone or not doc.source_address:
        frappe.throw("Add the source phone and address before registering stock.")
    if not doc.due_date:
        frappe.throw("Add the supplier or owner payment due date.")
    location = shop_warehouse()
    items, owner_items, opening_items = [], [], []
    for row in doc.products:
        item = product(row, doc)
        lock_stock(item.name, location)
        serial = serials(row.serials, row.quantity, item)
        row.registered_item = item.name
        state = stock_state(item.name, location)
        if state["pending_sales"]:
            frappe.throw("Close this product's open till sales before receiving another batch.")
        if state["quantity"] and not item.has_serial_no and row.condition != item.get("custom_k3ls_final_condition"):
            frappe.throw("Use a separate product or serial records when incoming pieces have a different condition.")
        # Costs are per configuration. Never overwrite existing valued stock with a new batch's cost.
        if state["ledger_quantity"] == 0 and not state["pending_sales"]:
            item.custom_k3ls_purchase_cost = row.cost
            item.custom_k3ls_landing_cost = row.delivery_cost
            item.custom_k3ls_cost_confirmed = int(doc.ownership == "K3LS Owned")
            item.custom_k3ls_acquired_on = doc.received_on
            item.custom_k3ls_acquisition_type = "Swap / Trade-in" if doc.source_type == "Trade-in" else "Supplier Purchase"
        elif not item.has_serial_no and doc.ownership == "K3LS Owned":
            total_pieces = Decimal(str(state["quantity"] + row.quantity))
            existing = Decimal(str(state["quantity"]))
            purchase_total = existing * Decimal(str(item.get("custom_k3ls_purchase_cost") or 0)) + row.quantity * Decimal(str(row.cost))
            delivery_total = existing * Decimal(str(item.get("custom_k3ls_landing_cost") or 0)) + row.quantity * Decimal(str(row.delivery_cost))
            repair_total = existing * Decimal(str(item.get("custom_k3ls_repair_cost") or 0))
            item.custom_k3ls_purchase_cost = float(purchase_total / total_pieces)
            item.custom_k3ls_landing_cost = float(delivery_total / total_pieces)
            item.custom_k3ls_repair_cost = float(repair_total / total_pieces)
        item.custom_k3ls_arrival_condition = row.condition
        item.custom_k3ls_inspection_required = int(row.testing != "Fully tested" or item.item_group == "Laptop")
        if not item.custom_k3ls_inspection_required:
            item.custom_k3ls_final_condition = row.condition
        if doc.ownership != "K3LS Owned":
            if state["ledger_quantity"] or state["pending_sales"]:
                frappe.throw("Owner-stock agreements need a new product with no previous stock.")
            agreement = frappe.get_doc(dict(doctype="K3LS Owner Stock", item=item.name, supplier=doc.supplier, intake=doc.name,
                ownership=doc.ownership, arrangement=doc.arrangement, phone=doc.source_phone, address=doc.source_address,
                agreement=doc.source_reference, quantity=row.quantity, payout_per_piece=row.owner_payout, due_date=doc.due_date))
            agreement.flags.k3ls_operation = True
            agreement.insert()
            item.is_customer_provided_item = 1
            item.is_purchase_item = 0
            item.valuation_rate = 0
            item.custom_k3ls_owner_stock = agreement.name
            row.owner_stock = agreement.name
            if doc.arrangement != "On demand":
                owner_items.append(dict(item_code=item.name, t_warehouse=location, qty=row.quantity,
                    basic_rate=0, allow_zero_valuation_rate=1, serial_no=serial, use_serial_batch_fields=int(bool(serial))))
        elif doc.source_type == "Opening stock":
            opening_items.append(dict(item_code=item.name, t_warehouse=location, qty=row.quantity, basic_rate=row.cost + row.delivery_cost,
                set_basic_rate_manually=1, serial_no=serial, use_serial_batch_fields=int(bool(serial))))
        else:
            items.append(dict(item_code=item.name, qty=row.quantity, rate=row.cost, warehouse=location,
                serial_no=serial, use_serial_batch_fields=int(bool(serial))))
        if item.has_serial_no:
            for number in serial.splitlines():
                frappe.get_doc(dict(doctype="K3LS Stock Unit", item=item.name, serial=number, intake=doc.name,
                    arrival_condition=row.condition, final_condition=row.condition if not item.custom_k3ls_inspection_required else None,
                    status="Needs inspection" if item.custom_k3ls_inspection_required else "Ready", purchase_cost=row.cost,
                    delivery_cost=row.delivery_cost, repair_cost=0, cost_known=int(doc.ownership == "K3LS Owned"))).insert()
        price(item, row.selling_price)
        item.save()
    if items:
        bill = frappe.get_doc(dict(doctype="Purchase Invoice", company=COMPANY, supplier=doc.supplier, posting_date=doc.received_on,
            due_date=doc.due_date, bill_no=doc.source_reference, bill_date=doc.received_on, currency="NGN", update_stock=1,
            items=items, remarks="Stock intake " + doc.name))
        extra = sum(Decimal(str(row.delivery_cost or 0)) * row.quantity for row in doc.products)
        if extra:
            company = frappe.get_doc("Company", COMPANY)
            bill.append("taxes", dict(charge_type="Actual", account_head=company.default_expense_account,
                description="Delivery included in stock cost", tax_amount=float(extra), category="Valuation and Total", add_deduct_tax="Add"))
        submit(bill)
        doc.purchase_invoice = bill.name
    if owner_items:
        entry = stock_entry(owner_items, "Material Receipt", "Owner-stock intake " + doc.name, posting_date=doc.received_on)
        doc.stock_entry = entry.name
    if opening_items:
        from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
        difference = get_difference_account("Opening Stock", COMPANY)
        if not difference:
            frappe.throw("Set the opening stock account before posting opening stock.")
        for row in opening_items:
            row["expense_account"] = difference
        entry = stock_entry(opening_items, "Material Receipt", "Opening stock intake " + doc.name, posting_date=doc.received_on)
        doc.stock_entry = entry.name
    doc.status = "Posted"
    doc.save()


def post_inspection(doc):
    if not doc.final_condition or not doc.verified_on or not doc.evidence:
        frappe.throw("Add the final condition, verification date and evidence.")
    item = frappe.get_doc("Item", doc.item, for_update=True)
    item.check_permission("write")
    location = shop_warehouse()
    lock_stock(item.name, location)
    state = stock_state(item.name, location, locked=True)
    if state["pending_sales"]:
        frappe.throw("Close this product's open till sales before recording its final check or fixing cost.")
    if doc.quantity != 1 and item.has_serial_no:
        frappe.throw("Record a separate inspection for each serial-tracked device.")
    unit = None
    if item.has_serial_no:
        number = serials(doc.serials, doc.quantity, item)
        name = frappe.db.get_value("K3LS Stock Unit", {"item": item.name, "serial": number}, "name")
        if not name:
            # Historical devices retain their IDs. The inspector explicitly
            # supplies the serial; costs stay unknown if acquisition is missing.
            from moniepoint_pos.pricing import amounts
            costs = amounts(item, None)
            unit = frappe.get_doc(dict(doctype="K3LS Stock Unit", item=item.name, serial=number,
                arrival_condition=item.get("custom_k3ls_arrival_condition"), purchase_cost=costs["cost_price"] or 0,
                delivery_cost=costs["delivery_cost"], repair_cost=costs["repair_cost"], cost_known=int(costs["cost_known"]))).insert()
        else:
            unit = frappe.get_doc("K3LS Stock Unit", name, for_update=True)
        actual = frappe.get_doc("Serial No", number)
        if actual.item_code != item.name or not actual.warehouse or unit.status in ("Sold", "Returned to owner"):
            frappe.throw("Inspect only a device currently held in stock.")
    elif doc.quantity != state["quantity"]:
        frappe.throw("Check every interchangeable piece together, or use separate serial-tracked products for different conditions.")
    if doc.total_cost and (not doc.repairer or not doc.work_done):
        frappe.throw("Add the repairer and work done for these fixing costs.")
    if doc.total_cost:
        from moniepoint_pos.ops_money import service_bill
        doc.expense_bill = service_bill(doc.repairer, doc.total_cost, "Stock fixing " + doc.name, posting_date=doc.fix_date).name
    if unit:
        unit.repair_cost = float(money(unit.repair_cost or 0, "Repair cost") + money(doc.total_cost, "Repair cost"))
        unit.final_condition, unit.inspection, unit.status = doc.final_condition, doc.name, "Ready"
        unit.save()
        item.custom_k3ls_inspection_required = int(bool(frappe.db.exists("K3LS Stock Unit", {"item": item.name, "status": "Needs inspection"})))
    else:
        item.custom_k3ls_repair_cost = float(money(item.get("custom_k3ls_repair_cost") or 0, "Repair cost") + money(doc.total_cost / doc.quantity, "Repair cost"))
        item.custom_k3ls_inspection_required = 0
    item.custom_k3ls_final_condition = doc.final_condition
    item.save()
    doc.verified_by = frappe.session.user
    doc.status = "Posted"
    doc.save()


def post_movement(doc):
    if doc.repair:
        repair = frappe.get_doc("K3LS Repair", doc.repair, for_update=True)
        repair.check_permission("write")
        if frappe.db.exists("K3LS Stock Movement", {"repair": repair.name, "status": ["in", ["Sent", "Received"]]}):
            frappe.throw("This customer repair is already with a repairer. Record its return first.")
        doc.released_by, doc.status = frappe.session.user, "Sent"
        doc.save()
        return
    item = frappe.get_doc("Item", doc.item)
    item.check_permission("read")
    lock_stock(item.name, doc.from_warehouse)
    if stock_state(item.name, doc.from_warehouse, locked=True)["quantity"] < doc.quantity:
        frappe.throw("There are not enough pieces at the source location.")
    serial = serials(doc.serials, doc.quantity, item)
    entry = stock_entry([dict(item_code=item.name, qty=doc.quantity, s_warehouse=doc.from_warehouse, t_warehouse=doc.to_warehouse,
        serial_no=serial, use_serial_batch_fields=int(bool(serial)))], "Material Transfer", "Stock movement " + doc.name)
    doc.stock_entry = entry.name
    doc.released_by = frappe.session.user
    doc.status = "Sent"
    doc.save()


def post_count(doc):
    company = frappe.get_doc("Company", COMPANY)
    purpose = "Stock Reconciliation" if frappe.db.exists("Stock Ledger Entry", {"company": COMPANY, "is_cancelled": 0}) else "Opening Stock"
    from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
    difference = get_difference_account(purpose, COMPANY)
    for row in sorted(doc.products, key=lambda r: (r.item, r.warehouse)):
        if row.counted == row.expected:
            continue
        item = frappe.get_doc("Item", row.item)
        if item.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner"):
            frappe.throw("Resolve missing owner stock with its owner before a count adjustment.")
        lock_stock(row.item, row.warehouse)
        state = stock_state(row.item, row.warehouse, locked=True)
        if state["stock_token"] != row.stock_token or state["pending_sales"]:
            frappe.throw("Stock changed or the till is open. Take a fresh count after closing the till.")
        rate = state["valuation_rate"]
        if row.counted and not rate:
            from moniepoint_pos.pricing import amounts
            prices = amounts(item, None)
            if not prices["cost_known"]:
                frappe.throw("Record product costs before adding opening pieces.")
            rate = prices["cost_price"] + prices["delivery_cost"]
        adjustment = frappe.get_doc(dict(doctype="Stock Reconciliation", company=COMPANY, purpose=purpose,
            expense_account=difference, cost_center=company.cost_center, posting_date=today(), posting_time=nowtime(), set_posting_time=1,
            items=[dict(item_code=row.item, warehouse=row.warehouse, qty=row.counted, valuation_rate=rate,
                serial_no=serials(row.serials, row.counted, item), use_serial_batch_fields=int(bool(item.has_serial_no)), allow_zero_valuation_rate=int(not rate))]))
        submit(adjustment)
        adjustment.add_comment("Comment", text=frappe.utils.escape_html("Count " + doc.name + ": " + row.note))
        row.adjustment = adjustment.name
    doc.status = "Posted"
    doc.save()


def perform(doc, action, values):
    if action == "terms" and doc.doctype == "K3LS Owner Stock":
        access(True)
        if doc.status != "Available" or not values.get("reason"):
            frappe.throw("Choose available owner stock and add a reason for changing its terms.")
        payout = float(money(values.get("payout_per_piece"), "Payout per piece"))
        if not payout or not values.get("due_date") or not values.get("agreement"):
            frappe.throw("Add the payout, payment date and new agreement.")
        doc.payout_per_piece, doc.due_date, doc.agreement = payout, values["due_date"], values["agreement"]
        doc.save()
    elif action == "post":
        access(True)
        if doc.status != "Approved":
            frappe.throw("Approve this record before posting it.")
        functions = {"K3LS Stock Intake": post_intake, "K3LS Stock Inspection": post_inspection,
            "K3LS Stock Movement": post_movement, "K3LS Stock Count": post_count}
        if doc.doctype not in functions:
            frappe.throw("Choose a supported stock action.")
        functions[doc.doctype](doc)
    elif action == "settle-agent" and doc.doctype == "K3LS Stock Movement":
        access(True)
        settle_agent(doc, values)
    elif action == "receive-owner" and doc.doctype == "K3LS Owner Stock":
        access(True)
        if doc.status != "Available" or doc.arrangement != "On demand":
            frappe.throw("Choose available owner stock still kept on demand.")
        item = frappe.get_doc("Item", doc.item)
        location = shop_warehouse()
        lock_stock(item.name, location)
        if stock_state(item.name, location, locked=True)["ledger_quantity"]:
            frappe.throw("This owner stock is already received.")
        numbers = serials(values.get("serials"), doc.quantity, item)
        entry = stock_entry([dict(item_code=item.name, t_warehouse=location, qty=doc.quantity, basic_rate=0,
            allow_zero_valuation_rate=1, serial_no=numbers, use_serial_batch_fields=int(bool(numbers)))], "Material Receipt", "Owner stock received " + doc.name)
        doc.receipt_record, doc.arrangement = entry.name, "Held at K3LS"
        doc.save()
    elif action == "received" and doc.doctype == "K3LS Stock Movement":
        if doc.status != "Sent":
            frappe.throw("Only sent stock can be received.")
        doc.received_by, doc.received_at, doc.status = frappe.session.user, now_datetime(), "Received"
        doc.save()
    elif action == "return" and doc.doctype == "K3LS Stock Movement":
        access(True)
        if doc.status not in ("Sent", "Received"):
            frappe.throw("This stock is not out.")
        if doc.repair:
            doc.returned_at, doc.status = now_datetime(), "Returned"
            doc.save()
            audit(doc, action, reason=values.get("reason"))
            return
        item = frappe.get_doc("Item", doc.item)
        lock_stock(item.name, doc.to_warehouse)
        if stock_state(item.name, doc.to_warehouse, locked=True)["quantity"] < doc.quantity:
            frappe.throw("Not enough pieces remain at the destination.")
        entry = stock_entry([dict(item_code=item.name, qty=doc.quantity, s_warehouse=doc.to_warehouse, t_warehouse=doc.from_warehouse,
            serial_no=serials(doc.serials, doc.quantity, item), use_serial_batch_fields=int(bool(item.has_serial_no)))], "Material Transfer", "Return of " + doc.name)
        doc.return_record = entry.name
        doc.returned_at, doc.status = now_datetime(), "Returned"
        doc.save()
    elif action in ("owner-direct", "return-owner") and doc.doctype == "K3LS Owner Stock":
        access(True)
        if doc.status != "Available":
            frappe.throw("Choose available owner stock.")
        item = frappe.get_doc("Item", doc.item)
        location = shop_warehouse()
        lock_stock(item.name, location)
        state = stock_state(item.name, location, locked=True)
        if state["pending_sales"]:
            frappe.throw("Close the till before returning owner stock.")
        remaining = piece_count(state["quantity"]) if doc.arrangement != "On demand" else doc.quantity
        if not remaining:
            frappe.throw("No pieces remain to return or record as an owner sale.")
        outside = frappe.get_all("Bin", filters={"item_code": item.name, "warehouse": ["!=", location], "actual_qty": ["!=", 0]}, pluck="warehouse")
        if outside:
            frappe.throw("Return stock from other locations before closing this agreement's remaining pieces.")
        numbers = serials(values.get("serials"), remaining, item)
        if state["quantity"]:
            stock_entry([dict(item_code=item.name, qty=remaining, s_warehouse=location,
                serial_no=numbers, use_serial_batch_fields=int(bool(item.has_serial_no)),
                allow_zero_valuation_rate=1)], "Material Issue", "Owner stock closed " + doc.name)
        for record in frappe.get_all("K3LS Stock Unit", filters={"item": item.name, "status": ["in", ["Ready", "Needs inspection"]]}, fields=["name"]):
            unit = frappe.get_doc("K3LS Stock Unit", record.name)
            if item.has_serial_no and unit.serial not in numbers.splitlines():
                continue
            unit.status = "Returned to owner"
            unit.save()
        # Closing unsold pieces does not erase prior K3LS sales or unpaid owner
        # accruals. Those remain collectible in Money we owe.
        doc.closed_quantity = remaining
        doc.status = "Owner direct sale" if action == "owner-direct" else "Returned"
        doc.closed_on = today()
        doc.notes = str(values.get("reason") or doc.notes or "")
        doc.save()
    else:
        frappe.throw("Choose a supported stock action.")
    audit(doc, action, reason=values.get("reason"))
