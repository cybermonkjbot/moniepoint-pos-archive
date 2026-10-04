# K3LS workbook-to-app gap audit

Audit date: October 4, 2026.

Workbook: `/Users/joshua/Downloads/K3LS_BUSINESS_MANAGEMENT_CONTROL_SYSTEM_FINAL_WITH_AUTO_IDS_LOGO_WATERMARKED.xlsx`.

App source: `/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos`, committed revision `0403cf0`, plus the uncommitted product and pricing changes present during this review.

## What is missing

The app covers product sales, customer repairs, customer contacts, partial payments, unpaid-invoice collections, supported shop accounts and user access. It does not yet cover the workbook's full stock, custody and payment-control system.

The largest missing workflows are:

1. Receive stock with source, quantity, configuration, ownership, evidence and an owner-review queue.
2. Inspect incoming stock, record faults and fixing costs, then verify its sale-ready condition.
3. Sell stock belonging to Goshen or another owner, calculate the agreed payout and track settlement.
4. Track stock sent to another location, agent or repairer, including handovers and overdue returns.
5. Handle customer returns, exchanges, refunds and write-offs through owner approval.
6. Turn a customer's unpaid balance into dated instalments, payment promises and collection follow-ups.
7. Show supplier debts, overdue bills, other obligations and verified supplier payments in one place.
8. Review receipts and payouts against evidence and actual bank balances.
9. Submit staff expense and correction requests, approve them and retain an action history.
10. Track delivery jobs, rider costs, delivery proof and unpaid delivery charges.

Piece counts, additional product configurations, optional Mode, barcode removal and repair cost in product profit have source changes underway. They are not counted as completed or deployed in this audit. Supplier intake is still missing.

## How to read the findings

- **Covered** means the shop-specific implementation exists in source. It does not certify the current Windows installation.
- **Partial** means related fields or an existing flow are present, but important workbook actions or controls are absent.
- **Missing** means no complete shop-specific workflow was found. A generic ERPNext module is not proof that the client can use it in this simplified app.
- **In progress** means uncommitted implementation exists but has not been applied and checked in the running environment.
- **Different by choice** means the user's newer instructions deliberately replace the workbook's approach.

No listener was running on the local app port 8000 or database port 3307 during this audit. This is a workbook and source review, not a live database, permission or Windows-installation verification. No client records were changed or imported. No tests, builds or exports were run.

## Every sheet mapped

