"""Small-shop presentation. No records, ledger entries or permissions are removed."""
import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.file_manager import save_file


# These fields are hidden only in the form. The owner can reveal their original UI.
FORMS = {
    "Supplier": {
        "hide": "alias gender supplier_group country defaults_section accounting_tab tax_tab settings_tab portal_users_tab more_info_tab".split(),
        "labels": {"supplier_name": "Supplier name", "supplier_type": "Business or person", "contact_and_address_tab": "Contact details", "supplier_details": "Notes", "disabled": "Stop using this supplier", "mobile_no": "Phone", "email_id": "Email", "dashboard_tab": "History"},
        "defaults": {"supplier_group": "All Supplier Groups", "country": "Nigeria"},
        "columns": ["mobile_no", "email_id"], "filters": [],
    },
    "Customer": {
        "hide": "alias gender customer_group territory section_break_hwkr loyalty_points_tab accounting_tab tax_tab settings_tab sales_team_tab portal_users_tab more_info_tab".split(),
        "labels": {"customer_name": "Customer name", "customer_type": "Person or business", "contact_and_address_tab": "Contact details", "customer_details": "Notes", "disabled": "Stop using this customer", "mobile_no": "Phone", "email_id": "Email", "connections_tab": "History"},
        "defaults": {"customer_type": "Individual", "customer_group": "K3LS Retail", "territory": "K3LS Shop"},
        "columns": ["mobile_no", "email_id"], "filters": [],
    },
    "Item": {
        "hide": "is_fixed_asset auto_create_assets is_grouped_asset asset_category asset_naming_series section_break_zlmj section_break_gjns section_break_znra accounting uom_tab variants_section purchasing_tab sales_details manufacturing quality_tab inventory_valuation_section inventory_settings_section reorder_section has_batch_no create_new_batch batch_number_series has_expiry_date shelf_life_in_days retain_sample sample_quantity use_serial_no_wise_valuation serial_no_series".split(),
        "labels": {"item_code": "Item ID", "item_name": "Product name", "item_group": "Category", "stock_uom": "Sold by", "is_stock_item": "Track stock", "inventory_section": "Stock", "pricing_tab": "Prices", "custom_k3ls_device": "Device and condition", "custom_k3ls_acquisition": "Purchase details", "custom_k3ls_purchase_cost": "Purchase cost, NGN", "custom_k3ls_landing_cost": "Delivery cost, NGN", "has_serial_no": "Track serial numbers", "dashboard_tab": "History"},
        "defaults": {"stock_uom": "Nos"},
        "columns": ["item_group"], "filters": ["item_group"], "keep_id": True,
    },
    "K3LS Repair": {
        "hide": ["received_by", "currency"],
        "labels": {"intake_tab": "Device and customer", "progress_tab": "Repair progress", "billing_tab": "Price and payment", "relationship": "New or returning customer", "item": "Shop item", "received_at": "Date received", "expected_ready_date": "Ready by", "fixed_at": "Date repaired", "collected_at": "Date collected", "customer_charge": "Price, NGN", "approval_reference": "Proof of approval", "sales_invoice": "Repair invoice", "agreement_reference": "Payment notes"},
        "defaults": {}, "columns": ["customer", "expected_ready_date"], "filters": ["status", "customer"], "keep_id": True,
    },
    "Purchase Invoice": {
        "hide": "naming_series posting_time currency_and_price_list accounting_dimensions_section is_subcontracted raw_materials_supplied pricing_rule_details subscription_section automation_section printing_settings additional_info_section scan_barcode shipping_rule incoterm use_company_roundoff_cost_center".split(),
        "labels": {"posting_date": "Date", "set_posting_time": "Change date", "due_date": "Pay by", "bill_no": "Supplier invoice number", "bill_date": "Supplier invoice date", "update_stock": "Add these items to stock", "is_paid": "Already paid", "is_return": "Return to supplier", "grand_total": "Total, NGN", "outstanding_amount": "Left to pay, NGN", "address_and_contact_tab": "Contact details", "more_info_tab": "Other details", "credit_to": "Supplier account", "remarks": "Notes"},
        "defaults": {}, "columns": ["posting_date", "grand_total", "outstanding_amount"], "filters": ["posting_date", "status"], "keep_id": True,
    },
    "Payment Entry": {
        "hide": "naming_series book_advance_payments_in_separate_party_account auto_repeat_section accounting_dimensions_section".split(),
        "labels": {"type_of_payment": "Payment", "payment_type": "Money in or out", "posting_date": "Date", "mode_of_payment": "Payment method", "party_section": "Who is paying or receiving?", "party_type": "Customer or supplier", "party": "Name", "party_name": "Name", "payment_accounts_section": "Bank or cash account", "paid_from": "Money from", "paid_to": "Money to", "payment_amounts_section": "Amount", "paid_amount": "Amount paid", "received_amount": "Amount received", "section_break_14": "Invoices being paid", "references": "Invoices", "reference_no": "Payment reference", "reference_date": "Payment date", "transaction_references": "Payment reference", "remarks": "Notes", "unallocated_amount": "Not matched to an invoice", "difference_amount": "Difference", "section_break_12": "Other details"},
        "defaults": {}, "columns": ["posting_date", "payment_type", "paid_amount"], "filters": ["posting_date", "payment_type"], "keep_id": True,
    },
    "POS Invoice": {
        "hide": "naming_series currency_and_price_list packing_list time_sheet_list loyalty_points_redemption customer_po_details utm_analytics_section sales_team_section_break section_break2 subscription_section auto_repeat_section edit_printing_settings".split(),
        "labels": {"customer": "Customer", "posting_date": "Date", "grand_total": "Total, NGN", "outstanding_amount": "Left to pay, NGN", "paid_amount": "Paid, NGN", "change_amount": "Change, NGN", "contact_and_address_tab": "Contact details", "more_info_tab": "Other details", "custom_k3ls_condition": "Condition and faults", "custom_k3ls_tested": "Was it tested?", "custom_k3ls_acknowledged": "Customer accepts the condition", "custom_k3ls_disclosure_ref": "Condition record or receipt number"},
        "defaults": {}, "columns": ["posting_date", "grand_total", "outstanding_amount"], "filters": ["posting_date", "status"], "keep_id": True,
    },
    "Sales Invoice": {
        "hide": "naming_series currency_and_price_list packing_list time_sheet_list loyalty_points_redemption customer_po_details utm_analytics_section sales_team_section_break section_break2 subscription_section auto_repeat_section edit_printing_settings".split(),
        "labels": {"posting_date": "Date", "grand_total": "Total, NGN", "outstanding_amount": "Left to pay, NGN", "contact_and_address_tab": "Contact details", "more_info_tab": "Other details", "remarks": "Notes"},
        "defaults": {}, "columns": ["posting_date", "grand_total", "outstanding_amount"], "filters": ["posting_date", "status"], "keep_id": True,
    },
    "POS Profile": {
        "hide": "__details country disabled company customer warehouse company_address pos_configurations_tab more_info_tab print_receipt_on_order_complete utm_analytics_section accounting_dimensions_section set_grand_total_to_default_mop price_list_and_currency_section write_off_section income_and_expense_account taxes_section section_break_19 pos_item_selector_section pos_item_details_section section_break_15 section_break_23 action_on_new_invoice validate_stock_on_save update_stock ignore_pricing_rule hide_images hide_unavailable_items auto_add_item_to_cart allow_rate_change allow_discount_change applicable_for_users item_groups customer_groups".split(),
        "labels": {"accounting_tab": "Payments", "pos_configurations_tab": "Receipt", "more_info_tab": "Receipt layout", "customer": "Walk-in customer", "warehouse": "Stock location", "applicable_for_users": "Users", "hide_images": "Hide product photos", "auto_add_item_to_cart": "Add items with one click", "allow_rate_change": "Allow price changes", "allow_discount_change": "Allow discounts", "validate_stock_on_save": "Check stock before saving", "selling_price_list": "Selling prices", "print_format": "Receipt layout", "print_receipt_on_order_complete": "Print after sale", "allow_partial_payment": "Allow part payments", "account_for_change_amount": "Cash account for change"},
        "defaults": {}, "columns": ["warehouse"], "filters": [],
    },
    "Moniepoint Settings": {
        "hide": [],
        "labels": {"enabled": "Use Moniepoint", "api_key": "Moniepoint connection key", "amount_units": "Payment amount format", "contract_confirmed": "Moniepoint confirmed the amount format", "webhook_secret": "Payment notification key"},
        "defaults": {}, "columns": [], "filters": [],
    },
    "Moniepoint Terminal": {
        "hide": [],
        "labels": {"terminal_serial": "Terminal serial number", "pos_profile": "Shop", "mode_of_payment": "Bank account", "enabled": "Use this terminal"},
        "defaults": {}, "columns": ["terminal_serial", "enabled"], "filters": [],
    },
    "Moniepoint Transaction": {
        "hide": ["response_code", "amount_units", "payment_method"],
        "labels": {"invoice": "Sale", "terminal": "Terminal", "merchant_reference": "Payment reference", "request_amount": "Amount requested", "state": "Payment status", "processing_status": "Moniepoint status", "actual_amount": "Amount reported by Moniepoint", "last_checked": "Last checked"},
        "defaults": {}, "columns": ["state", "invoice", "last_checked"], "filters": ["state"], "keep_id": True,
    },
}

