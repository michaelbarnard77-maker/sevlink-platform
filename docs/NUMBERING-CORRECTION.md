# Request, quotation, job and invoice references

This supersedes earlier SQ/SI annual record-number instructions and the 0025
request-time SV numbering rule. No PDF generation or line-item calculation exists.

- New repair requests receive **REQ-0001**, REQ-0002, etc. UUIDs remain the database
  keys and secure links. REQ stays available after approval.
- Staff manually enter the quotation reference printed on the external PDF, for
  example **SQ-0001**. It is required on upload, draft edit and submission. Staff
  must inspect the PDF and confirm their entry matches it; the application does
  not OCR/verify printed text. No SQ number is suggested, allocated or incremented.
- Quotation references are reserved globally, ignoring case and surrounding
  spaces. Separate quotation series cannot claim the same reference. Use **Upload
  next revision** or **Request approved quotation amendment** for revised PDFs.
  The chain can retain the same printed reference, with an increasing revision,
  or use a genuinely changed external reference; previous PDFs/references remain.
  References previously used by a series remain reserved, including after edits.
- A successful authorised quotation approval allocates **SV-0001** etc within the
  same transaction as the decision/activity/notification. One locked global series,
  no annual or regional reset. Repeat decisions, retries and approved amendments
  do not allocate another number. Failed/rolled-back decisions issue no number.
- Staff manually enter invoice numbers matching external PDFs, for example
  **INV-0001**. New uploads/corrected invoices get no automatic SI record number.
  Historical SQ/SI record fields remain stored, never rewritten; UUIDs identify
  new document records. Payment/refund/void/correction history is unchanged.
- Approval alone never creates an appointment or confirms a payment. Normally
  confirmed, staff-recorded receipts must cover 50% of the effective approved
  quotation amount. The existing explicit, audited Super Admin scheduling
  arrangement remains the exception. Private subcontractor finances are separate.

## Existing data and migration 0027

Stop writers and back up SQLite plus private documents/configuration first.
Migration 0027 adds request references in creation order. It retains existing
numbers on requests with historical approved quotations. It removes premature
SV numbers from unapproved requests and saves their old six-digit display in
`legacy_job_reference`. UUID/SV-UUID links, existing documents, quotation reference
text, public snapshots, approvals, payments and users remain unchanged.
The SV sequence stays at or above the largest previously reserved number, so gaps
are expected and old numbers are never reused. An existing approved SV-000011 is
now displayed SV-0011; its old representation remains an alias. Scheduling search
accepts REQ, official SV, saved historical SV and UUID aliases.

Duplicate historical quotation references are retained. Conflicting reservations
block new reuse/submission until Operations reviews the original documents and
records a distinct externally issued reference in a permitted draft/new revision.
Already approved PDFs/decisions must not be changed. A revision/amendment can use
a new external reference without erasing historical conflicts.

Do not reverse 0027 on a populated database: it deliberately refuses to discard
issued reference mappings. Recover only through a coordinated, verified backup
restore of the matching code, database and private files. Never reset sequences,
delete records or edit numbered database rows to make the sequence gapless.

## Manual acceptance

1. Submit a request: REQ only, no official SV. Upload SQ-0001 manually and send it.
2. Reject/request revision: still REQ. Upload the next PDF through its revision
   workflow, retaining the external reference if it matches that PDF.
3. Approve as the authorised PM: one SV appears; REQ and UUID remain. Retry/stale
   approval must not produce another SV. Another agency cannot decide/download.
4. Approve an amendment: original PDF/decision remain and the same SV stays.
5. Before recording a deposit, scheduling must be blocked unless Super Admin
   explicitly records an agreed exception. Record a confirmed 50% receipt as
   authorised Sevlink staff, then schedule. Approval does not book anything.
6. Upload INV-0001 manually; verify totals, due date, receipts, outstanding balance
   and correction/refund history. Supplier invoices remain private to Sevlink.
7. Check overview, attention items, calendars and local notification previews show
   REQ before approval and SV afterwards. Actual outbound email stays disabled.

For a safe existing Windows SQLite update, follow
[the Windows update guide](WINDOWS-PM-DASHBOARD-UPDATE.md), including its backup,
configuration and post-migration checks. Windows acceptance is still manual.
