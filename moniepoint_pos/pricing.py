"""Owner product prices and accounting profit, using ERPNext's existing records."""
from decimal import Decimal, InvalidOperation
from datetime import timedelta

import frappe
from frappe.utils import getdate, now_datetime, today

COMPANY = "K3LS LIMITED"
PROFILE = "K3LS Shop"


def owner_item(name, write=False, modified=None):
    frappe.only_for("System Manager")
    item = frappe.get_doc("Item", name, for_update=write)
    item.check_permission("write" if write else "read")
    if write and (not modified or str(item.modified) != str(modified)):
        frappe.throw("This product changed. Close and reopen it before saving.")
    return item


def shop_price_list():
    profile = frappe.get_doc("POS Profile", PROFILE)
    profile.check_permission("read")
    if profile.company != COMPANY or profile.currency != "NGN":
        frappe.throw("Prices are available for the K3LS NGN shop only.")
    price_list = frappe.get_doc("Price List", profile.selling_price_list)
    price_list.check_permission("read")
    if not price_list.enabled or not price_list.selling or price_list.currency != "NGN":
        frappe.throw("Check the shop's selling price list.")
    return price_list.name


def selling_price(item, price_list):
    candidates = frappe.get_list("Item Price",
        filters={"item_code": item.name, "price_list": price_list, "selling": 1,
                 "currency": "NGN", "uom": item.stock_uom},
        fields=["name", "modified", "price_list_rate", "valid_from", "valid_upto",
                "customer", "supplier", "batch_no", "packing_unit"],
        order_by="valid_from desc, modified desc", limit_page_length=100)
    active = [row for row in candidates if not row.customer and not row.supplier and not row.batch_no
        and (not row.valid_from or getdate(row.valid_from) <= getdate(today()))
        and (not row.valid_upto or getdate(row.valid_upto) >= getdate(today()))
        and (row.packing_unit or 0) in (0, 1)]
    if len(active) > 1:
        frappe.throw("This product has overlapping selling prices. Review its Item Prices first.")
    return active[0] if active else None


def amounts(item, price):
    cost_known = bool(item.get("custom_k3ls_cost_confirmed") or item.get("custom_k3ls_purchase_cost"))
    cost = Decimal(str(item.get("custom_k3ls_purchase_cost") or 0))
    delivery = Decimal(str(item.get("custom_k3ls_landing_cost") or 0))
    repair = Decimal(str(item.get("custom_k3ls_repair_cost") or 0))
    selling = Decimal(str(price.price_list_rate)) if price else None
    total = cost + delivery + repair
    profit = selling - total if selling is not None and cost_known else None
    return {"cost_known": cost_known, "cost_price": float(cost) if cost_known else None,
        "delivery_cost": float(delivery), "repair_cost": float(repair),
        "total_cost": float(total) if cost_known else None,
        "selling_price": float(selling) if selling is not None else None,
        "expected_profit": float(profit) if profit is not None else None}


@frappe.whitelist(methods=["GET"])
def prices(item):
    doc = owner_item(item)
    price_list = shop_price_list()
    price = selling_price(doc, price_list)
    units = []
    if doc.has_serial_no and frappe.db.exists("DocType", "K3LS Stock Unit"):
        for unit in frappe.get_list("K3LS Stock Unit", filters={"item": doc.name, "status": ["in", ["Ready", "Needs inspection"]]},
            fields=["name", "serial", "status", "purchase_cost", "delivery_cost", "repair_cost", "cost_known"], limit_page_length=100):
            unit.total_cost = float(unit.purchase_cost + unit.delivery_cost + unit.repair_cost) if unit.cost_known else None
            unit.profit = float(price.price_list_rate - unit.total_cost) if price and unit.total_cost is not None else None
            units.append(unit)
    return {"item": doc.name, "modified": str(doc.modified), "currency": "NGN", "unit": doc.stock_uom,
        "price_name": price.name if price else None, "price_modified": str(price.modified) if price else None,
        "can_edit": doc.has_permission("write") and frappe.has_permission("Item Price", "write" if price else "create"),
        "devices": units, **amounts(doc, price)}