# Short labels for normal shop work. Stored document and select names stay unchanged.
FORMS["Supplier"]["labels"].update({"supplier_type": "Type"})
FORMS["Customer"]["labels"].update({"customer_type": "Type"})
FORMS["Item"]["labels"].update({
    "item_code": "Product ID", "custom_k3ls_device": "Device", "custom_k3ls_configuration": "Specifications",
    "custom_k3ls_serial": "Serial or IMEI", "custom_k3ls_ownership": "Owner", "custom_k3ls_owner": "Supplier or owner",
    "custom_k3ls_arrival_condition": "Condition when received", "custom_k3ls_final_condition": "Condition now",
    "custom_k3ls_acquired_on": "Date received", "custom_k3ls_acquisition_type": "How received",
    "custom_k3ls_mode": "Mode", "custom_k3ls_repair_cost": "Repair cost",
})
FORMS["Item"]["hide"].extend("item_tax_section_break is_stock_item has_serial_no custom_k3ls_ownership custom_k3ls_owner custom_k3ls_acquisition sb_barcodes barcodes opening_stock valuation_rate stock_levels_section stock_levels_html serial_nos_and_batches".split())
FORMS["POS Invoice"]["hide"].append("scan_barcode")
for _doctype in ("Item", "Customer", "Supplier", "Purchase Invoice", "Sales Invoice", "POS Invoice", "Payment Entry"):
    FORMS[_doctype]["hide"].extend(["dashboard_tab", "connections_tab"])
