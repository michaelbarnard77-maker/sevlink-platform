# PM payment notification and Sevlink verification

Outstanding, active agency invoices now have a **Paid** button for the scoped Property Manager and agency administrator. Clicking saves an append-only `InvoiceAction` claim, creates an Operations inbox item and staff job update, and changes the card to **Payment reported · Awaiting Sevlink verification**. It does not create an InvoicePayment, alter balances, approve a quote or verify a deposit.

Sevlink sees **Verify**. After checking the bank transaction, staff clicks it to confirm the complete current invoice balance. The server records a receipt with the invoice reference, staff identity and verification date, leaving zero outstanding. No manual-entry form is shown for agency invoices. Existing staff partial-receipt APIs and historical entries remain supported. This resolves the claim. Quoted-job deposit allocation verification remains a separate existing scheduling gate.

The current invoice status remains Unpaid/Part-paid until staff records money. Claims are rejected for tenants, staff, unrelated PMs/agencies, private supplier invoices, void/held/settled invoices and stale versions. Repeated clicks/retries create one pending claim and one notification. Full historical claim records remain in the private financial audit history.

No schema migration is required; the existing append-only action and notification tables are reused. No real email is enabled or sent by this change. Operations notifications are durable and visible locally even with live email disabled.

## Local installation

Stop the existing local Django CMD server with Ctrl+C. Copy the Raw contents of `scripts/update-windows-verify-and-close.ps1` into PowerShell and press Enter. It backs up and verifies four existing source files, refuses a running target server, and does not replace the database or uploads. Restart the existing CMD server with `python -X utf8 manage.py runserver 127.0.0.1:8000`, close the job, Ctrl+F5, and reopen it. This installer is source-payload verified; Windows PowerShell execution must be confirmed on the owner's computer.

## Verification

Focused tests cover money unchanged, notification/retry deduplication, role/portfolio/private-document restrictions, stale/void/hold guards, staff receipt resolution and new claims after partial receipts. Authenticated browser proof uses real Django APIs and an isolated SQLite database with synthetic test accounts and invoices; it is not a screenshot of the owner's Windows database.

Browser result: 82 authenticated/source screenshots passed, including PM Paid button, pending claim, staff Verify payment, unchanged funds and locked attendance until existing verification. See `visual-proof/payment-reported-2026-10-28/`.

Full regression: 270 tests, 18 PostgreSQL-only skips; all remaining tests passed. JavaScript syntax, Django system checks and migration drift checks passed.

## One-click verification and closure

The authenticated Super Admin's Verify action calculates the outstanding balance inside the existing locked payment transaction; clients cannot supply a different amount/date. It preserves the original invoice PDFs and numbers, and records one auditable receipt. Paid invoices have no Verify or manual-entry control. Supplier accounting remains unchanged.

The existing completion and finance guards still control automatic closure: a completed job with accepted completion evidence, an active final invoice, all active agency invoices settled and no reconciliation hold moves to Closed. A deposit alone does not close unfinished work. The current dashboard/register refreshes after verification, and both invoice cards remain visible.

New local installer: `scripts/update-windows-verify-and-close.ps1`; stop the local server first. It replaces four backed-up source files without schema migrations or database replacement. Embedded payloads are verified; Windows execution must be confirmed by the owner.

One-click browser acceptance: 84 authenticated/source screenshots passed, including the actual final invoice Verify click, both saved deposit/final invoices showing zero outstanding, Closed status from the authenticated detail API, and unchanged tenant/agency privacy. Evidence: `visual-proof/verify-and-close-2026-10-28/`.

Latest regression run: 272 tests; 18 PostgreSQL-only skips. One obsolete browser assertion expected the previous manual partial receipt of R250; the new browser action correctly verified the full R1,000 invoice. Updated that assertion and reran all five authenticated maintenance browser tests: all passed. The other 253 tests in the full run passed. The 14 targeted payment/operational tests also passed. Source scenario suites, JavaScript syntax, Django checks and migration drift checks passed.
