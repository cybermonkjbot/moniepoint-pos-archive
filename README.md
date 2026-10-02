# Moniepoint POS

ERPNext custom app for API-key terminal integration. Disabled by default.

After installation, a System Manager configures Moniepoint Settings and a Moniepoint Terminal for each POS Profile. Credentials are Frappe Password fields and remain server-side. Only the published production API-key contract is implemented. Legacy client-ID token exchange is not implemented.

Confirm amount units with Moniepoint before enabling requests. A saved NGN draft POS Invoice needs exactly one positive payment row matching the terminal's Mode of Payment.

Authenticated POST methods:

- `moniepoint_pos.api.check_credentials`
- `moniepoint_pos.api.request_payment` with `invoice` and `terminal`
- `moniepoint_pos.api.check_payment` with `transaction`

The app persists a unique merchant reference before sending a request. Unknown outcomes stay unresolved and block further charges for that invoice, including concurrent requests. There is no automatic retry, refund, cancellation or invoice settlement. An accepted request is not proof of payment. Do not manually submit an invoice as paid based only on this app's provider status.

Installed on the local `development.localhost` site. Open `/desk/moniepoint-settings` for credentials, `/desk/moniepoint-terminal` for terminal mappings and `/desk/moniepoint-transaction` for request records. Integration remains disabled until configured.

There are no checkout UI changes or webhook endpoint. Payment-success mapping, reconciliation and authenticated webhooks remain unimplemented. No live API calls or tests were performed.

## K3LS navigation

`moniepoint_pos.navigation.configure` sets up the focused Shop and Owner navigation with distinct icons. To refresh only the icons on existing K3LS workspaces, run `moniepoint_pos.navigation.apply_icons` as a System Manager. This preserves links, order and record permissions.

Shop uses a storefront and Owner uses a shield. Each sidebar section has its own Lucide symbol. Desktop SVGs include solid and subtle variants in `moniepoint_pos/public/icons/desktop_icons`. The adapted Lucide geometry retains its license in `moniepoint_pos/public/icons/LICENSE`.

## K3LS shop setup

`moniepoint_pos.shop_setup.configure` installs the repair register, workbook device metadata, sale-condition fields and K3LS receipt. It sets the till to create POS Invoices, matching sales history and the terminal integration. Run it as a System Manager after the client masters and K3LS navigation exist.

The opening screen selects K3LS Shop automatically and asks only for counted drawer cash. Bank payment methods start each new shift at zero, not the bank's account balance. No shift is created by the setup command.

Repairs has Details, Progress and Price and payment sections. Customer contact, device condition and repair work are recorded separately from the invoice ledger. An owner can create one draft invoice from an approved price. The Payments screen keeps ERPNext's payment accounting. Repair staff cannot access the price or cost fields. No staff accounts have been created or granted this role.

Sales require recorded condition, testing, customer acknowledgement and a disclosure reference before submission. Third-party sales are blocked until an owner payout workflow is implemented. Device purchase and landing costs are workbook metadata, not opening-stock values or posted liabilities.

Applied to the local site. Inspected the opening screen at wide and narrow widths, the repair tabs and the populated stock form. No tests, builds or bundling were run. Transactional checkout, repair billing and staff-only rendering remain unverified. Stock posting, confirmed drawer cash, staff identities and live Moniepoint credentials remain outstanding. Consignment, dispatch, instalment and owner payout controls are not complete.

## Shop screens

`moniepoint_pos.shop_ui.configure` applies short labels and focused list columns. The browser customization is active only on the K3LS site. Products, Repairs, Customers, Suppliers, Purchases, Sales, Payments and till settings hide unrelated fields. An owner can reveal the original fields through Menu > More fields without saving any record.

Headers use one page heading instead of breadcrumbs. Everyday lists open as lists rather than the last report or board view. The view selector, saved-filter selector and supplier/customer report and creation menus are not shown in the header. Owners can open the report from the list menu. Essential filters, exports, confirmations and accounting permissions remain intact.

Routine forms omit comments, activity, assignment, sharing, tags, likes and edited-by panels. Files and product photos remain available. Repairer assignment is a repair field, not a generic task. The K3LS sidebar menu omits Website, Edit sidebar, Display, Session defaults and Help.

Shop uploads omit web links and the bulk privacy switch. Existing attachment privacy defaults are unchanged. The first UI configuration stores a private metadata backup named `k3ls-ui-before-cleanup.json`; restoration is manual.

The till resumes an existing open session on refresh. Its displayed date follows the site timezone, and POS draft sales take the current shop date when saved. A new day does not automatically close the till, invent cash counts or reconcile money. A till that has never been opened still requires the first drawer cash count.
