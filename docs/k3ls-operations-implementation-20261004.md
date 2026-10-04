# K3LS implementation status

October 4, 2026. This records the source changes following the workbook audit at revision `0403cf0`. It does not replace the original audit's record of what was missing before implementation.

## Source changes

| Area | Workbook sheets | Implementation |
| --- | --- | --- |
| Products and intake | 10, 11, 19, 20, 23, 30, 40 | Piece counts, model/specification/Mode/colour, source registration, stock ownership, receipt evidence, owner review and linked purchase or stock receipts. Existing item and invoice IDs remain separate. |
| Stock checks and fixing costs | 12, 39 | Arrival testing and fault checklist, fixing work and parts/labour/other costs, supplier bills, final condition and verification. Individual serial devices retain separate costs. |
| Stock custody and counts | 4, 7, 13, 22 | Location inventory, transfers, repairer and agent handovers, expected returns, receiver acknowledgement, agent settlement and approved count corrections. Missing or written-off serial devices use a stock issue. |
| Other-owner stock | 37, 38 | Zero-value custody stock, source agreements, frozen sale payout amounts and dates, accruals and verified payouts. Returning all remaining stock preserves earlier sales and unpaid payouts. |
| Sales and customer repairs | 1, 3, 5, 12 | Saved credit-sale approval, bank-payment evidence before checkout, repair follow-up and external custody, confirmed repair billing and fixing-cost bills. Collection requires a confirmed bill and an agreement when unpaid. |
| Returns and trade-ins | 6, 31 | Original-sale and serial checks, owner decisions, accounting credits, debt offsets, refunds, separate replacement checkout and paired trade-in settlement. |
| Debts and payment plans | 24, 32, 33, 35, 36 | Older evidenced obligations, supplier/customer balance views, dated instalments, original/revised promises, follow-up and verified receipt allocation/reversal. |
| Payments, expenses and accounts | 14, 21, 27, 29, 34 | Expense approvals and reimbursements, reviewed receipt posting, unique bank references, manual statement-match dates, account differences and evidenced opening balances. |
| Reviews and reports | 8, 9, 15, 16, 17, 18, 25 | Grouped exception measures, staff-safe operational records, owner-only financial fields, access reviews, before/after action history and CSV review exports. Existing accounting/stock reports remain available. |
| Deliveries | 28 | Related sale or repair, addresses, rider costs, charge, delivery proof, unpaid bills and guarded cancellation. |
| Replaced workbook processes | 2, 26 | Native shop flows replace spreadsheet instructions and email forms. Staff remains user management. Payroll, salaries and commission remain excluded by the user's earlier choice. |

The Owner workspace now uses navy backgrounds for its canvas, cards, fields, menus, dialogs, notifications, tables and chart tooltips. Shared pages retain the Owner theme while the Owner sidebar is selected. The Shop workspace stays white with blue highlights. Receipt paper and uploaded images keep their original colours.

Overview now includes product sales and product profit over time, plus the five best-selling products by net pieces sold. The same submitted-sale rows supply the totals and charts. Returns reduce both amounts and pieces. Saved costs include purchase, delivery and fixing costs. Profit is unavailable when a sale has no saved cost. Charts group by day, week or month according to the selected dates and offer dated figures alongside the graph. A period with no product sales shows one empty-state message rather than blank axes.

The stock-intake dialog now keeps its stage fields separate from the layout sections Frappe inserts, preventing the first stage from hiding its own inputs.

## State of verification

- Source and diffs reviewed. No tests, lint, compilation, builds or package exports were run. The existing local app was started without a build watcher.
- A database, site-config and uploaded-file backup was saved before configuration, with prefix `20261004_183958-development_localhost-` in the site's private backups folder.
- Additive product/workflow configuration was applied locally. Readiness reported `ready: true`, 20 workflow types and no missing requirements at schema revision `20261004-9`. No workbook transactions, opening balances or client records were imported, and no stock was posted.
- Overview was inspected at the existing desktop viewport and 390px mobile width. Navy cards, loading and empty states, date changes and the mobile layout were confirmed. Before/after screenshots show the empty-state refinement. The empty chart axes rendered before being replaced with one message. This site has no submitted product-sale invoices, so populated charts, best-seller links, missing-cost figures and chart tooltips remain unverified in the browser.
- The receive-stock dialog's first-stage inputs are visible again. Its remaining stages and saving/posting flows still need transactional verification.
- No remote Windows installation or transactional verification was performed. No update ZIP was generated or sent.

The local additive configuration entry point is `moniepoint_pos.operations_schema.setup`. `moniepoint_pos.operations.configuration_status` reports required workflow metadata and permission readiness. Both were executed locally. These checks do not establish that every business flow works.

The v9 Windows updater source carries the new modules and page. It pauses web, scheduler and worker together, saves previous source/settings, configures additive product/workflow metadata, then checks metadata, login and assets. It leaves current Windows users, passwords, recovery codes, database and uploads intact. It does not restore the Mac database. Configuration rollback retains additive metadata and its permissions plus an empty reimbursement account.

## Boundaries requiring a verification pass

- Bank checks are manual owner verification, not automatic Moniepoint, FCMB or UBA settlement confirmation. The terminal integration remains separate.
- Simplified receipt flows enforce verification. Original accounting forms and Journal Entries are not universally restricted to those workflows. Confirm role access to all direct accounting paths before promising a universal evidence gate.
- Serial/batch bundle handling, POS consolidation, partial returns, refunds and reversals require end-to-end verification against ERPNext 16.37.0 and Frappe 16.36.1. Batch stock remains outside the simplified intake/count flow.
- Owner returns currently close all remaining pieces. Partial returns to a stock owner and resale after closing an agreement need additional handling.
- An owner agreement's overdue flag uses its earliest unpaid sale date; do not treat the entire agreement balance as a date-by-date overdue amount.
- Product sale costs freeze at submission. A partial return from a multi-device line currently copies that line's average cost, not an independently frozen serial-specific return cost. Historical devices use recorded acquisition costs where available; missing acquisition facts remain unverified.
- Data-heavy dashboard and inventory paths need performance review with the client's actual record counts.
- The 40 workbook sheets map to grouped workflows. This is not a claim that every formula, administrative exception or historical row has been reproduced.

## Missing client facts

Keep these unresolved until the owner supplies evidence:

- Surface serial `010988293157`, purchase NGN 350,000, delivery NGN 5,000 and planned selling price NGN 450,000. Fixing cost and final test result remain unknown.
- The Surface's trade-in source and paired original sale.
- Dates, payment evidence and suppliers for the five MIKUSO mice at NGN 6,500/10,000 and five unbranded mice at NGN 5,500/8,500.
- Goshen's ownership agreements and payouts. Its stock must not be assumed to be purchased by K3LS.
- Confirmed bank opening balances and genuine older debts, without duplicating existing invoices.

The rejected QA inbox row remains excluded. Cash, Moniepoint, FCMB `2008133309` and UBA `1029877525` retain the existing K3LS LIMITED setup.