| # | Workbook sheet | App coverage | Missing or different |
| --- | --- | --- | --- |
| 1 | ADMIN SALES FORM INBOX | Different by choice; approval aspect missing | Native POS replaces Google Forms. No raw staff sale-submission queue with Pending, Rejected and Posted decisions and posted-invoice links. Do not introduce a second sale ledger. |
| 2 | START HERE | Different by choice | The workbook's owner-only file and restricted-form operating guide needs an app equivalent only where behavior is unfamiliar. Do not recreate spreadsheet instructions as mandatory screens. |
| 3 | STAFF SALES | Partial | POS supports products, quantity, customer, payments, unpaid balances and condition acknowledgement. Missing structured payment arrangements, approval of credit, pickup or delivery dates, last contact, next follow-up and collection responsibility. Condition evidence is invoice-level text, not a structured record for each physical unit. Other-owner sales are blocked. |
| 4 | STAFF STOCK MOVEMENT | Missing | No simple transfer, consignment, repair dispatch, repair return or customer-return movement log with releasing and receiving staff, actual custodian, reason, expected return and current status. |
| 5 | STAFF REPAIR INTAKE | Largely covered | Repairs has customer contact, device, serial, specifications, colour, arrival condition, fault, evidence and intake actor. An optional Item link exists in the full record, but the simplified flow does not expose it or connect it to custody movements. |
| 6 | STAFF CUSTOMER RETURNS | Missing | No intake-to-decision flow for refund, exchange, repair or rejection, linked to the original sale and condition. Native invoice returns do not provide the workbook's owner-approval case record. |
| 7 | STAFF STOCK COUNT | Missing; count correction in progress | Owner piece-count correction is being added. That is not a physical count session with expected and observed locations, found or missing state, condition, counter, supervisor, discrepancies and resolution. |
| 8 | STAFF CHANGE REQUESTS | Missing | No staff request queue for corrections, cancellation, missing stock, write-off, price change, refund or deletion with evidence, impact, approval and action references. |
| 9 | STAFF DASHBOARD | Partial | Repair status counts exist within Repairs. No combined operational queue for open movements, pending changes and stock discrepancies. Purchase costs, profit and bank details must stay owner-only. |
| 10 | ADMIN ITEM REGISTER | Partial; stock and pricing in progress | Model, serial, specifications, colour, ownership and cost metadata exist. Missing operational custodian and movement history, source and swap links, linked owner-stock agreement, structured arrival inspection and final verification. Grouped configurations and counts are underway, not deployed. |
| 11 | ADMIN PURCHASES | Partial | Restock currently opens a simplified Purchase Invoice. Missing guided new-stock intake, business versus individual or customer acquisition, trade-in linkage, arrival inspection, receiver, source completeness checks and payment follow-up. Generic purchase accounting does not provide the full intake workflow. |
| 12 | ADMIN REPAIRS | Partial | Intake, assigned staff, external repairer, diagnosis, work, quote approval, parts/labour/other cost, charge, fix and collection dates exist. Optional follow-up and agreement fields exist, but the simplified editor does not expose the complete set. Missing structured send-out custody, a collection follow-up flow and repair-specific profitability in owner reporting. Billing creates a draft invoice; saved repair costs do not themselves post an expense. Owner collection can proceed unpaid or without an invoice. |
| 13 | ADMIN CONSIGNMENT | Missing | No register for K3LS-owned stock sent to agents, amount due, return deadline, overdue days and settlement. This is distinct from holding someone else's stock. |
| 14 | ADMIN FINANCIALS | Partial | Money in/out uses Payment Entry and Accounts reads posted ledger transactions. Missing a simple operating-expense or other-cash flow with evidence and approvals. Payment records alone do not replace actual expense recognition. |
| 15 | ADMIN APPROVALS | Missing | No owner decision register connecting a request, evidence, decision, approver, implementation and audit record. A repair quote approval is a customer's price approval, not this administrative workflow. |
| 16 | ADMIN AUDIT LOG | Partial | Framework record metadata and some tracked changes exist. No unified owner-visible history with before and after values, reason, approval, verifier and linked action across the shop workflows. Hidden History tabs are not a substitute for a retained audit record. |
| 17 | ADMIN SETTINGS | Different by choice; review controls partial | Username/password access and roles replace sheet protections and form-email controls. No workbook-equivalent access-review dates or control-review record. Hiding fields or pages is not permission enforcement. |
| 18 | ADMIN DASHBOARD | Partial | Profit, account balances, debtor totals and repair counts exist in separate views. Most of the workbook's 26 custody, debt, receipt and payout exception measures are missing. See the metric mapping below. |
| 19 | STAFF INVENTORY VIEW | Partial; piece counts in progress | Product browsing and selling prices exist. Missing a complete staff-safe view of stock location, custodian, last movement, ownership contact and verified condition. Financial cost and owner-payout fields must not be returned to shop staff. |
| 20 | STAFF CUSTOMERS | Partial; email deliberately omitted | Customer contacts exist. Missing a complete buyer/seller/both classification and source identity/business reference used when the shop buys from a customer. Preferred contact is unnecessary where it only repeats the available phone contact. |
| 21 | STAFF EXPENSE REQUESTS | Missing | No request, evidence, approval, paid-by record and reimbursement flow. General accounting forms are not the simplified staff request workflow. |
| 22 | STAFF CONSIGNMENT VIEW | Missing | No safe staff view of outgoing stock, custody, contact, return deadline and status without confidential amounts. |
| 23 | ADMIN SUPPLIERS & PAYABLES | Partial | Suppliers exists as a directory. Missing shop-specific balances, purchased products, overdue amounts, terms and source/owner classification. Goshen is seeded as a Company Supplier rather than a separate accessories owner with payouts. |
| 24 | ADMIN RECEIVABLES | Missing for other/legacy debts | Money owed derives from submitted POS and Sales Invoices. No simple workflow for a genuine older or other debt not represented by an invoice, with evidence, collection owner and follow-up. Do not duplicate invoice debts here. |
| 25 | ADMIN MANAGEMENT REPORTS | Partial | Existing financial views are narrower than the workbook's stock, custody, approvals, expense, supplier and debtor exception reports. A usable combined review/export is missing. |
| 26 | ADMIN STAFF & HR | Different by choice | Employment, salary dates, commission, holdbacks, emergency contact and payroll are absent. Staff was deliberately changed to user management, so these are not automatically part of the next update. The workbook bases commission on verified collected completed-sales amounts, not total invoices. |
| 27 | ADMIN PAYMENT RECEIPTS | Partial | Cash and bank receipts and some Moniepoint transaction states exist. Missing a unified receipt-review flow with Pending, Verified and Rejected states, evidence, verifier, bank-match date, linked instalment and reference checks. Selecting FCMB or UBA records a reported transfer; it does not verify one. |
| 28 | ADMIN DISPATCH | Missing | A Dispatch service Item exists, but POS rejects non-stock services. There is no delivery-job workflow with addresses, rider, charge, payout, fuel, margin, receipt, balance, expected delivery and proof. |
| 29 | ADMIN ACCOUNT RECONCILIATION | Partial | Accounts shows posted balances and recent transactions. Missing opening-date/balance review, actual bank or cash balance, expected-versus-actual difference and a saved reconciliation decision. |
| 30 | ADMIN STOCK SUBMISSIONS | Missing | No staff or owner intake queue for quantity, source, model, serial/specs, condition, purchase costs, evidence, ownership, payout and owner review, with links to the stock actually registered. |
| 31 | ADMIN TRADE INS | Missing | A product can have Swap / Trade-in acquisition metadata. No paired sale/acquisition flow with approved trade-in credit, received product, customer, condition, residual cash and balance. |
| 32 | ADMIN INSTALMENT SCHEDULE | Missing | Part payment and one invoice due date are supported. Missing multiple scheduled amounts/dates, allocated receipts, original and revised promise dates, overdue instalments and detection of balance not covered by a plan. |
| 33 | ADMIN DEBTOR OVERVIEW | Partial | Money owed groups unpaid POS and repair/sale invoices and shows overdue status without counting consolidated POS twice. Missing legacy debts, trade-in credits, arrangements, next instalment, last contact, collection owner and follow-up. Unbilled or draft repair charges do not appear as submitted-invoice debts. |
| 34 | ADMIN SUPPLIER PAYMENTS | Partial | Supplier Payment Entries and the core purchase-bill Create Payment action provide actual supplier-payment coverage. Missing the workbook's separate evidence review, verification, documented reversal, matched date and reference-exception workflow, plus a guided flow for independent obligations. |
| 35 | ADMIN OTHER PAYABLES | Missing | No guided entry of genuine older supplier debts or other obligations with source evidence, terms, due date and follow-up. Do not duplicate an existing Restock bill. |
| 36 | ADMIN PAYABLE OVERVIEW | Missing as a shop view | No equivalent of Money owed for money K3LS owes suppliers, combining purchase bills and other obligations with contacts, age, due dates and follow-up. Generic ERPNext payable reporting is not integrated into this shop flow. |
| 37 | ADMIN THIRD PARTY STOCK | Missing beyond labels | Ownership and supplier-link fields exist, but sales are blocked. Missing held versus on-demand arrangements, agreed payout, sale proceeds, owner balance, payout deadline, return to owner, direct owner sale and complaints. |
| 38 | ADMIN OWNER PAYMENTS | Missing | No verified payout ledger tied to an owner-stock agreement, with owner, amount, account, evidence, reversals and remaining balance. |
| 39 | ADMIN STOCK INSPECTION | Missing as a workflow; aggregate repair cost in progress | Free-text arrival/final condition exists. Missing fault checklist, arrival testing/operating status, inspector/date, dated fixing work, parts/labour/other cost breakdown and final verifier/date. The repair-cost field underway does not provide these records. |
| 40 | ADMIN STOCK FORM INBOX | Different by choice; intake/review missing | A native supply-intake flow should replace the email-based form. Raw submission, review outcome and posted stock references still need implementing. Never register the rejected QA row in this sheet. |

