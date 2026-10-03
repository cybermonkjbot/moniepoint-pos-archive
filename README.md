# Moniepoint POS

ERPNext custom app for API-key terminal integration. Disabled by default.

After installation, a System Manager configures Moniepoint Settings and a Moniepoint Terminal for each POS Profile. Credentials are encrypted Frappe Password fields and remain server-side. The API-key connection uses the published production API contract. Client credentials can be stored separately, but client-ID token exchange is blocked until Moniepoint confirms its HTTPS environment endpoints. See `docs/moniepoint-client-auth.md` for the documented exchange and remaining gaps.

Confirm amount units with Moniepoint before enabling requests. A saved NGN draft POS Invoice needs exactly one positive payment row matching the terminal's Mode of Payment.

Authenticated POST methods:

- `moniepoint_pos.api.check_credentials`
- `moniepoint_pos.api.request_payment` with `invoice` and `terminal`
- `moniepoint_pos.api.check_payment` with `transaction`

The app persists a unique merchant reference before sending a request. Unknown outcomes stay unresolved and block further charges for that invoice, including concurrent requests. There is no automatic retry, refund, cancellation or invoice settlement. An accepted request is not proof of payment. Do not manually submit an invoice as paid based only on this app's provider status.

Installed on the local `development.localhost` site. Moniepoint Settings contains Connection, Terminals and Payment requests. Terminal edits use a dialog and request/provider statuses are separate. Integration remains disabled until configured.

K3LS checkout changes below record payments already received. They do not charge a terminal or settle an invoice from a provider status. Payment-success mapping, reconciliation and authenticated webhooks remain unimplemented. No live API calls or tests were performed.

## K3LS navigation

`moniepoint_pos.navigation.configure` sets up the focused Shop and Owner navigation with distinct icons. To refresh only the icons on existing K3LS workspaces, run `moniepoint_pos.navigation.apply_icons` as a System Manager. This preserves links, order and record permissions.

Shop uses a storefront and Owner uses a shield. Each sidebar section has its own Lucide symbol. Desktop SVGs include solid and subtle variants in `moniepoint_pos/public/icons/desktop_icons`. The adapted Lucide geometry retains its license in `moniepoint_pos/public/icons/LICENSE`.

## K3LS shop setup

`moniepoint_pos.shop_setup.configure` installs the repair register, workbook device metadata, sale-condition fields and K3LS receipt. It sets the till to create POS Invoices, matching sales history and the terminal integration. Run it as a System Manager after the client masters and K3LS navigation exist.

The opening screen selects K3LS Shop automatically and asks only for counted drawer cash. Bank payment methods start each new shift at zero, not the bank's account balance. No shift is created by the setup command.

Repairs has Details, Progress and Price and payment sections. Customer contact, device condition and repair work are recorded separately from the invoice ledger. An owner can create one draft invoice from an approved price. The Payments screen keeps ERPNext's payment accounting. Repair staff cannot access the price or cost fields. No staff accounts have been created or granted this role.

Sales require recorded condition, testing, customer acknowledgement and a disclosure reference before submission. Third-party sales are blocked until an owner payout workflow is implemented. Device purchase and landing costs are workbook metadata, not opening-stock values or posted liabilities.

Applied to the local site. Inspected the opening screen at wide and narrow widths, the repair tabs and the populated stock form. No tests, builds or bundling were run. Transactional checkout, repair billing and staff-only rendering remain unverified. Stock posting, confirmed drawer cash, staff identities and live Moniepoint credentials remain outstanding. Consignment, dispatch, scheduled instalments and owner payout controls are not complete.

## Shop screens

`moniepoint_pos.shop_ui.configure` applies short labels and focused list columns. The browser customization is active only on the K3LS site. Products, Repairs, Customers, Suppliers, Restock, Sales, Money in/out and Checkout settings hide unrelated fields. An owner can reveal the original fields through Menu > More fields without saving any record.

Headers use one page heading instead of breadcrumbs. Everyday lists open as lists rather than the last report or board view. The view selector, saved-filter selector and supplier/customer report and creation menus are not shown in the header. Owners can open the report from the list menu. Essential filters, exports, confirmations and accounting permissions remain intact.

Routine forms omit comments, activity, assignment, sharing, tags, likes and edited-by panels. Product photos remain available. Files are hidden on connection, terminal, request, checkout and account forms. Repairer assignment is a repair field, not a generic task. Notifications sit beside the signed-in account, without Events or What's New. The K3LS sidebar menu omits Website, Edit sidebar, Display, Session defaults and Help.

Shop uploads omit web links and the bulk privacy switch. Existing attachment privacy defaults are unchanged. The first UI configuration stores a private metadata backup named `k3ls-ui-before-cleanup.json`; restoration is manual.

The till resumes an existing open session on refresh. Its displayed date follows the site timezone, and POS draft sales take the current shop date when saved. A new day does not automatically close the till, invent cash counts or reconcile money. A till that has never been opened still requires the first drawer cash count.

## Products, repairs and unpaid balances

The K3LS POS catalogue includes physical products only. Search does not add a product while typing. Product cards retain real stock and prices, and unavailable or unpriced products cannot be added. Existing product photos are shown when available. The Repairs button opens `/desk/shop-repairs`, a separate intake and progress workflow over K3LS Repair records. Price, approval, billing and collection remain owner controls.

