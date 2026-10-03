# Prices, profit and company banks

Owners can open Products, select a product and use Prices to see its cost price,
selling price and expected profit per unit. Edit prices opens a saved-record
dialog. Saving updates the existing cost metadata and K3LS Retail NGN Item Price.
It does not change stock valuation, historic invoices or accounting entries.
Expected profit subtracts cost and delivery from selling price, before other
expenses. Missing cost or selling price appears as Not recorded, not zero.

Owner Profit uses ERPNext's posted Profit and Loss records. A sale's payment
method or part-payment does not determine its profit. Record real stock costs
through Restock or valid opening stock, and record expenses, for accounting
profit to include them. Product cost metadata alone does not post stock cost.
Close the till to include unconsolidated POS sales in the accounting report.

FCMB account 2008133309 and UBA account 1029877525 are saved company Bank Account
records under K3LS LIMITED and link to their existing NGN ledger accounts.
`accounts.configure_company_banks` refuses to overwrite a different saved number.
It does not post balances or change passwords.

Cash, Moniepoint, FCMB and UBA are enabled for checkout and collections.
FCMB and UBA represent bank transfers already received. Their selection does
not call a bank, verify a transfer or charge a customer. Payment amounts must
reflect money actually received. Each method uses its existing company ledger.
The Accounts screen shows posted ledger balances, not live bank balances.

Source and running-preview review only. No test, build or financial transaction
was run. The Windows package includes these changes and the saved bank records.
