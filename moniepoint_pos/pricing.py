"""Owner product prices and accounting profit, using ERPNext's existing records."""
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import getdate, now_datetime, today

COMPANY = "K3LS LIMITED"
PROFILE = "K3LS Shop"


def owner_item(name, write=False, modified=None):
    frappe.only_for("System Manager")
    item = frappe.get_doc("Item", name, for_update=write)
    item.check_permission("write" if write else "read")
    if write and (not modified or str(item.modified) != str(modified)):
        frappe.throw("These prices changed. Close and reopen Prices before saving.")
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
    selling = Decimal(str(price.price_list_rate)) if price else None
    profit = selling - cost - delivery if selling is not None and cost_known else None
    return {"cost_known": cost_known, "cost_price": float(cost) if cost_known else None,
        "delivery_cost": float(delivery), "selling_price": float(selling) if selling is not None else None,
        "expected_profit": float(profit) if profit is not None else None}


@frappe.whitelist(methods=["GET"])
def prices(item):
    doc = owner_item(item)
    price_list = shop_price_list()
    price = selling_price(doc, price_list)
    return {"item": doc.name, "modified": str(doc.modified), "currency": "NGN", "unit": doc.stock_uom,
        "price_name": price.name if price else None, "price_modified": str(price.modified) if price else None,
        "can_edit": doc.has_permission("write") and frappe.has_permission("Item Price", "write" if price else "create"),
        **amounts(doc, price)}


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
                price_name=None, price_modified=None):
    doc = owner_item(item, write=True, modified=modified)
    if doc.disabled:
        frappe.throw("This product is stopped. Enable it before changing prices.")
    cost, delivery, sell = money(cost_price, "Cost price"), money(delivery_cost, "Delivery cost"), money(selling_price_value, "Selling price")
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
    return {"from_date": str(start), "to_date": str(end), "currency": "NGN",
        "income": summary[0]["value"] if has_entries else None,
        "expenses": summary[1]["value"] if has_entries else None,
        "profit": summary[2]["value"] if has_entries else None,
        "has_entries": has_entries, "unclosed_sales": bool(open_pos), "updated_at": now_datetime().isoformat()}


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