FORMS["K3LS Repair"]["labels"].update({
    "intake_tab": "Details", "progress_tab": "Progress", "billing_tab": "Price and payment",
    "relationship": "Customer type", "configuration": "Specifications", "serial_no": "Serial or IMEI",
    "diagnosis": "Problem found", "intake_evidence": "Device photo", "quote_approved": "Price approved",
    "assigned_to": "Repairer", "final_condition": "Condition now", "customer_address": "Address",
    "approval_reference": "Approval reference", "sales_invoice": "Invoice", "received_at": "Received on",
    "expected_ready_date": "Ready by", "fixed_at": "Repaired on", "collected_at": "Collected on",
})
FORMS["Payment Entry"]["labels"].update({
    "payment_type": "Direction", "party_section": "Customer or supplier", "payment_accounts_section": "Accounts",
    "paid_from": "From account", "paid_to": "To account", "paid_amount": "Paid", "received_amount": "Received",
    "section_break_14": "Invoices", "reference_no": "Reference", "unallocated_amount": "Unmatched amount",
    "paid_from_account_currency": "From currency", "paid_to_account_currency": "To currency",
    "source_exchange_rate": "From exchange rate", "target_exchange_rate": "To exchange rate",
    "total_allocated_amount": "Matched amount", "deductions": "Fees or adjustments", "taxes": "Tax",
})
FORMS["POS Invoice"]["labels"].update({
    "custom_k3ls_tested": "Testing", "custom_k3ls_acknowledged": "Customer accepts condition",
    "custom_k3ls_disclosure_ref": "Condition reference",
})
for _doctype in ("Purchase Invoice", "POS Invoice", "Sales Invoice"):
    FORMS[_doctype]["labels"].update({"grand_total": "Total", "outstanding_amount": "Left to pay"})
