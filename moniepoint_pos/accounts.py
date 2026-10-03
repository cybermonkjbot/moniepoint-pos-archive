"""The shop's cash and bank accounts. Accounting records stay in ERPNext."""
import frappe
from frappe.query_builder.functions import Count, Sum
from frappe.utils import now_datetime, today

COMPANY = "K3LS LIMITED"
BANK_ICONS = {"FCMB": "fcmb-logo.svg", "UBA": "uba-mark.png", "Moniepoint MFB": "moniepoint-mark.svg"}


def checkout_accounts():
    """Only accounts backing the supported shop payment methods."""
    from moniepoint_pos.checkout import PAYMENT_METHODS, PROFILE
    profile = frappe.get_doc("POS Profile", PROFILE)
    profile.check_permission("read")
    if profile.company != COMPANY:
        frappe.throw("This checkout belongs to another company.")
    names = []
    for method in PAYMENT_METHODS:
        if not any(row.mode_of_payment == method for row in profile.payments):
            continue
        payment = frappe.get_doc("Mode of Payment", method)
        payment.check_permission("read")
        if not payment.enabled:
            continue
        names.extend(row.default_account for row in payment.accounts if row.company == COMPANY and row.default_account)
    return names


def visible_accounts():
    """Checkout accounts plus the company's explicitly configured bank accounts."""
    names = checkout_accounts()
    names.extend(row.account for row in frappe.get_list("Bank Account",
        filters={"company": COMPANY, "is_company_account": 1, "disabled": 0,
            "bank": ["in", ["FCMB", "UBA"]]}, fields=["account"], limit_page_length=100) if row.account)
    return list(dict.fromkeys(names))


@frappe.whitelist(methods=["GET"])
def overview():
    frappe.only_for("System Manager")
    frappe.get_doc("Company", COMPANY).check_permission("read")
    accounts = frappe.get_list(
        "Account",
        filters={"company": COMPANY, "is_group": 0, "disabled": 0, "name": ["in", visible_accounts()],
            "account_type": ["in", ["Cash", "Bank"]]},
        fields=["name", "account_name", "account_type", "account_currency"],
        order_by="account_type desc, account_name asc",
        limit_page_length=100,
    )
    can_read_balances = frappe.has_permission("GL Entry", "read")
    banks = {row.account: row for row in frappe.get_list("Bank Account",
        filters={"company": COMPANY, "is_company_account": 1, "disabled": 0,
            "account": ["in", [account.name for account in accounts]]},
        fields=["account", "bank", "account_name", "bank_account_no"], limit_page_length=100)} if accounts else {}
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
        account.label = "Moniepoint" if account.account_name == "Moniepoint MFB" else account.account_name
        bank = banks.get(account.name)
        account.holder = bank.account_name if bank else None
        account.number = bank.bank_account_no if bank else None
        account.icon = BANK_ICONS.get(bank.bank if bank else account.account_name)
    return {"accounts": accounts, "can_read_balances": can_read_balances,
        "as_of": today(), "updated_at": now_datetime().isoformat()}


@frappe.whitelist(methods=["GET"])
def transactions(account):
    frappe.only_for("System Manager")
    doc = frappe.get_doc("Account", account)
    doc.check_permission("read")
    if doc.company != COMPANY or doc.disabled or doc.is_group or doc.account_type not in ("Cash", "Bank") or doc.name not in visible_accounts():
        frappe.throw("Choose one of the shop's accounts.")
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


def configure_company_banks():
    """Attach the owner's bank details without changing checkout or posting money."""
    frappe.only_for("System Manager")
    company = frappe.get_doc("Company", COMPANY)
    company.check_permission("read")
    changed = []
    for bank, number in (("FCMB", "2008133309"), ("UBA", "1029877525")):
        account = frappe.get_doc("Account", f"{bank} - {company.abbr}")
        account.check_permission("read")
        if account.company != COMPANY or account.account_type != "Bank" or account.is_group or account.disabled:
            frappe.throw(f"Check the existing {bank} company account.")
        if not frappe.db.exists("Bank", bank):
            frappe.get_doc({"doctype": "Bank", "bank_name": bank}).insert()
        existing = frappe.get_all("Bank Account", filters={"account": account.name}, pluck="name")
        if len(existing) > 1:
            frappe.throw(f"More than one bank record is linked to {bank}. Review them first.")
        doc = frappe.get_doc("Bank Account", existing[0]) if existing else frappe.get_doc({
            "doctype": "Bank Account", "bank": bank, "account": account.name,
            "account_name": COMPANY, "company": COMPANY, "is_company_account": 1})
        if doc.bank != bank or (doc.company and doc.company != COMPANY):
            frappe.throw(f"The existing {bank} record belongs to another bank or company.")
        if doc.bank_account_no and doc.bank_account_no != number:
            frappe.throw(f"{bank} already has a different account number. It was not overwritten.")
        doc.account_name = COMPANY
        doc.company = COMPANY
        doc.is_company_account = 1
        doc.bank_account_no = number
        doc.disabled = 0
        doc.save()
        changed.append({"bank": bank, "number": number, "holder": COMPANY})
    frappe.clear_cache()
    frappe.db.commit()
    return {"accounts": changed, "checkout_changed": False, "balances_posted": False}