Part-paid sales require a named customer, phone and Pay by date. The checkout confirmation shows received money and the remaining balance. It uses ERPNext's save and server validation. Customer changes preserve entered payment amounts; changes to currency or payment methods require review.

`/desk/shop-money-owed` is owner-only. It groups submitted unpaid POS and Sales Invoices by customer and currency, shows due dates and offers Take payment. Consolidated POS invoices are excluded to avoid counting the same sale twice. It shows unpaid invoices, not net customer credit or a full account statement.

POS collection records money already received through ERPNext's supported update-payments method. Invoice row locks and the displayed balance reject repeated or stale requests. Repair and other Sales Invoice collections return an unsaved Payment for review. Discounts, multi-currency accounts and payment-term allocations use the standard invoice payment form. No payment is submitted by that draft-preparation endpoint.

`moniepoint_pos.accounts.configure`, `moniepoint_pos.repairs.configure` and `moniepoint_pos.receivables.configure` register the three focused pages and update their existing sidebar links. They do not post transactions.

## App-style presentation

Shop screens use white surfaces and blue highlights. Owner screens use dark navy surfaces and light text. Desktop retains the sidebar and two-column POS. Phones get POS, Repairs, Stock and More navigation, limited by record read permissions. POS has Products/Basket panels; new repair intake has Device/Problem/Customer panels with a fixed primary action. The dock is hidden during dialogs, text entry and navigation-drawer use. Existing ledger tables and permissions are retained.

The supplied loading logo is cropped vertically from 447 x 447 to 447 x 93, with the original untouched. Moniepoint uses its real wordmark in Settings and brand mark in the sidebar. Owner Users opens ERPNext's existing user management; no separate staff directory or payroll implementation is included.

Rendered checks reuse the running local app. No tests, builds, bundling or additional servers were run. No stock, customer, user, repair, terminal or payment records were created during checks. See `design-qa.md` for evidence and remaining verification gaps.

## Checkout settings

`moniepoint_pos.checkout.configure` changes only K3LS Shop's checkout configuration. It keeps Cash as the default and Moniepoint as the other payment method. Existing FCMB, Sterling and UBA bank masters and all invoices/shifts remain intact. The previous profile is stored in private `k3ls-checkout-before-two-methods.json` for manual restoration.

Checkout settings shows two read-only payment cards. Country, active status, receipt options, currency, price list, ledger accounts, write-offs, product filters and stock controls remain configured but hidden in the routine view. Part payments remain enabled, stock validation stays on, and payment amounts are not assumed received automatically. Existing drafts with nonzero legacy payment amounts retain those choices. Accounts shows only the accounts backing Cash and Moniepoint, with balances and transaction details. The date and refresh-time lines are omitted. Other bank accounts and their history remain in ERPNext.

Tax setup controls, including item-row tax templates, are hidden across the routine shop forms. Tax rules, invoice calculations and nonzero amount disclosures are not removed or reset. More fields restores the administrator's original controls. Hiding controls is not an authorization boundary.

Moniepoint's published Push Payment Request documentation lists `CARD_PURCHASE`, `POS_TRANSFER` and `ANY`. New terminal dialogs default to Card or transfer, Moniepoint and the only active shop, with Use terminal off. This does not enable credentials or settle invoices. Source: TeamApt page 1039826999, version 20, updated 22 January 2025, retrieved 3 October 2026. See `docs/moniepoint-client-auth.md` for the official documentation URL and unresolved connection prerequisites.

## Focused lists and everyday flows

The twelve configured shop lists use one search for names, IDs, contact details and references. Lists with date or status fields also recognize dates and supported status words. Existing Filter dialog values remain active. Queries use Frappe's permitted fields, row permissions, pagination and count logic. Search and the Owner sidebar context survive refresh. Search controls have a magnifying-glass icon and clear action. The supplied logo sits left-aligned above the sidebar title.

Owner navigation includes Repairs and Products. `navigation.add_owner_repairs` and `navigation.add_owner_products` update only those links and the Restock label, preserving other navigation and access. Product forms use the existing Item manager. Everyday list menus omit import, permission, customization, quick-filter and list-settings shortcuts. Reports remain available. Users also has a Shop access shortcut.

Add Sale offers Product sale or Repair. Plain new sales route to POS or repair intake. Prefilled records, mappings, returns and initialization callbacks keep the original creation path. Empty POS baskets show one message with the licensed unDraw Empty cart illustration and cannot enter checkout. See `moniepoint_pos/public/images/undraw-source.md` for the asset source and license.

New Restock forms reveal products after supplier selection, then totals and payment after a product is added. Earlier details stay editable. There is no step counter or Continue button. Supplier references are optional. Paid now reveals the payment method and amount, with Pay by retained for unpaid or partly paid purchases. Saved records, returns and More fields retain the broader form. Defaults come from the only readable active client checkout profile. No stock is posted by opening the form.

Users shows Details, Access and Password, retaining core role assignments and password actions. Shop access focuses the existing permission manager on shop screens and roles. View, Add, Edit, Confirm and Print are shown, with Own records only preserved. Higher permission levels, other roles and technical rights remain in More options. Changes use the core permission endpoints and save immediately when an operator edits them. This presentation change did not alter saved permissions or grant users access.

Rendered review covered desktop list menus, Owner Products, user details, sale choices and progressive Restock, plus phone sale choices, Restock payment and Shop access. No tests, lint, builds, compilation, bundling or extra servers were run. No records, permissions, stock or payments were saved during review. Transactional and full failure-state validation remain deferred.
