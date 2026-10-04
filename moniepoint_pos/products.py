"""Product configurations and piece counts backed by ERPNext stock records."""
from decimal import Decimal, InvalidOperation
import hashlib

import frappe
from frappe.utils import nowtime, today

from moniepoint_pos.pricing import COMPANY, PROFILE, amounts, money, owner_item


def shop_warehouse():
    profile = frappe.get_doc("POS Profile", PROFILE)
    profile.check_permission("read")
    if profile.company != COMPANY or profile.disabled or not profile.warehouse:
        frappe.throw("Check the shop stock location.")
    warehouse = frappe.get_doc("Warehouse", profile.warehouse)
    warehouse.check_permission("read")
    if warehouse.company != COMPANY or warehouse.is_group or warehouse.disabled:
        frappe.throw("Check the shop stock location.")
    return warehouse.name


def piece_count(value):
    try:
        count = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw("Enter the number of pieces.")
    if not count.is_finite() or count < 0 or count != count.to_integral_value() or count > 999999999:
        frappe.throw("Enter a whole number of pieces, zero or more.")
    return int(count)


def stock_state(item, warehouse, locked=False):
    # Writes use current reads after locking Bin, not an older transaction snapshot.
    suffix = " FOR UPDATE" if locked else ""
    bins = frappe.db.sql("SELECT actual_qty, valuation_rate, modified FROM `tabBin` "
        "WHERE item_code=%s AND warehouse=%s" + suffix, (item, warehouse), as_dict=True)
    qty, rate = (bins[0].actual_qty or 0, bins[0].valuation_rate or 0) if bins else (0, 0)
    pending_rows = []
    for table, quantity_field in (("POS Invoice Item", "stock_qty"), ("Packed Item", "qty")):
        pending_rows.extend(frappe.db.sql(f"SELECT child.name, child.{quantity_field} AS qty "
            f"FROM `tab{table}` child JOIN `tabPOS Invoice` invoice ON invoice.name=child.parent "
            "WHERE child.item_code=%s AND child.warehouse=%s AND child.docstatus=1 "
            "AND COALESCE(invoice.consolidated_invoice, '')=''" + suffix, (item, warehouse), as_dict=True))
    pending = sum(row.qty or 0 for row in pending_rows)
    # An absent Bin and a newly created zero Bin represent the same stock version.
    token = hashlib.sha256(frappe.as_json([item, warehouse, qty, rate, sorted((row.name, row.qty) for row in pending_rows)]).encode()).hexdigest()
    return {"quantity": qty - pending, "ledger_quantity": qty, "pending_sales": pending,
        "valuation_rate": rate, "stock_token": token}


@frappe.whitelist(methods=["GET"])
def stock(item):
    doc = owner_item(item)
    if not doc.is_stock_item:
        return {"tracked": False}
    warehouse = shop_warehouse()
    data = stock_state(doc.name, warehouse)
    tracked_serials = bool(doc.has_serial_no or doc.has_batch_no)
    return {"tracked": True, "item": doc.name, "modified": str(doc.modified), "unit": "pieces",
        "can_adjust": not tracked_serials and doc.stock_uom == "Nos" and not doc.disabled
            and doc.has_permission("write") and frappe.has_permission("Stock Reconciliation", "create")
            and frappe.has_permission("Stock Reconciliation", "submit"),
        "serial_tracked": tracked_serials, **data}