FORMS["Account"] = {"hide": [], "labels": {}, "defaults": {}, "columns": [], "filters": [], "keep_id": True, "presentation_only": True}
FORMS["User"] = {
    "hide": [], "labels": {"user_details_tab": "Details", "roles_permissions_tab": "Access",
        "settings_tab": "Password", "section_break_3": "", "first_name": "First name",
        "last_name": "Last name", "enabled": "Active", "sb1": "Access", "mobile_no": "Mobile",
        "username": "Username", "new_password": "New password", "logout_all_sessions": "Sign out other devices"},
    "defaults": {}, "columns": ["full_name", "username", "enabled"], "filters": ["enabled"],
    "keep_id": False, "presentation_only": True,
}

CHILD_LABELS = {
    "Payment Entry Reference": {"reference_doctype": "Type", "reference_name": "Invoice", "total_amount": "Total", "outstanding_amount": "Unpaid", "allocated_amount": "Payment", "due_date": "Pay by"},
    "Payment Entry Deduction": {"account": "Account", "amount": "Amount", "cost_center": "Cost centre"},
    "Purchase Invoice Item": {"item_code": "Product", "item_name": "Product name", "qty": "Quantity", "rate": "Price", "amount": "Total", "warehouse": "Stock location", "uom": "Unit"},
    "Sales Invoice Item": {"item_code": "Product", "item_name": "Product name", "qty": "Quantity", "rate": "Price", "amount": "Total", "warehouse": "Stock location", "uom": "Unit"},
    "POS Invoice Item": {"item_code": "Product", "item_name": "Product name", "qty": "Quantity", "rate": "Price", "amount": "Total", "warehouse": "Stock location", "uom": "Unit"},
}


def presentation_config():
    """Omit tax setup controls, not tax calculations or recorded amounts."""
    import copy
    config = copy.deepcopy(FORMS)
    user_fields = {"user_details_tab", "enabled", "section_break_3", "username", "first_name", "last_name",
        "column_break0", "column_break_11", "roles_permissions_tab", "sb1", "roles_html", "roles",
        "phone", "mobile_no", "settings_tab", "change_password"}
    config["User"]["hide"] = [df.fieldname for df in frappe.get_meta("User").fields if df.fieldname not in user_fields]
    purchase_fields = {"supplier", "supplier_name", "posting_date", "due_date", "is_paid", "is_return", "return_against",
        "bill_no", "bill_date", "items", "update_stock", "mode_of_payment", "paid_amount", "grand_total",
        "rounded_total", "rounding_adjustment", "total_taxes_and_charges", "discount_amount", "outstanding_amount", "remarks"}
    purchase_meta = frappe.get_meta("Purchase Invoice")
    config["Purchase Invoice"]["hide"].extend(df.fieldname for df in purchase_meta.fields
        if df.fieldtype not in ("Column Break", "Section Break") and df.fieldname not in purchase_fields)
    config["Purchase Invoice"]["labels"].update({"is_paid": "Paid now", "mode_of_payment": "Paid with", "paid_amount": "Amount paid",
        "update_stock": "Add to stock", "bill_no": "Supplier reference", "bill_date": "Supplier receipt date",
        "supplier_invoice_details": "Supplier receipt", "items": "Products", "sec_warehouse": "Products",
        "due_date": "Pay by", "is_return": "Return to supplier", "return_against": "Original purchase"})
    for doctype, settings in config.items():
        if settings.get("presentation_only"):
            continue
        for df in frappe.get_meta(doctype).fields:
            if "tax" in df.fieldname and df.fieldtype != "Column Break" and (
                not df.read_only or df.fieldname == "tax_id"
            ):
                settings["hide"].append(df.fieldname)
    return config


