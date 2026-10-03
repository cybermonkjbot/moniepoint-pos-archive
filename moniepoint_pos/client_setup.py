"""Idempotent K3LS master configuration. Does not post opening balances."""
import frappe


def configure():
    frappe.only_for("System Manager")
    company = frappe.get_doc("Company", "K3LS LIMITED")
    abbr = company.abbr
    created = []
    stock_settings = frappe.get_single("Stock Settings")
    stock_settings.enable_serial_and_batch_no_for_item = 1
    stock_settings.save()

    def ensure(doctype, name, values):
        if not frappe.db.exists(doctype, name):
            doc = frappe.get_doc({"doctype": doctype, **values}).insert()
            created.append(f"{doctype}: {doc.name}")
            return doc.name
        return name

    warehouse = ensure("Warehouse", f"Shop - {abbr}", {
        "warehouse_name": "Shop", "company": company.name,
        "parent_warehouse": f"All Warehouses - {abbr}",
    })
    for group in ("Laptop", "Accessories", "Repair Services", "Dispatch Services"):
        ensure("Item Group", group, {"item_group_name": group, "parent_item_group": "All Item Groups"})
    ensure("Supplier", "Goshen Global Connect", {
        "supplier_name": "Goshen Global Connect", "supplier_type": "Company",
        "supplier_group": "All Supplier Groups",
    })
    price_list = ensure("Price List", "K3LS Retail NGN", {
        "price_list_name": "K3LS Retail NGN", "currency": "NGN", "selling": 1, "enabled": 1,
    })
    for bank in ("Moniepoint MFB", "FCMB", "Sterling", "UBA"):
        account = ensure("Account", f"{bank} - {abbr}", {
            "account_name": bank, "company": company.name,
            "parent_account": f"Bank Accounts - {abbr}", "account_type": "Bank",
        })
        ensure("Mode of Payment", bank, {"mode_of_payment": bank, "type": "Bank",
            "accounts": [{"company": company.name, "default_account": account}]})
    ensure("Customer Group", "K3LS Retail", {"customer_group_name": "K3LS Retail", "parent_customer_group": "All Customer Groups"})
    ensure("Territory", "K3LS Shop", {"territory_name": "K3LS Shop", "parent_territory": "All Territories"})
    ensure("Customer", "K3LS Walk-in Customer", {"customer_name": "K3LS Walk-in Customer",
        "customer_type": "Individual", "customer_group": "K3LS Retail", "territory": "K3LS Shop"})
    ensure("POS Profile", "K3LS Shop", {
        "name": "K3LS Shop", "company": company.name, "country": "Nigeria", "currency": "NGN",
        "warehouse": warehouse, "customer": "K3LS Walk-in Customer", "selling_price_list": price_list,
        "write_off_account": company.write_off_account, "write_off_cost_center": company.cost_center,
        "cost_center": company.cost_center, "income_account": company.default_income_account,
        "expense_account": company.default_expense_account, "update_stock": 1,
        "allow_partial_payment": 1,
        "payments": [{"mode_of_payment": "Cash", "default": 1}, {"mode_of_payment": "Moniepoint MFB"}],
    })
    for number in range(2, 12):
        code = f"K3LS-ITM-{number:04d}"
        branded = number <= 6
        name = "MIKUSO MOSW115 mouse" if branded else "Unbranded wireless mouse"
        ensure("Item", code, {"item_code": code, "item_name": name, "item_group": "Accessories",
            "stock_uom": "Nos", "is_stock_item": 1,
            "description": name + ". One physical unit. Supplier, purchase date and payment details pending."})
        if not frappe.db.exists("Item Price", {"item_code": code, "price_list": price_list}):
            frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": price_list,
                "currency": "NGN", "price_list_rate": 10000 if branded else 8500}).insert()
    ensure("Item", "K3LS-ITM-0001", {"item_code": "K3LS-ITM-0001", "item_name": "Microsoft Surface Book 2",
        "item_group": "Laptop", "stock_uom": "Nos", "is_stock_item": 1, "has_serial_no": 1,
        "description": "Serial 010988293157. Intel Core i7-8650U, 16 GB RAM, 512 GB nominal storage, GTX 1050 2 GB, silver. Workbook records a broken screen. Final condition and source need confirmation."})
    if not frappe.db.exists("Item Price", {"item_code": "K3LS-ITM-0001", "price_list": price_list}):
        frappe.get_doc({"doctype": "Item Price", "item_code": "K3LS-ITM-0001", "price_list": price_list,
            "currency": "NGN", "price_list_rate": 450000}).insert()
    for code, title, group in (("K3LS-REPAIR", "Repair service", "Repair Services"),
                              ("K3LS-DISPATCH", "Dispatch service", "Dispatch Services")):
        ensure("Item", code, {"item_code": code, "item_name": title, "item_group": group,
            "stock_uom": "Nos", "is_stock_item": 0})
    frappe.db.commit()
    return {"company": company.name, "pos_profile": "K3LS Shop", "created": created,
            "opening_stock_posted": False, "opening_balances_posted": False}
