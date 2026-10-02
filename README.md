# Moniepoint POS

ERPNext custom app for API-key terminal integration. Disabled by default.

After installation, a System Manager configures Moniepoint Settings and a Moniepoint Terminal for each POS Profile. Credentials are Frappe Password fields and remain server-side. Only the published production API-key contract is implemented. Legacy client-ID token exchange is not implemented.

Confirm amount units with Moniepoint before enabling requests. A saved NGN draft POS Invoice needs exactly one positive payment row matching the terminal's Mode of Payment.

Authenticated POST methods:

- `moniepoint_pos.api.check_credentials`
- `moniepoint_pos.api.request_payment` with `invoice` and `terminal`
- `moniepoint_pos.api.check_payment` with `transaction`

The app persists a unique merchant reference before sending a request. Unknown outcomes stay unresolved and block further charges for that invoice, including concurrent requests. There is no automatic retry, refund, cancellation or invoice settlement. An accepted request is not proof of payment. Do not manually submit an invoice as paid based only on this app's provider status.

This patch implements backend code and DocType definitions only. It is not installed on the local site yet. There are no checkout UI changes or webhook endpoint. Payment-success mapping, reconciliation and authenticated webhooks require the confirmed provider contract before activation. No live API calls or tests were performed.
