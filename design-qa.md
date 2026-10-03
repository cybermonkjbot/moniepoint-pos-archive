# K3LS interface review

Reviewed 3 October 2026 against the running local ERPNext site. No tests, builds, bundling or new verification servers were run. No transactional records were created.

## Evidence

Evidence directory: `/Users/joshua/.codex/visualizations/2026/10/02/01a0fe36-90f9-7223-9937-14a79bf781f1`.

- Source capture: `accounts-before.jpg`, 1280 x 720 pixels.
- Implementation: `accounts-desktop-final.jpg`, 1280 x 720 pixels.
- Combined comparison: `accounts-comparison.jpg`, 2576 x 720 pixels, two unscaled captures separated by 16 pixels.
- Phone implementation: `accounts-phone-final.jpg`, 390 x 844 pixels, matching CSS viewport.
- Checkout implementation: `checkout-settings-desktop-final.jpg`, 1280 x 720 pixels, and `checkout-settings-phone-final.jpg`, 390 x 844 pixels.
- Notifications implementation: `owner-notifications-final.jpg`, 1280 x 720 pixels.
- Earlier repair intake evidence: `repair-phone-device-final.jpg` and `repair-phone-problem-final.jpg`, 390 x 844 pixels.

Accounts comparison uses the same route, Administrator, navy owner palette, empty transaction state and viewport. Browser captures have one screenshot pixel per CSS pixel. The paired image was opened together for direct comparison. Card text and icons were also inspected in the individual full-resolution captures, so a separate cropped region was not needed.

Checkout's before capture is 1122 x 1134 rather than 1280 x 720. `checkout-comparison.jpg` therefore documents content removal only, not measured visual fidelity. The saved Mobbin capture also differs in viewport and product state from the repair intake. `mobbin-repair-comparison.jpg` is not a valid fidelity baseline.

## Findings and iteration history

- The initial desktop owner sidebar clipped lower links at 1280 x 720. Compact-height spacing was adjusted, without reducing the phone targets. Revised captures show all nine navigation links, Notifications and the account control. Scrolling remains available for shorter windows.
- Moniepoint Terminals initially left the connection form visible. The container selection was corrected to include the form page. Direct inspection now shows only the selected section. Add terminal opens a dialog defaulting to K3LS Shop, Moniepoint, Card or transfer and terminal off. The dialog was cancelled without creating a record.
- Accounts formerly showed five banks, a repeated heading and two date lines. The final paired comparison shows Cash and Moniepoint only, with no date lines or Accounting details menu. These are intentional removals requested by the user. Account details still open an empty transaction dialog.
- Checkout formerly exposed bank-row editing, currency, ledger, write-off, tax and stock settings. Final inspection shows two payment cards only. Country, disabled and printing controls retain saved values but are hidden. More fields remains an administrator escape hatch.

## Required visual checks

- Typography: Existing app font retained. The compared Accounts cards preserve readable label and balance sizes, with no clipping at wide or phone widths.
- Spacing: Account cards preserve width, radius and alignment. Intentional content removal reduces vertical density. Phone cards stack, with balances below labels. Checkout payment cards also stack.
- Colors: Owner navy and light text remain consistent in both comparison captures. Shop product and repair views use white surfaces with blue selection.
- Assets: Moniepoint uses the unchanged source SVG and viewBox-cropped brand mark. The supplied loading bitmap is cropped vertically only; the actual transient splash appearance remains unverified.
- Copy: Repeated Cash/Bank subtitles, account date lines and unused setup labels are removed. Missing ledger activity says No transactions yet rather than presenting a fabricated balance.
- Interactions: Account details open and close. Checkout navigation opens the only active profile. Moniepoint section switching and terminal-dialog cancellation work. Notifications open beside the account with one category. Phone drawer closing and persistent navigation were inspected.

## Remaining gaps

The scoped Accounts simplification has no remaining actionable visual findings in the captured empty state. Populated balances, long transaction rows, text scaling and keyboard traversal remain unexercised.

The wider repair/POS design pass has no matching-state, matching-viewport source comparison. Real repair saves, customer lookup, uploads, populated POS payment selection, receipts, mobile notification focus, and the loading splash were not exercised. Live integration remains disabled. Earlier socket polling errors were present before these changes; a clean-console pass is not claimed.

## Completion checklist

- Accounts date lines and unsupported banks removed from the visible page.
- Cash and Moniepoint retained; bank masters, shifts and invoice history preserved.
- Checkout settings reduced; tax setup controls hidden, calculations and nonzero disclosures preserved.
- Obtain matching-state reference evidence before claiming full repair/POS design fidelity.
- Verify transactional and populated states only in an explicitly authorized validation pass.

final result: blocked

Blocker: Full repair/POS visual fidelity cannot be established from the available mismatched source captures. This does not negate the directly inspected Accounts and checkout simplifications.

## Additional scoped review on 3 October 2026

This pass covers focused lists, sale choices, Restock progression, Owner navigation and Shop access. It does not resolve the wider fidelity gaps above.

Desktop evidence at 1280 x 720 includes `products-search-before.jpg`, `products-search-final.jpg`, `customers-search-logo-desktop-final.jpg`, `users-details-before.jpg`, `users-access-final.jpg`, `sales-owner-before.jpg`, `new-sale-owner-final.jpg`, `pos-empty-basket-final.jpg`, `restock-supplier-final.jpg`, `restock-products-payment-final.jpg`, `permissions-before.jpg`, `permissions-desktop-final.jpg`, `products-owner-final.jpg` and `sales-menu-owner-final.jpg`.

Phone evidence at 390 x 844 includes `new-sale-phone-final.jpg`, `restock-payment-phone-final.jpg` and `permissions-phone-final.jpg`. Temporary viewport overrides were reset after inspection. Intermediate screenshots can predate the final Restock/sidebar copy; the specifically named Restock and Sales menu captures show those removals.

- One search returned the known product ID, category and active status. Clearing it retained the existing Active filter. Refresh preserved search. Customer and User lists also showed one search. Populated Restock records and invalid-date recovery were not exercised.
- Add Sale opened the two-choice dialog from Shop and Owner lists. Product sale returned to the empty basket without setup-field errors. Repair opened intake directly. The phone chooser rendered as a bottom sheet.
- Restock initially showed supplier and date only. Supplier selection revealed products; choosing a product with nonzero quantity revealed totals and Payment. Paid now revealed method and amount controls. Phone payment stacked without an overlapping drawer. None of these drafts was saved.
- Owner Products opened the existing product list and stayed in the Owner view after refresh. Owner Repairs remained in the sidebar. Lower Owner links are scrollable at short desktop heights; this pass adds links rather than removing any.
- The final Sales list menu showed Report only. Import, User Permissions, Role Permissions Manager, Customize, Edit DocType, Customize Quick Filters and List Settings were absent.
- Shop access showed screen and role selectors, shorter permission labels and no permission-level column. More options restored technical rules. Add access opened a two-field dialog and was cancelled. The phone layout stacked the table cells. No checkbox, reset, add or remove operation was applied.
- User Details had full-width readable fields. Roles, passwords and account values were not changed. The supplied logo was left-aligned above the workspace title.

Remaining gaps include record save/submission, stock posting, payment collection, role-change behavior under restricted users, full form-load failure recovery, keyboard/text-scale coverage and full mobile theme coverage. Existing socket polling errors remain. These checks used the already-running site; no tests, lint, typechecks, builds, bundling, compilation or additional servers were run.