## Financial and stock rules that matter

### Product cost and profit

The workbook calculates the complete product cost as purchase cost plus landing cost plus fixing cost. See `ADMIN ITEM REGISTER!I:K`, its total-cost formula in `K5`, and `ADMIN STOCK INSPECTION!S:V` for parts, labour and other fixing costs.

The committed app's pricing records cover purchase and delivery cost. The pending change adds per-piece repair cost and snapshots total cost on new sales. This is separate from accounting profit, which reads posted ERPNext income and expense records. Changing an Item's cost metadata does not create a real stock valuation or repair expense. Historical sales without a reliable saved cost cannot be assigned today's cost and presented as verified historical profit.

The workbook's repair gross profit is customer charge minus repairer cost, `ADMIN REPAIRS!N5`. The app saves repair costs and charges but does not yet provide the full repair-profit and expense-posting flow in the owner overview.

### Quantity and individual devices

The workbook allocates one permanent Item ID per physical unit. The user's newer request is one product configuration with stock counted in pieces. The workbook's five MIKUSO mice and five unbranded mice are currently represented by ten separate IDs in the setup source.

Keep grouped quantities for interchangeable pieces. Preserve a unit record where serial, condition, fixing cost or ownership differs, especially for laptops. Separate RAM, CPU, storage or other configurations must remain distinguishable. Optional Mode is a new user requirement, not a workbook column. Existing stock and invoice IDs must not be merged automatically. Barcode entry is not necessary for this model.