@frappe.whitelist(methods=["POST"])
def set_stock(item, modified, stock_token, quantity, reason):
    doc = owner_item(item, write=True, modified=modified)
    if not doc.is_stock_item or doc.disabled or doc.stock_uom != "Nos":
        frappe.throw("Choose an active product sold in pieces.")
    if doc.has_serial_no or doc.has_batch_no:
        frappe.throw("This product tracks individual serial numbers. Use Restock to keep those records.")
    if doc.get("custom_k3ls_ownership") in ("Sister Owned", "Third-party Owner") or doc.is_customer_provided_item:
        frappe.throw("Stock counts can only be changed for shop-owned products.")
    frappe.has_permission("Stock Reconciliation", "create", throw=True)
    frappe.has_permission("Stock Reconciliation", "submit", throw=True)
    quantity = piece_count(quantity)
    reason = str(reason or "").strip()
    if not reason or len(reason) > 500:
        frappe.throw("Add a reason of up to 500 characters.")
    warehouse = shop_warehouse()
    lock_stock(doc.name, warehouse)
    current = stock_state(doc.name, warehouse, locked=True)
    if not stock_token or current["stock_token"] != stock_token:
        frappe.throw("Stock changed. Reopen Stock before saving.")
    if current["pending_sales"]:
        frappe.throw("Close the till before correcting this product's stock count.")
    if quantity == current["quantity"]:
        frappe.throw("The stock count is unchanged.")
    # Preserve existing ledger valuation. Initial stock uses the complete recorded
    # per-piece cost. A count correction never overwrites costs of earlier purchases.
    rate = current["valuation_rate"]
    if quantity and not rate:
        recorded = amounts(doc, None)
        if not recorded["cost_known"]:
            frappe.throw("Record this product's cost in Prices before adding its first stock.")
        rate = recorded["cost_price"] + recorded["delivery_cost"]
    purpose = "Stock Reconciliation" if frappe.db.exists("Stock Ledger Entry", {"company": COMPANY, "is_cancelled": 0}) else "Opening Stock"
    from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
    difference = get_difference_account(purpose, COMPANY)
    if not difference:
        frappe.throw("Set the shop stock adjustment account first.")
    reconciliation = frappe.new_doc("Stock Reconciliation")
    reconciliation.update({"company": COMPANY, "expense_account": difference,
        "cost_center": frappe.get_cached_value("Company", COMPANY, "cost_center"),
        "purpose": purpose, "posting_date": today(), "posting_time": nowtime(),
        "set_posting_time": 1, "items": [{"item_code": doc.name,
            "warehouse": warehouse, "qty": quantity, "valuation_rate": rate,
            "allow_zero_valuation_rate": int(not rate)}]})
    reconciliation.insert()
    reconciliation.submit()
    reconciliation.add_comment("Comment", text=frappe.utils.escape_html(reason))
    return {"stock_record": reconciliation.name, **stock(doc.name)}


def lock_stock(item, warehouse):
    from erpnext.stock.utils import get_bin
    bin_doc = get_bin(item, warehouse)
    frappe.get_doc("Bin", bin_doc.name, for_update=True)


def lock_sale_stock(doc, method=None):
    if doc.company != COMPANY or (doc.doctype == "Sales Invoice" and not doc.update_stock):
        return
    for item, warehouse in sorted({(row.item_code, row.warehouse) for row in doc.items if row.warehouse}):
        if frappe.get_cached_value("Item", item, "is_stock_item"):
            lock_stock(item, warehouse)
            if not doc.is_return and not (doc.doctype == "Sales Invoice" and doc.is_consolidated):
                requested = sum(Decimal(str(row.stock_qty or 0)) for row in doc.items
                    if row.item_code == item and row.warehouse == warehouse)
                available = Decimal(str(stock_state(item, warehouse, locked=True)["quantity"]))
                if requested > available:
                    frappe.throw(f"Not enough stock for {item}. Refresh the products and try again.")


@frappe.whitelist(methods=["POST"])
def add_configuration(item, modified, model, specifications, mode="", colour=""):
    source = owner_item(item, write=True, modified=modified)
    if not source.is_stock_item or source.disabled:
        frappe.throw("Choose an active product.")
    frappe.has_permission("Item", "create", throw=True)
    model, specifications, mode, colour = [str(value or "").strip()
        for value in (model, specifications, mode, colour)]
    if not model or not specifications:
        frappe.throw("Add a model and its specifications.")
    if len(model) > 140 or len(mode) > 140 or len(colour) > 140 or len(specifications) > 2000:
        frappe.throw("Keep model, mode and colour under 140 characters and specifications under 2,000.")
    if frappe.get_list("Item", filters={"item_name": source.item_name, "disabled": 0,
        "custom_k3ls_model": model, "custom_k3ls_configuration": specifications,
        "custom_k3ls_mode": mode, "custom_k3ls_colour": colour}, pluck="name", limit_page_length=1):
        frappe.throw("This configuration already exists. Add pieces to its stock instead.")
    from frappe.model.naming import make_autoname
    code = make_autoname("K3LS-PROD-.#####")
    # Explicit allowlist: no copied serials, barcodes, prices, conditions, stock or acquisition history.
    product = frappe.get_doc({"doctype": "Item", "item_code": code, "naming_series": "STO-ITEM-.YYYY.-",
        "item_name": source.item_name, "item_group": source.item_group, "stock_uom": "Nos",
        "is_stock_item": 1, "is_sales_item": 1, "is_purchase_item": 1, "has_serial_no": 0,
        "has_batch_no": 0, "image": source.image, "custom_k3ls_model": model,
        "custom_k3ls_configuration": specifications, "custom_k3ls_mode": mode,
        "custom_k3ls_colour": colour, "custom_k3ls_ownership": "K3LS Owned"})
    product.insert()
    return {"item": product.name}


