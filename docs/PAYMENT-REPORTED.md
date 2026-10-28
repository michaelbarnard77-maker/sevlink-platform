# PM payment notification and Sevlink verification

Outstanding, active agency invoices now have a **Paid** button for the scoped Property Manager and agency administrator. Clicking saves an append-only `InvoiceAction` claim, creates an Operations inbox item and staff job update, and changes the card to **Payment reported · Awaiting Sevlink verification**. It does not create an InvoicePayment, alter balances, approve a quote or verify a deposit.

Sevlink sees **Verify payment**, opening the existing receipt form. Staff must check the bank transaction and record the actual received amount/date/reference. This resolves the claim. If only part was received, the remaining balance can be reported again. Quoted-job deposit allocation verification remains a separate existing scheduling gate.

The current invoice status remains Unpaid/Part-paid until staff records money. Claims are rejected for tenants, staff, unrelated PMs/agencies, private supplier invoices, void/held/settled invoices and stale versions. Repeated clicks/retries create one pending claim and one notification. Full historical claim records remain in the private financial audit history.

No schema migration is required; the existing append-only action and notification tables are reused. No real email is enabled or sent by this change. Operations notifications are durable and visible locally even with live email disabled.

## Local installation

Stop the existing local Django CMD server with Ctrl+C. Copy the Raw contents of `scripts/update-windows-payment-reported.ps1` into PowerShell and press Enter. It backs up and verifies four existing source files, refuses a running target server, and does not replace the database or uploads. Restart the existing CMD server with `python -X utf8 manage.py runserver 127.0.0.1:8000`, close the job, Ctrl+F5, and reopen it. This installer is source-payload verified; Windows PowerShell execution must be confirmed on the owner's computer.

## Verification

Focused tests cover money unchanged, notification/retry deduplication, role/portfolio/private-document restrictions, stale/void/hold guards, staff receipt resolution and new claims after partial receipts. Authenticated browser proof uses real Django APIs and an isolated SQLite database with synthetic test accounts and invoices; it is not a screenshot of the owner's Windows database.

Browser result: 82 authenticated/source screenshots passed, including PM Paid button, pending claim, staff Verify payment, unchanged funds and locked attendance until existing verification. See `visual-proof/payment-reported-2026-10-28/`.

Full regression: 270 tests, 18 PostgreSQL-only skips; all remaining tests passed. JavaScript syntax, Django system checks and migration drift checks passed.