### Stock owned by someone else

`ADMIN THIRD PARTY STOCK`, `ADMIN OWNER PAYMENTS`, `ADMIN STOCK SUBMISSIONS!X:AC` and `ADMIN ITEM REGISTER!AA:AG` distinguish K3LS purchases from sister/external-owner stock.

Goshen stock in K3LS space is not automatically stock K3LS bought. An agreed owner payout must not be presented as K3LS purchase cost without the correct ownership/accounting treatment. Owner direct sales must not become K3LS revenue or an owner payout obligation. Customer money received and money paid to the stock owner are separate events.

The current POS sale validator blocks sister/external-owner stock until owner payouts are supported. Removing that block without adding the agreements and settlement records would lose an important control. The ownership guard is attached to POS Invoice, not universally enforced for every Sales Invoice path. This is a permission and accounting gap to close before enabling those sales.

### Receipts, balances and instalments

The workbook only reduces balances with Verified payments whose reference checks pass. See `STAFF SALES!J5`, `ADMIN REPAIRS!L5`, `ADMIN PAYMENT RECEIPTS!I:S` and the supplier/owner payment sheets.

The app supports part payments, but it does not yet implement this complete evidence/verification model. One due date is not an instalment plan. Promise revisions should retain the original agreed date, and payment receipts should be attributable to both the debt and its instalment where a plan exists.

Other debts must be separate from invoice debts. Other payables must be separate from existing purchase bills. These are opening or independent obligations, not a way to record the same balance twice.

Accounts currently reads posted ledger balances. FCMB and UBA selections are manual received-transfer recording, not bank confirmation. Account reconciliation needs actual balances and differences, not a second copy of all payments.

### Approvals and confidentiality

The workbook requires owner decisions before returns, refunds, corrections, write-offs and expense reimbursements. Those actions need enforced server-side permission and approval records. Merely hiding a button or tab does not enforce the workbook's access boundaries.

Staff should see operational stock, sale prices, repairs and custody information. Purchase costs, profit, supplier liabilities, owner payouts and bank data belong to the owner. A saved action history should remain available to the owner even when regular forms no longer show activity/comments/history tabs.

## Owner dashboard metric mapping

The workbook lists 26 measures in `ADMIN DASHBOARD!A3:Z3`. They should become useful linked exception views, not 26 permanent cards on every screen.

