# K3LS app-style pass

Implemented 3 October 2026 over the existing shop screens. The goal is a small sales-and-repairs app that also works on desktop, without changing the accounting records.

## Scope

The shared shell affects POS, Repairs, Money owed, Accounts and the configured K3LS product, customer, supplier, purchase, payment, sale and settings forms/lists. Other ERP routes do not receive the new app-style tokens. POS uses two desktop columns; existing invoice grids keep their compact inputs.

The existing icon library and product photos are reused. No illustrations, product images, transactions, stock or customer balances were fabricated.

## Presentation

- Soft neutral canvas and white cards, with green-filled selections and primary actions.
- Rounded navigation items, product cards, account rows and dialogs.
- Larger header actions and pill-style form/category/status tabs.
- Phone navigation for POS, Repairs, Stock and More, using existing record read permissions.
- The phone dock is hidden while a dialog, text input or sidebar drawer is active. Content reserves space for the dock and device safe area.
- Dark-theme colours, visible keyboard focus and reduced-motion handling.

## Workflow preservation

The new dock uses existing routes and the Frappe drawer, not a second navigation system. Files, stock tracking, filters, permission checks and ledger records remain. Repair price/billing and Money owed stay owner-only. Money owed shows unpaid invoices, not customer credit-netted ledger balances.

Part-paid checkout retains customer, phone and due date. Collection checks the displayed balance under an invoice lock to reject repeated requests. Checkout uses one confirmation dialog and core save/server validation. Sales Invoice payments are returned unsaved for review; discounts, multiple payment terms and non-NGN account matching use the standard payment form.

## Review status

Source and diffs reviewed. Existing 1280 by 720 screenshots provided the starting POS and Repairs layout. The owner unpaid-balance empty state was previously inspected at 390 by 844. These captures precede the style pass and are not final acceptance evidence.

No web/database process was running during the final style work. The browser action was blocked, so desktop/phone comparisons, dark theme, keyboard/drawer behavior, populated rows and payment/repair completion are incomplete. No extra server, tests, lint, typechecks, build, compilation or bundling process was run.

The next review should use the running local site with the same data at 1280 by 720 and 390 by 844, then inspect the phone keyboard and navigation drawer. Financial transactions require a separately authorized verification pass.