def validate_product(doc, method=None):
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        return
    old = doc.get_doc_before_save()
    if frappe.db.get_default("k3ls_operations_revision") and not frappe.flags.get("k3ls_workflow"):
        protected = ("custom_k3ls_inspection_required", "custom_k3ls_owner_stock", "custom_k3ls_final_condition")
        if old and any(doc.get(field) != old.get(field) for field in protected):
            frappe.throw("Use Stock checks or an owner-stock agreement to change verified condition and ownership.")
        if old and any(doc.get(field) != old.get(field) for field in ("custom_k3ls_ownership", "custom_k3ls_owner")):
            frappe.throw("Receive this stock under its owner agreement. Do not change ownership on an existing product.")
        if not old and any(doc.get(field) for field in protected):
            frappe.throw("Receive and check the product before setting its verified condition.")
    for field, label in (("custom_k3ls_purchase_cost", "Cost price"),
        ("custom_k3ls_landing_cost", "Delivery cost"), ("custom_k3ls_repair_cost", "Repair cost")):
        if doc.get(field) is not None:
            doc.set(field, float(money(doc.get(field), label)))


def list_stock(names):
    """Enrich only the product IDs already selected by the permission-aware list."""
    warehouse = shop_warehouse()
    if not names:
        return {}
    counts = dict.fromkeys(names, 0)
    for row in frappe.get_all("Bin", filters={"item_code": ["in", names], "warehouse": warehouse}, fields=["item_code", "actual_qty"]):
        counts[row.item_code] = row.actual_qty or 0
    # Two batched queries mirror POS pending-quantity accounting, including bundles.
    for table, quantity_field in (("POS Invoice Item", "stock_qty"), ("Packed Item", "qty")):
        for row in frappe.db.sql(f"SELECT child.item_code, SUM(child.{quantity_field}) AS qty "
            f"FROM `tab{table}` child JOIN `tabPOS Invoice` invoice ON invoice.name=child.parent "
            "WHERE child.item_code IN %s AND child.warehouse=%s AND child.docstatus=1 "
            "AND COALESCE(invoice.consolidated_invoice, '')='' GROUP BY child.item_code",
                (tuple(names), warehouse), as_dict=True):
            counts[row.item_code] -= row.qty or 0
    return counts