def enabled():
    return frappe.db.exists("Workspace Sidebar", "K3LS Shop") and frappe.db.get_value("POS Profile", "K3LS Shop", "company") == "K3LS LIMITED"


def boot_session(bootinfo):
    if not enabled():
        return
    bootinfo.k3ls_operations_ready = frappe.db.get_default("k3ls_operations_revision") == "20261004-9"
    from moniepoint_pos.checkout import PAYMENT_METHODS
    from moniepoint_pos.accounts import BANK_ICONS
    bootinfo.k3ls_payment_methods = list(PAYMENT_METHODS)
    bootinfo.k3ls_bank_icons = BANK_ICONS
    bootinfo.k3ls_shop_ui = presentation_config()
    bootinfo.k3ls_username = "Administrator" if frappe.session.user == "Administrator" else frappe.db.get_value("User", frappe.session.user, "username")
    from moniepoint_pos.list_search import LISTS
    for doctype, search in LISTS.items():
        bootinfo.k3ls_shop_ui[doctype]["search_title"] = search["title"]
    # Only skip the list when this user can read exactly one active client till.
    profiles = frappe.get_list("POS Profile", filters={"company": "K3LS LIMITED", "disabled": 0},
        fields=["name", "warehouse", "company"], limit_page_length=2) if frappe.has_permission("POS Profile", "read") else []
    bootinfo.k3ls_till_profile = profiles[0].name if len(profiles) == 1 else None
    if len(profiles) == 1:
        bootinfo.k3ls_purchase_defaults = {"company": profiles[0].company, "set_warehouse": profiles[0].warehouse}
    # Keep all record permissions unchanged. Only filter navigation presented to this site.
    bootinfo.workspace_sidebar_item = {key: value for key, value in bootinfo.workspace_sidebar_item.items() if key in ("k3ls shop", "k3ls owner", "my workspaces")}
    # Checkout uses the saved profile internally. It is not a shop setup action.
    for key in ("k3ls shop", "k3ls owner"):
        sidebar = bootinfo.workspace_sidebar_item.get(key)
        if sidebar:
            sidebar["items"] = [item for item in sidebar["items"]
                if not (item.get("link_type") == "DocType" and item.get("link_to") == "POS Profile")]
    owner = bootinfo.workspace_sidebar_item.get("k3ls owner")
    if owner:
        # Both links are read-only summaries. Keep one existing, permission-
        # filtered route rather than presenting them as separate setup screens.
        items = []
        overview_added = False
        for item in owner["items"]:
            if item.get("link_type") == "Page" and item.get("link_to") in ("shop-accounts", "shop-profit"):
                if overview_added:
                    continue
                item = dict(item, label=_("Overview"), link_to="shop-accounts", icon="chart-line")
                overview_added = True
            items.append(item)
        owner["items"] = items
    for name in ("shop-accounts", "shop-profit"):
        page = bootinfo.get("page_info", {}).get(name)
        if page:
            page.update({"title": _("Overview"), "route": "shop-accounts"})


