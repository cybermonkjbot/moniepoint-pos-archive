"""Focused client navigation. Hiding icons does not change record permissions."""
import frappe


SECTION_ICONS = {
    "K3LS Shop": {
        "POS": "shopping-cart",
        "Repairs": "wrench",
        "Sales": "receipt",
        "Stock": "package",
        "Customers": "users",
    },
    "K3LS Owner": {
        "Users": "users",
        "Sales": "receipt",
        "Money in/out": "wallet",
        "Money owed": "hand-coins",
        "Suppliers": "truck",
        "Purchases": "shopping-bag",
        "Accounts": "landmark",
        "Checkout settings": "sliders-horizontal",
        "Moniepoint settings": "key-round",
    },
}

WORKSPACE_ICONS = {"K3LS Shop": "store", "K3LS Owner": "shield-check"}


def apply_icons():
    """Update only K3LS icon metadata, preserving links, order and permissions."""
    frappe.only_for("System Manager")
    for title, sections in SECTION_ICONS.items():
        sidebar = frappe.get_doc("Workspace Sidebar", title)
        sidebar.header_icon = WORKSPACE_ICONS[title]
        for item in sidebar.items:
            if item.label in sections:
                item.icon = sections[item.label]
        sidebar.save()
        icon = frappe.get_doc("Desktop Icon", title)
        icon.icon = WORKSPACE_ICONS[title]
        icon.app = "moniepoint_pos"
        icon.logo_url = f"/assets/moniepoint_pos/icons/desktop_icons/solid/{frappe.scrub(title)}.svg"
        icon.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"workspaces": WORKSPACE_ICONS, "sections": SECTION_ICONS}


def configure():
    frappe.only_for("System Manager")
    definitions = {
        "K3LS Shop": [("POS", "point-of-sale"), ("Repairs", "shop-repairs" if frappe.db.exists("Page", "shop-repairs") else "K3LS Repair" if frappe.db.exists("DocType", "K3LS Repair") else "Issue"),
            ("Sales", "POS Invoice"), ("Stock", "Item"), ("Customers", "Customer")],
        "K3LS Owner": [("Sales", "POS Invoice"), ("Money in/out", "Payment Entry"), ("Money owed", "shop-money-owed" if frappe.db.exists("Page", "shop-money-owed") else "Sales Invoice"), ("Suppliers", "Supplier"),
            ("Purchases", "Purchase Invoice"), ("Accounts", "shop-accounts" if frappe.db.exists("Page", "shop-accounts") else "Account"),
            ("Checkout settings", "POS Profile"), ("Moniepoint settings", "Moniepoint Settings"),
            ("Users", "User")],
    }
    snapshot = {row.name: row.hidden for row in frappe.get_all("Desktop Icon", fields=["name", "hidden"])}
    if not frappe.db.get_single_value("System Settings", "setup_complete"):
        frappe.throw("Complete the existing setup wizard first.")
    for title, entries in definitions.items():
        sidebar = (frappe.get_doc("Workspace Sidebar", title)
            if frappe.db.exists("Workspace Sidebar", title)
            else frappe.get_doc({"doctype": "Workspace Sidebar", "title": title}))
        sidebar.set("items", [{"type": "Link", "label": label,
            "link_type": "Page" if target in ("point-of-sale", "shop-accounts", "shop-repairs", "shop-money-owed") else "DocType", "link_to": target,
            "navigate_to_tab": "accounting_tab" if target == "POS Profile" else None,
            "route_options": frappe.as_json({"sidebar": title}) if target == "POS Invoice" else None}
            for label, target in entries])
        sidebar.save()
        if not frappe.db.exists("Desktop Icon", title):
            frappe.get_doc({"doctype": "Desktop Icon", "label": title, "icon_type": "Link",
                "link_type": "Workspace Sidebar", "link_to": title, "sidebar": title,
                "roles": [{"role": "System Manager"}] if title == "K3LS Owner" else []}).insert()
    for name in snapshot:
        if name not in definitions:
            frappe.db.set_value("Desktop Icon", name, "hidden", 1)
    apply_icons()
    frappe.clear_cache()
    frappe.db.commit()
    return {"visible": list(definitions), "previous_hidden_state": snapshot}


def simplify_links():
    """Update existing K3LS links without replacing custom navigation or records."""
    frappe.only_for("System Manager")
    for title in ("K3LS Shop", "K3LS Owner"):
        sidebar = frappe.get_doc("Workspace Sidebar", title)
        sidebar.items = [item for item in sidebar.items if item.link_to not in ("Moniepoint Terminal", "Moniepoint Transaction")]
        for item in sidebar.items:
            if item.link_to in ("shop-staff", "User"):
                item.label = "Users"
                item.link_type = "DocType"
                item.link_to = "User"
            elif item.link_to == "Payment Entry":
                item.label = "Money in/out"
            elif item.link_to == "POS Profile":
                item.label = "Checkout settings"
                item.navigate_to_tab = "accounting_tab"
            elif item.link_to == "POS Invoice":
                item.label = "Sales"
                item.route_options = frappe.as_json({"sidebar": title})
            if item.label in SECTION_ICONS[title]:
                item.icon = SECTION_ICONS[title][item.label]
        if title == "K3LS Owner" and not any(item.link_to == "POS Invoice" for item in sidebar.items):
            sidebar.append("items", {"type": "Link", "label": "Sales", "link_type": "DocType",
                "link_to": "POS Invoice", "icon": "receipt", "route_options": frappe.as_json({"sidebar": title})}, position=0)
        if title == "K3LS Owner":
            sidebar.items.sort(key=lambda item: item.link_to != "POS Invoice")
        for index, item in enumerate(sidebar.items, 1):
            item.idx = index
        sidebar.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"sales": "POS Invoice", "money": "Payment Entry", "till_tab": "accounting_tab"}