def configure():
    """Add fields and presentation defaults, never import masters or post stock."""
    frappe.only_for("System Manager")
    from moniepoint_pos.shop_ui import enabled
    if not enabled():
        frappe.throw("Set up the K3LS shop first.")
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    create_custom_fields({"Item": [
        {"fieldname": "custom_k3ls_mode", "fieldtype": "Data", "label": "Mode",
            "insert_after": "custom_k3ls_configuration"},
        {"fieldname": "custom_k3ls_repair_cost", "fieldtype": "Currency", "label": "Repair cost",
            "options": "NGN", "permlevel": 1, "insert_after": "custom_k3ls_landing_cost"},
        {"fieldname": "custom_k3ls_cost_confirmed", "fieldtype": "Check", "label": "Cost recorded",
            "hidden": 1, "read_only": 1, "permlevel": 1, "insert_after": "custom_k3ls_repair_cost"}],
        **{doctype: [
            {"fieldname": "custom_k3ls_cost_recorded", "fieldtype": "Check", "label": "Cost recorded",
                "hidden": 1, "read_only": 1, "permlevel": 1, "no_copy": 1, "insert_after": "item_code"},
            {"fieldname": "custom_k3ls_unit_cost", "fieldtype": "Currency", "label": "Total cost per piece",
                "options": "NGN", "hidden": 1, "read_only": 1, "permlevel": 1, "no_copy": 1,
                "insert_after": "custom_k3ls_cost_recorded"},
            {"fieldname": "custom_k3ls_unit_repair_cost", "fieldtype": "Currency", "label": "Repair cost per piece",
                "options": "NGN", "hidden": 1, "read_only": 1, "permlevel": 1, "no_copy": 1,
                "insert_after": "custom_k3ls_unit_cost"}]
            for doctype in ("POS Invoice Item", "Sales Invoice Item")}})
    for doctype, field in (("Item", "barcodes"), ("POS Invoice", "scan_barcode"), ("Purchase Invoice", "scan_barcode")):
        if frappe.get_meta(doctype).has_field(field):
            make_property_setter(doctype, field, "reqd", 0, "Check")
            make_property_setter(doctype, field, "mandatory_depends_on", "", "Data")
    settings = frappe.get_single("POS Settings")
    from erpnext.accounts.doctype.pos_settings.pos_settings import get_search_field_option
    search_fields = {row.fieldname for row in settings.pos_search_fields}
    for field in ("custom_k3ls_model", "custom_k3ls_configuration", "custom_k3ls_mode", "custom_k3ls_colour"):
        if field not in search_fields:
            settings.append("pos_search_fields", {"fieldname": field,
                "field": get_search_field_option(frappe.get_meta("Item").get_field(field))})
    settings.save()
    # Keep the new fields on Details, alongside existing model/specification fields.
    meta = frappe.get_meta("Item", cached=False)
    order = [df.fieldname for df in meta.fields]
    for field, after in (("custom_k3ls_mode", "custom_k3ls_configuration"),
                         ("custom_k3ls_repair_cost", "custom_k3ls_landing_cost")):
        order.remove(field)
        order.insert(order.index(after) + 1, field)
    make_property_setter("Item", None, "field_order", frappe.as_json(order), "Text", for_doctype=True)
    frappe.clear_cache()
    frappe.db.commit()
    return {"piece_counts": True, "repair_cost": True, "stock_posted": False, "existing_sales_changed": False}


def configuration_snapshot():
    """Console-only rollback of existing presentation settings, not stock or prices."""
    frappe.only_for("Administrator")
    fields = {"Item": ["barcodes"], "POS Invoice": ["scan_barcode"], "Purchase Invoice": ["scan_barcode"]}
    setters = []
    for doctype, names in fields.items():
        for name in names:
            for prop in ("reqd", "mandatory_depends_on"):
                setters.append({"doc_type": doctype, "field_name": name, "property": prop,
                    "existing": frappe.get_all("Property Setter", filters={"doc_type": doctype,
                        "field_name": name, "property": prop}, fields=["*"])})
    setters.append({"doc_type": "Item", "field_name": None, "property": "field_order",
        "existing": frappe.get_all("Property Setter", filters={"doc_type": "Item", "property": "field_order"}, fields=["*"])})
    return {"setters": setters, "pos_search_fields": [row.as_dict() for row in frappe.get_single("POS Settings").pos_search_fields]}


def restore_configuration(snapshot_path):
    from pathlib import Path
    import json
    frappe.only_for("Administrator")
    path = Path(snapshot_path).resolve(strict=True)
    if not path.is_relative_to(Path("/opt/k3ls/updates").resolve()) or path.name != "products-before.json":
        frappe.throw("Choose the saved product-settings snapshot.")
    data = json.loads(path.read_text())
    for entry in data["setters"]:
        filters = {key: entry[key] for key in ("doc_type", "field_name", "property")}
        if not entry["field_name"]:
            filters.pop("field_name")
        for name in frappe.get_all("Property Setter", filters=filters, pluck="name"):
            frappe.delete_doc("Property Setter", name)
        for old in entry["existing"]:
            frappe.get_doc(old).insert(ignore_permissions=True)
    settings = frappe.get_single("POS Settings")
    settings.set("pos_search_fields", data["pos_search_fields"])
    settings.save()
    frappe.clear_cache()
    frappe.db.commit()