| Workbook measures | Coverage and missing inputs |
| --- | --- |
| Missing items; stock discrepancies | Missing physical-count records, reconciliation reasons and unresolved discrepancy cases. Pending count correction does not supply these. |
| Overdue consignment; items with repairers | Missing custody movements, outgoing consignments, handover and return dates. |
| Pending repairs | Repair states/counts exist; not yet combined with other operational exceptions. |
| Receivables; overdue debtors; overdue balance | Invoice-derived balances and overdue flags exist. Other debts, plans and follow-up remain missing. |
| Unmatched receipts; receipt reference exceptions | Missing common verification queue, bank-match state and reference-exception review. Moniepoint status alone is narrower. |
| Dispatch balances | Missing delivery-job and delivery-payment records. |
| Sales record exceptions | Some sale checks exist. Missing a unified review of per-unit disclosure, ownership, intake and credit-control exceptions. |
| Overdue instalments; unscheduled instalment balance | Missing instalment plans and allocations. |
| Supplier balance owed; overdue supplier balance; overdue supplier items; supplier payment exceptions | Generic purchase accounting exists. Missing the simplified payable overview, independent obligations, follow-up and payment-verification review. |
| Sister stock available; other owner stock available | Ownership labels exist. Missing reliable ownership agreements, unit custody and available/on-demand state. |
| Owner payout balance; overdue owner payout; missing payout due dates | Missing owner-stock agreements, due dates and linked verified payouts. |
| Third-party gross margin | Missing the third-party sale and agreed payout calculation. Existing product margin is not this measure. |
| Ownership exceptions; owner payout exceptions | Missing owner/contact/arrangement completeness checks and payout-reference validation. |

## Data missing from the workbook itself

These are missing source facts, not facts an implementation should invent.

- There are 11 populated product-register rows, `ADMIN ITEM REGISTER!A5:AK15`. Many other rows are preassigned identifiers and formulas, not completed business transactions.
- The Surface Book 2, `K3LS-ITM-0001`, has serial `010988293157`, purchase cost ₦350,000, landing cost ₦5,000 and selling price ₦450,000. Preserve the leading zero in its serial.
- Its broken screen is recorded in `ADMIN STOCK INSPECTION!H5` and the observation in `P5`. Testing/arrival details, fixing amounts, work evidence and final verification are incomplete. Its full sale-ready cost and condition cannot be inferred from the listed price.
- The Surface was acquired through a swap/trade-in. The source contact and corresponding swap-sale linkage need confirmation.
- The five MIKUSO mice cost ₦6,500 each with selling price ₦10,000. The five unbranded wireless mice cost ₦5,500 each with selling price ₦8,500. Supplier, purchase dates and payment details remain incomplete.
- `ADMIN SUPPLIERS & PAYABLES!A5:P5` identifies Goshen Global Connect as `K3LS-SRC-0001`, Sister / Accessories Owner. Phone/address and item-specific payout agreements are not completed.
- No reliable actual opening bank/cash balances or verified payment history can be derived from the inspected populated rows. Zeros generated by formulas are not evidence of a bank balance.
- `ADMIN SALES FORM INBOX!A2:AC2` and `ADMIN STOCK FORM INBOX!A2:AB2` are explicitly rejected synthetic QA submissions. Exclude them from real sales, stock, debt, payouts and opening balances.

## Spreadsheet differences that should not become app clutter

- Username/password accounts and recovery codes deliberately replace email-dependent login and password recovery. Form email columns are not a reason to restore email requirements.
- The app's native POS and intake screens replace Google Forms and spreadsheet inbox mechanics. Keep an approval queue only where it supports the actual business decision.
- User management deliberately replaced Staff/HR. Payroll, salary and collected-sales commission are workbook capabilities, but they need a separate scope decision before reinstating them.
- Cash, Moniepoint, FCMB and UBA are the requested supported payment methods. Sterling/Other in the workbook or historical master records should not automatically return to checkout.
- Account reconciliation dates are needed in saved reconciliation records. They need not reintroduce the unnecessary balance-date and updated captions removed from the normal Accounts screen.
- The workbook's 40 sheets should not become 40 sidebar pages. Several are safe views, raw submission inboxes or derived reports over the same records.
- All inspected sheet protections are off in this XLSX. Its owner-only labels do not themselves restrict access. Some formulas are Google Sheets export expressions using `__xludf.DUMMYFUNCTION`, `IMPORTRANGE`, `MAP` and related functions. Cached values and the absence of cached error cells do not establish that Excel can recalculate them. Implement the underlying rules, not the spreadsheet formula strings.

