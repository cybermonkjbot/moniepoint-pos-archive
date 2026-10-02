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