def configure():
    frappe.only_for("System Manager")
    if not enabled():
        frappe.throw("Set up K3LS Shop first.")
    backup_name = "k3ls-ui-before-cleanup.json"
    backup = {"property_setters": frappe.get_all("Property Setter", fields=["*"]), "list_settings": frappe.get_all("List View Settings", fields=["*"]), "enable_onboarding": frappe.db.get_single_value("System Settings", "enable_onboarding")}
    if not frappe.db.exists("File", {"file_name": backup_name}):
        save_file(backup_name, frappe.as_json(backup), None, None, is_private=1)
    count = 0
    for doctype, labels in CHILD_LABELS.items():
        meta = frappe.get_meta(doctype)
        for field, label in labels.items():
            if meta.has_field(field):
                make_property_setter(doctype, field, "label", label, "Data")
    for doctype, config in FORMS.items():
        if config.get("presentation_only"):
            continue
        meta = frappe.get_meta(doctype, cached=False)
        for field, label in config["labels"].items():
            if meta.has_field(field):
                make_property_setter(doctype, field, "label", label, "Data")
        for field, default in config["defaults"].items():
            make_property_setter(doctype, field, "default", default, "Text")
        for df in meta.fields:
            if df.in_list_view or df.fieldname in config["columns"]:
                make_property_setter(doctype, df.fieldname, "in_list_view", int(df.fieldname in config["columns"]), "Check")
            if df.in_standard_filter or df.fieldname in config["filters"]:
                make_property_setter(doctype, df.fieldname, "in_standard_filter", int(df.fieldname in config["filters"]), "Check")
        if meta.issingle:
            continue
        fields = [{"fieldname": "status_field"}] + [{"fieldname": name} for name in config["columns"]]
        exists = frappe.db.exists("List View Settings", doctype)
        settings = frappe.get_doc("List View Settings", doctype) if exists else frappe.new_doc("List View Settings")
        settings.name = doctype
        settings.update({"fields": frappe.as_json(fields), "disable_comment_count": 1, "disable_sidebar_stats": 1, "disable_automatic_recency_filters": 1, "allow_edit": 0})
        settings.save() if exists else settings.insert()
        count += 1
    # Put notes on the first tab, without duplicating fields or changing records.
    for doctype, notes, before in (("Supplier", "supplier_details", "defaults_section"), ("Customer", "customer_details", "section_break_hwkr")):
        order = [df.fieldname for df in frappe.get_meta(doctype).fields if df.fieldname != notes]
        order.insert(order.index(before), notes)
        make_property_setter(doctype, None, "field_order", frappe.as_json(order), "Text", for_doctype=True)
    # Frappe places custom sections after the existing tab boundary. Keep device data on Details.
    meta = frappe.get_meta("Item")
    block = [df.fieldname for df in meta.fields if df.fieldname.startswith("custom_k3ls_")]
    order = [df.fieldname for df in meta.fields if df.fieldname not in block]
    index = order.index("accounting")
    order[index:index] = block
    make_property_setter("Item", None, "field_order", frappe.as_json(order), "Text", for_doctype=True)
    make_property_setter("Item", "section_break_11", "collapsible", 0, "Check")
    for doctype, field in (("Supplier", "supplier_details"), ("Customer", "customer_details")):
        make_property_setter(doctype, field, "description", "", "Text")
    # The checkout form reads a separate list of labels, rather than DocField labels.
    settings = frappe.get_single("POS Settings")
    for row in settings.invoice_fields:
        label = FORMS["POS Invoice"]["labels"].get(row.fieldname)
        if label:
            row.label = label
    settings.save()
    frappe.db.set_single_value("System Settings", "enable_onboarding", 0)
    frappe.clear_cache()
    frappe.db.commit()
    return {"forms": count, "backup": backup_name, "records_deleted": 0, "permissions_changed": False}