## Suggested order for the next updates

| Order | App area | Work to group together |
| --- | --- | --- |
| 1 | Products / Receive stock | Complete piece counts and configurations; guided intake; ownership/source; inspection and fixing cost; stock posting with evidence; safe individual-unit traceability. |
| 2 | Sales / Repairs | Complete repair billing/cost reporting; condition evidence; trade-ins; owner-approved customer returns and exchanges. |
| 3 | Money owed | Instalment plans, receipt allocation, revised promises, collection follow-up and genuine other debts. |
| 4 | Suppliers / Money we owe | Purchase and other obligations, due dates, verified payments and supplier follow-up. |
| 5 | Owner stock / Stock movements | Goshen/external-owner agreements, sale settlement/payouts, outgoing consignments, transfers and repairer custody. Other-owner sales must remain blocked until this is implemented. |
| 6 | Owner review | Expense/change requests, approvals, retained action history, receipt verification, account reconciliation and linked exception reports. |
| Optional scope | Deliveries; Payroll | Add delivery management if the shop uses it. Payroll requires renewed approval because the user replaced Staff/HR with user management. |

This grouping preserves the simple shop UI while retaining the workbook's business controls.

## Primary source references

Workbook references above point to the supplied file, not external documentation. App references below describe local source only.

The [companion source capability audit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/docs/k3ls-app-capability-audit-20261004.md) separately records committed implementation, uncommitted work and available ERPNext core modules. It includes source references for procurement, stock transactions, inspection, payment schedules and bank reconciliation that could support these flows without recreating their accounting logic.

- [Setup and original product/supplier masters](../moniepoint_pos/client_setup.py), lines 21-76. Existing Items and prices are not posted opening stock or bank balances.
- [Product metadata and sale checks](../moniepoint_pos/shop_setup.py), lines 38-80 and 136-153. Ownership metadata, financial permission level, condition acknowledgement, other-owner blocking and partial-payment requirements.
- [Workbook metadata mapping](../moniepoint_pos/stock_details.py), lines 5-28. Blank-only descriptive fields, not inspection records or stock transactions.
- [Repair intake and progress API](../moniepoint_pos/repairs.py), lines 5-11 and 18-137. Supported fields, role boundaries and actions.
- [Repair validation and draft billing](../moniepoint_pos/moniepoint_pos/doctype/k3ls_repair/k3ls_repair.py), lines 7-71. Saved costs, quote approval, readiness and linked draft invoice.
- [Invoice debt and collection API](../moniepoint_pos/receivables.py), lines 9-125. Submitted-invoice scope, consolidated POS handling, collection methods and balances.
- [Account balances and bank metadata](../moniepoint_pos/accounts.py), lines 38-90 and 108-140. Posted ledger balances, latest 50 transactions and company bank details.
- [Current bank and profit scope](prices-and-banks.md). Manual transfer recording versus bank verification and metadata versus accounting profit.
- [Owner/shop navigation](../moniepoint_pos/navigation.py), especially lines 53-83. Shop routes are not a complete inventory of framework capabilities or permissions.
- [User-management replacement](../moniepoint_pos/staff.py). Staff screen is a compatibility route, not HR/payroll.
- [Pending product implementation](../moniepoint_pos/products.py), lines 33-236, and [pending product controls](../moniepoint_pos/public/js/k3ls_products.js). Uncommitted and undeployed during this audit.
- [Pricing and pending sale-cost snapshots](../moniepoint_pos/pricing.py), especially lines 48-56 and 145-206. Pending changes are not proof of saved costs on existing invoices.
