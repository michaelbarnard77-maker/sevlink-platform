# Subcontractor payments — external banking only

This requirement supersedes the banking section of Step 8.5. Sevlink has no
subcontractor bank model, bank form, bank-detail API or finance-access provisioning
command at the current schema. Historical migration definitions remain necessary
for safe upgrades. Negotiated rates/commission agreements, profiles, teams,
coverage, documents and assignment history are unchanged.

All transfers take place manually in the external business banking system.
Sevlink only records externally prepared supplier invoice PDFs and manual payment
amounts, dates and references. It never initiates, verifies or schedules a bank
transfer. No gateway, bank integration, payout or new paid service is introduced.

## Private invoice and payment workflow

1. Sign in as Sevlink Operations (existing active Super Admin authorization).
2. In Service areas, open a supplier's Profile & teams. Upload a private invoice
   PDF against a job previously assigned to that supplier. Enter the reference
   printed on the PDF, positive ZAR amount and due date. Existing PDF safety,
   size, private storage, authenticated download and rollback cleanup apply.
3. Make the actual payment outside Sevlink. Record its amount, date and external
   reference in the supplier profile or Supplier invoices & payments view. A
   nonempty reference is required. Partial/full payment status and net outstanding
   balance are derived from the existing immutable ledger; marking paid without
   recording payment amounts is not supported. Future-dated and excess amounts
   are rejected. Version checks, locks and submission keys prevent stale/duplicate
   payments. This is an accounting entry, not proof of transfer.
4. Use Supplier invoices & payments to filter outstanding, paid, void or all
   linked supplier invoices, with payment records and private PDF links. Open the
   job for existing refund, void, correction and financial audit controls.

The existing JobInvoice/InvoicePayment ledger and secure maintenance document
storage are reused. A nullable supplier link distinguishes supplier payables from
agency invoices and historical unlinked records. Linked invoices are permanently
Operations-only, enforced by a database constraint. PDF/header/supplier identity
remain immutable. Corrections preserve the supplier link; payment/refund/void
history remains intact. Supplier references are unique case-insensitively per
supplier, allowing two suppliers to use the same printed invoice number.

Agencies, PMs, tenants, ordinary staff and private-client accounts cannot read the
supplier ledger or documents. Internal supplier invoices never appear in external
job APIs. Existing historical unlinked invoices retain their original records and
job-based controls; they are not automatically attributed to a supplier and are
not included in the supplier-linked dashboard. No supplier attribution is guessed.

Bank details must remain in the external banking process. Do not put account
numbers in payment references, notes, agreements or contact fields. PDF storage
preserves original invoice bytes; it does not automatically find/redact banking
text. Obtain an externally prepared/redacted invoice copy if those details should
not be retained in Sevlink's private PDF storage.

## Safe retirement of legacy bank data

Observed workspace check: the local `portal/production/development.sqlite3` file
has no migration history and no `portal_subcontractorbank` table. No bank rows
were found there. No other development database was available/inspected; do not
interpret this as a global statement about other installations. No real bank
records were exported, modified or deleted by this work.

Migration 0018 checks the historical bank table **before any field/table removal**.
If any rows exist, it raises a count-only error and stops without removing bank
data. The UI/API are removed from the application independently; `/bank/` returns
404. Existing audit metadata is retained and contains no account values.
Obsolete bank-specific permissions are retired only after the guard succeeds.

If the guard reports rows, stop and propose this procedure to the data owner:

1. Use an authorised database operator to inventory the row count and affected
   supplier IDs in a restricted environment. Do not print account values into
   chat, terminal recordings, CI, issue trackers or repository files.
2. Agree the lawful retention/deletion policy and securely back up the database
   to approved encrypted storage with restricted access and a retention deadline.
3. Transfer/reconcile the necessary details into the approved external banking
   system, independently verify them and obtain written owner confirmation.
4. Obtain explicit approval to delete the legacy rows, including a plan for
   replicas, snapshots, backups and logs. Do not add an automatic purge/export
   to migrations. This approval has **not** been requested or assumed here.
5. The authorised operator performs a separately reviewed deletion transaction
   against only the retired bank table, records a count-only audit outside the
   bank data, verifies zero remaining rows and then runs `python manage.py migrate`.
6. Verify the bank table and obsolete permissions are removed and all supplier
   profiles, financial ledgers, assignments and PDF histories remain intact.
   Apply the approved retention process to legacy backups; table deletion alone
   does not securely erase database pages or backup copies.

Reversing schema migration 0018 can recreate an empty historical bank table; it
cannot recover deleted bank data. Recovery requires the separately approved backup
procedure. Do not reverse production/development financial migrations casually.

## Acceptance and automated verification

- Bank GET/POST routes return 404; no bank inputs or finance-grant command remain.
- Upload a synthetic supplier invoice; record partial and full external payments;
  refresh and verify outstanding/paid filters, dates, references and totals.
- Retry the same payment key, use an old version, omit the reference, or overpay:
  duplicate/stale/invalid writes must fail safely without additional ledger rows.
- Verify different suppliers may share a printed invoice reference while one
  supplier cannot duplicate it. Attempts to mark a linked invoice agency-visible
  are rejected by both API and database.
- PM/tenant/foreign-agency sessions must not obtain supplier documents or ledger
  data; job JSON must exclude supplier references and payment details.
- The migration regression inserts one synthetic legacy bank row, confirms the
  upgrade stops and preserves it, deletes that test fixture only, and verifies
  the empty upgrade succeeds and preserves the supplier.

Run the existing full checks (`SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh`) and
PostgreSQL CI. Existing maintenance, quotations, finance, supplier profiles,
compliance, team and concurrency regressions remain enabled. Manual owner
acceptance and real invoice/payment reconciliation remain necessary. No merge,
deployment, real email activation or paid services are authorised by this change.
