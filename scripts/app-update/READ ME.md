# K3LS shop update

Extract this ZIP to a folder on the Windows shop computer. Double-click `Update K3LS.vbs`.

The PowerShell window stays open. Wait for `Update complete`, then refresh the browser. Use the same Windows account that installed K3LS.

This update adds stock intake, piece counts, configurations, stock checks, fixing costs and grouped shop workflows. It keeps the existing username/password login, passwords and recovery codes. It does not generate replacement recovery codes or change account-security settings.

Accounts and Profit are now together in `Overview` on the owner's sidebar. Open an account to see its transactions. Use `Dates` to change the profit period. Money owed and Moniepoint settings stay separate.

`Checkout settings` is no longer in the sidebar. POS still uses the saved checkout configuration and payment methods.

Owner screens use navy backgrounds and light text throughout the workspace, including cards, fields, menus, dialogs, notifications, report tables and chart tooltips. Shop screens keep their white background and blue highlights. Printed receipts keep their paper layout.

Products now show stock in pieces. Each model/specification combination has its own product, count and prices. Open a product's `Stock` tab to restock, correct its count or add a configuration. `Mode` is optional. Existing products and serial-number records are kept separate.

`Receive stock` records the source, pieces, condition, prices and receipt. Staff can save a request. The owner reviews it and confirms the stock. Owned purchases create a Restock bill; opening stock creates a stock receipt. Other-owner products use separate zero-value stock records and an agreed owner payout.

`Stock checks` records arrival faults, fixing work, costs and the final condition. Serial-tracked devices are checked individually. Interchangeable pieces are checked together. Confirming fixing costs creates a supplier bill as well as updating product costs.

`Stock movements` groups stock by location, devices, handovers and count sessions. It also records stock with agents and repairers, expected returns and receiving staff. Approved missing-stock or write-off requests can remove selected serial-numbered devices.

`Requests` collects expense, correction, price-change and credit-sale requests. Confirmed expenses post accounting records and can be reimbursed through reviewed payments. Stopping a product or contact keeps its existing transaction history.

`Returns` links a customer return to the exact original sale line. The owner decides whether to repair, reject, refund or exchange it. An exchange records the return and refund first; its replacement is sold separately in POS. `Trade-ins` pairs received stock with an unpaid sale and posts the agreed settlement.

`Money we owe` includes supplier bills, older obligations, owner payouts and reimbursements. `Money owed` includes customer sale and repair balances. Add dated payment plans and record follow-up promises without replacing their original dates.

`Owner review` groups pending requests, receipt checks, stock and payment exceptions, account checks, deliveries, access reviews and action history. Its review can be exported, and its report links use ERPNext's existing ledgers.

Cash checkout remains immediate. For Moniepoint, FCMB and UBA payments, save the sale and add the payment reference and evidence. An owner must verify the payment check before checkout can finish. Later collections and supplier payments are posted from `Payments to check`. `Bank matched` is an owner's statement review, not a live bank feed or automatic bank confirmation.

In `Prices`, record purchase, delivery and repair costs per piece, plus the selling price. Repair cost is what the shop spends fixing its own product before sale, not what a customer pays for a repair. Expected profit subtracts all three costs from the selling price.

`Overview` shows product sales, product costs and product profit, including repair costs. Costs are saved with new sales so later price changes do not rewrite their profit. Older sales without a saved cost show profit as unavailable. Returns use the original sale cost. Accounting profit remains separate and is not reduced a second time by these pricing fields.

Barcodes are no longer required or shown in normal product, POS or Restock work. Existing barcodes and serial tracking are preserved.

`Password and recovery` now opens with a loading state and offers a retry if it cannot connect. Under `Users`, open a person and choose `Reset password` from any tab. Enter your admin password and their new password. The user's old password and email are not needed. `Guest` is the anonymous account and has no sign-in password.

It uses the installed WSL environment, needs no downloads and does not reinstall ERPNext. Sales, passwords, accounts and uploads remain in place. No workbook transactions, opening stock, opening bank balances or historical costs are imported by the updater. Enter those only from confirmed source records after installation.

Existing `Password and recovery` controls remain available. Generate a new code list only if replacing the user's previous unused codes is intended.

On the login screen, `Forgot password?` asks for the username, one recovery code and the new password. Existing passwords are not changed by installing the update.

The web server, scheduler and worker pause during the update. Run it when nobody is using the shop. Old app files, navigation and product settings are saved inside `/opt/k3ls/updates`. If configuration or server checks fail, the updater attempts to restore those files and settings. Newly added workflow tables, fields, their permissions and the empty reimbursement account stay in place. No stock is posted and no live shop database is restored.

The completion message confirms workflow metadata and login/asset checks. It does not certify every sale, return or permission path. Verify those on a separate copy before applying this release to the live shop.

Logs are in the extracted package's `update-logs` folder. Do not rerun the original full installer to apply this update.
