"""The shop's cash and bank accounts. Accounting records stay in ERPNext."""
import frappe
from frappe.query_builder.functions import Count, Sum
from frappe.utils import now_datetime, today

COMPANY = "K3LS LIMITED"


@frappe.whitelist(methods=["GET"])
def overview():
    frappe.only_for("System Manager")
    frappe.get_doc("Company", COMPANY).check_permission("read")
    accounts = frappe.get_list(
        "Account",
        filters={"company": COMPANY, "is_group": 0, "disabled": 0, "account_type": ["in", ["Cash", "Bank"]]},
        fields=["name", "account_name", "account_type", "account_currency"],
        order_by="account_type desc, account_name asc",
        limit_page_length=100,
    )
    can_read_balances = frappe.has_permission("GL Entry", "read")
    balances = {}
    if accounts and can_read_balances:
        ledger = frappe.qb.DocType("GL Entry")
        query = frappe.qb.get_query(
            "GL Entry", fields=[ledger.account], ignore_permissions=False,
            filters={"company": COMPANY, "is_cancelled": 0, "posting_date": ["<=", today()],
                "account": ["in", [account.name for account in accounts]]},
        ).select(
            (Sum(ledger.debit_in_account_currency) - Sum(ledger.credit_in_account_currency)).as_("balance"),
            Count(ledger.name).as_("transactions"),
        ).groupby(ledger.account)
        balances = {row.account: row for row in query.run(as_dict=True)}
    for account in accounts:
        row = balances.get(account.name)
        account.balance = float(row.balance or 0) if row else None
        account.has_transactions = bool(row and row.transactions)
    return {"accounts": accounts, "can_read_balances": can_read_balances,
        "as_of": today(), "updated_at": now_datetime().isoformat()}


@frappe.whitelist(methods=["GET"])
def transactions(account):
    frappe.only_for("System Manager")
    doc = frappe.get_doc("Account", account)
    doc.check_permission("read")
    if doc.company != COMPANY or doc.is_group or doc.account_type not in ("Cash", "Bank"):
        frappe.throw("Choose a shop cash or bank account.")
    return frappe.get_list("GL Entry",
        filters={"company": COMPANY, "account": account, "is_cancelled": 0, "posting_date": ["<=", today()]},
        fields=["posting_date", "remarks", "voucher_no", "debit_in_account_currency", "credit_in_account_currency"],
        order_by="posting_date desc, creation desc", limit_page_length=50)


def configure():
    frappe.only_for("System Manager")
    from frappe.modules.import_file import import_file
    import_file("Moniepoint POS", "Page", "shop-accounts", force=True)
    sidebar = frappe.get_doc("Workspace Sidebar", "K3LS Owner")
    for item in sidebar.items:
        if item.label == "Accounts":
            item.link_type = "Page"
            item.link_to = "shop-accounts"
    sidebar.save()
    frappe.clear_cache()
    frappe.db.commit()
    return {"page": "shop-accounts", "accounts_changed": False}