def money(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(f"Enter a valid {label.lower()}.")
    if not result.is_finite() or result < 0 or result > Decimal("999999999999"):
        frappe.throw(f"{label} must be a valid amount of zero or more.")
    return result.quantize(Decimal("0.01"))


@frappe.whitelist(methods=["POST"])
def save_prices(item, modified, cost_price, delivery_cost, selling_price_value,
                price_name=None, price_modified=None, repair_cost=None):
    doc = owner_item(item, write=True, modified=modified)
    if doc.disabled:
        frappe.throw("This product is stopped. Enable it before changing prices.")
    cost, delivery, sell = money(cost_price, "Cost price"), money(delivery_cost, "Delivery cost"), money(selling_price_value, "Selling price")
    repair = money((doc.get("custom_k3ls_repair_cost") or 0) if repair_cost is None else repair_cost, "Repair cost")
    if sell <= 0:
        frappe.throw("Selling price must be above zero.")
    price_list = shop_price_list()
    current = selling_price(doc, price_list)
    if (current.name if current else None) != (price_name or None):
        frappe.throw("The selling price changed. Close and reopen Prices before saving.")
    if current:
        price = frappe.get_doc("Item Price", current.name, for_update=True)
        price.check_permission("write")
        if not price_modified or str(price.modified) != str(price_modified):
            frappe.throw("The selling price changed. Close and reopen Prices before saving.")
    else:
        frappe.has_permission("Item Price", "create", throw=True)
        price = frappe.get_doc({"doctype": "Item Price", "item_code": doc.name,
            "uom": doc.stock_uom, "price_list": price_list, "currency": "NGN", "valid_from": today()})
    doc.custom_k3ls_purchase_cost = float(cost)
    doc.custom_k3ls_landing_cost = float(delivery)
    doc.custom_k3ls_repair_cost = float(repair)
    doc.custom_k3ls_cost_confirmed = 1
    doc.save()
    price.price_list_rate = float(sell)
    price.save()
    return prices(doc.name)


@frappe.whitelist(methods=["GET"])
def profit(from_date=None, to_date=None):
    frappe.only_for("System Manager")
    frappe.get_doc("Company", COMPANY).check_permission("read")
    frappe.has_permission("GL Entry", "read", throw=True)
    end = getdate(to_date or today())
    start = getdate(from_date or end.replace(day=1))
    if start > end or end > getdate(today()) or (end - start).days > 366:
        frappe.throw("Choose a date range of up to one year, ending today or earlier.")
    filters = frappe._dict(company=COMPANY, filter_based_on="Date Range", periodicity="Monthly",
        period_start_date=str(start), period_end_date=str(end), accumulated_values=0,
        include_default_book_entries=1, presentation_currency="NGN")
    from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import execute
    report = execute(filters)
    summary = report[4]
    has_entries = bool(frappe.get_list("GL Entry", filters={"company": COMPANY, "is_cancelled": 0,
        "posting_date": ["between", [str(start), str(end)]]}, fields=["name"], limit_page_length=1))
    open_pos = frappe.get_list("POS Invoice", filters={"company": COMPANY, "docstatus": 1,
        "consolidated_invoice": ["is", "not set"], "posting_date": ["between", [str(start), str(end)]]},
        fields=["name"], limit_page_length=1)
    product_sales = product_profit(start, end)
    charts = product_sales.pop("charts")
    return {"from_date": str(start), "to_date": str(end), "currency": "NGN",
        "income": summary[0]["value"] if has_entries else None,
        "expenses": summary[1]["value"] if has_entries else None,
        "profit": summary[2]["value"] if has_entries else None,
        "has_entries": has_entries, "unclosed_sales": bool(open_pos), "updated_at": now_datetime().isoformat(),
        "product_sales": product_sales, "repairs": repair_profit(start, end),
        "charts": charts}


def repair_profit(start, end):
    rows = frappe.get_list("K3LS Repair", filters={"status": ["!=", "Cancelled"]},
        fields=["name", "sales_invoice", "total_cost", "custom_k3ls_cost_bill"], limit_page_length=0)
    income, cost, count = Decimal(0), Decimal(0), 0
    for repair in rows:
        if not repair.sales_invoice:
            continue
        bill = frappe.get_doc("Sales Invoice", repair.sales_invoice)
        if bill.docstatus != 1 or not start <= getdate(bill.posting_date) <= end:
            continue
        count += 1
        income += Decimal(str(bill.base_net_total or 0))
        cost += Decimal(str(repair.total_cost or 0))
    return dict(count=count, income=float(income), cost=float(cost), margin=float(income - cost))


def snapshot_sale_costs(doc, method=None):
    """Freeze per-piece costs at submission. Never post a second expense to GL."""
    if doc.company != COMPANY or (doc.doctype == "Sales Invoice" and doc.is_consolidated):
        return
    original = None
    if doc.is_return and doc.return_against:
        original = frappe.get_doc(doc.doctype, doc.return_against)
        if original.company != COMPANY or original.docstatus != 1:
            frappe.throw("Choose a confirmed sale from this shop to return.")
    for row in doc.items:
        row.custom_k3ls_cost_recorded = 0
        row.custom_k3ls_unit_cost = 0
        row.custom_k3ls_unit_repair_cost = 0
        item = frappe.get_cached_doc("Item", row.item_code)
        if not item.is_stock_item:
            continue
        if original:
            source_name = row.get("pos_invoice_item" if doc.doctype == "POS Invoice" else "sales_invoice_item")
            candidates = [source for source in original.items if source.item_code == row.item_code
                and (not source_name or source.name == source_name)]
            if len(candidates) != 1:
                frappe.throw("Choose the original sale line for this returned product.")
            source = candidates[0]
            for field in ("custom_k3ls_cost_recorded", "custom_k3ls_unit_cost", "custom_k3ls_unit_repair_cost"):
                row.set(field, source.get(field) or 0)
        else:
            data = amounts(item, None)
            # Current stock valuation is the purchase/delivery cost for pooled
            # pieces. Device records retain exact acquisition and fixing costs.
            from moniepoint_pos.products import stock_state
            from moniepoint_pos.ops_sales import units_for
            units = units_for(row, item) if frappe.db.exists("DocType", "K3LS Stock Unit") else []
            if units:
                data["cost_known"] = len(units) == abs(int(row.stock_qty)) and all(unit.cost_known for unit in units)
                data["total_cost"] = sum(unit.purchase_cost + unit.delivery_cost + (unit.repair_cost or 0) for unit in units) / len(units)
                data["repair_cost"] = sum(unit.repair_cost or 0 for unit in units) / len(units)
            elif row.warehouse:
                stock = stock_state(item.name, row.warehouse)
                if stock["valuation_rate"]:
                    data["cost_known"] = True
                    data["total_cost"] = stock["valuation_rate"] + data["repair_cost"]
            if row.get("custom_k3ls_owner_stock"):
                data["cost_known"] = True
                data["total_cost"] = row.custom_k3ls_owner_due
                data["repair_cost"] = 0
            if data["cost_known"]:
                row.custom_k3ls_cost_recorded = 1
                row.custom_k3ls_unit_cost = data["total_cost"]
                row.custom_k3ls_unit_repair_cost = data["repair_cost"]


def product_profit(start, end):
    """Submitted product sales, counted once before and after till consolidation."""
    sales, costs, repairs = Decimal(0), Decimal(0), Decimal(0)
    missing, lines = 0, 0
    periods, period_for_date, grouping = profit_periods(start, end)
    products = {}
    for parent, child in (("POS Invoice", "POS Invoice Item"), ("Sales Invoice", "Sales Invoice Item")):
        filters = {"company": COMPANY, "docstatus": 1, "posting_date": ["between", [str(start), str(end)]]}
        if parent == "Sales Invoice":
            filters["is_consolidated"] = 0
        invoices = frappe.get_list(parent, filters=filters, fields=["name", "posting_date"], limit_page_length=0)
        dates = {invoice.name: str(invoice.posting_date) for invoice in invoices}
        names = list(dates)
        if not names:
            continue
        # Parent IDs have passed permission-aware get_list. Child rows cannot be queried independently.
        for row in frappe.get_all(child, filters={"parent": ["in", names], "parenttype": parent, "docstatus": 1},
                fields=["parent", "item_code", "item_name", "stock_qty", "base_net_amount", "custom_k3ls_cost_recorded",
                        "custom_k3ls_unit_cost", "custom_k3ls_unit_repair_cost"]):
            if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
                continue
            lines += 1
            income = Decimal(str(row.base_net_amount or 0))
            qty = Decimal(str(row.stock_qty or 0))
            sales += income
            period = periods[period_for_date[dates[row.parent]]]
            period["sales"] += income
            period["lines"] += 1
            product = products.setdefault(row.item_code, {"item": row.item_code,
                "label": row.item_name or row.item_code, "pieces": Decimal(0)})
            product["pieces"] += qty
            if not row.custom_k3ls_cost_recorded:
                missing += 1
                period["missing_cost_lines"] += 1
                continue
            cost = qty * Decimal(str(row.custom_k3ls_unit_cost or 0))
            costs += cost
            period["costs"] += cost
            repairs += qty * Decimal(str(row.custom_k3ls_unit_repair_cost or 0))
    trend = [{"from_date": period["from_date"], "to_date": period["to_date"],
        "sales": float(period["sales"]),
        "profit": None if period["missing_cost_lines"] else float(period["sales"] - period["costs"]),
        "missing_cost_lines": period["missing_cost_lines"], "has_sales": bool(period["lines"])} for period in periods]
    best_sellers = sorted((product for product in products.values() if product["pieces"] > 0),
        key=lambda product: (-product["pieces"], product["item"]))[:5]
    for product in best_sellers:
        product["pieces"] = float(product["pieces"])
    return {"income": float(sales) if lines else None,
        "costs": float(costs) if lines and not missing else None,
        "profit": float(sales - costs) if lines and not missing else None,
        "repair_cost": float(repairs), "missing_cost_lines": missing, "has_sales": bool(lines),
        "charts": {"grouping": grouping, "trend": trend, "best_sellers": best_sellers,
            "has_sales": bool(lines), "missing_cost_lines": missing}}


def profit_periods(start, end):
    """Use a readable number of buckets, with exact dates for each point."""
    span = (end - start).days + 1
    grouping = "day" if span <= 31 else "week" if span <= 120 else "month"
    periods, date_index = [], {}
    cursor = start
    while cursor <= end:
        if grouping == "month":
            next_date = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            next_date = cursor + timedelta(days=1 if grouping == "day" else 7)
        last = min(next_date - timedelta(days=1), end)
        period = {"from_date": str(cursor), "to_date": str(last), "sales": Decimal(0),
            "costs": Decimal(0), "lines": 0, "missing_cost_lines": 0}
        index = len(periods)
        periods.append(period)
        while cursor <= last:
            date_index[str(cursor)] = index
            cursor += timedelta(days=1)
    return periods, date_index, grouping


def configure():
    frappe.only_for("System Manager")
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"Item": [{"fieldname": "custom_k3ls_cost_confirmed", "fieldtype": "Check",
        "label": "Cost recorded", "permlevel": 1, "hidden": 1,
        "insert_after": "custom_k3ls_landing_cost", "read_only": 1}]})
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-profit", force=True)
    sidebar = frappe.get_doc("Workspace Sidebar", "K3LS Owner")
    if not any(row.link_to == "shop-profit" for row in sidebar.items):
        position = next((index + 1 for index, row in enumerate(sidebar.items) if row.label == "Accounts"), len(sidebar.items))
        sidebar.append("items", {"type": "Link", "label": "Profit", "link_type": "Page",
            "link_to": "shop-profit", "icon": "chart-line", "route_options": frappe.as_json({"sidebar": sidebar.name})}, position=position)
        for index, row in enumerate(sidebar.items, 1):
            row.idx = index
        sidebar.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"prices": "Item Price", "costs": "existing product costs", "profit_page": "shop-profit", "stock_posted": False}
