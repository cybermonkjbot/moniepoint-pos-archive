"""Focused client navigation. Hiding icons does not change record permissions."""
import frappe


SECTION_ICONS = {
    "K3LS Shop": {
        "POS": "shopping-cart",
        "Repairs": "wrench",
        "Sales history": "receipt",
        "Stock": "package",
        "Customers": "users",
    },
    "K3LS Owner": {
        "Payments": "wallet",
        "Suppliers": "truck",
        "Purchases": "shopping-bag",
        "Accounts": "landmark",
        "Shop settings": "sliders-horizontal",
        "Moniepoint settings": "key-round",
        "Terminals": "monitor",
        "Terminal transactions": "list-checks",
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
        "K3LS Shop": [("POS", "point-of-sale"), ("Repairs", "Issue"),
            ("Sales history", "POS Invoice"), ("Stock", "Item"), ("Customers", "Customer")],
        "K3LS Owner": [("Payments", "Payment Entry"), ("Suppliers", "Supplier"),
            ("Purchases", "Purchase Invoice"), ("Accounts", "Account"),
            ("Shop settings", "POS Profile"), ("Moniepoint settings", "Moniepoint Settings"),
            ("Terminals", "Moniepoint Terminal"), ("Terminal transactions", "Moniepoint Transaction")],
    }
    snapshot = {row.name: row.hidden for row in frappe.get_all("Desktop Icon", fields=["name", "hidden"])}
    if not frappe.db.get_single_value("System Settings", "setup_complete"):
        frappe.throw("Complete the existing setup wizard first.")
    for title, entries in definitions.items():
        sidebar = (frappe.get_doc("Workspace Sidebar", title)
            if frappe.db.exists("Workspace Sidebar", title)
            else frappe.get_doc({"doctype": "Workspace Sidebar", "title": title}))
        sidebar.set("items", [{"type": "Link", "label": label,
            "link_type": "Page" if target == "point-of-sale" else "DocType", "link_to": target}
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
