# Quotations, invoices, conversations and Operations inbox

Current business rule: **quotations and invoices are prepared externally and manually uploaded as PDFs**. This guide supersedes the earlier line-item/VAT/PDF-generation design. Work remains on `development/phase-1-foundations`; draft PR #1 is not merged. No deployment, payment gateway, live email or paid AWS service is activated.

## Connected screens and permissions

The existing `/login/` and `/maintenance/` workspace uses Django authentication, CSRF and the configured database. The public website and original `portal/dist/` demo/assets/styles are unchanged.

| Authenticated screen/control | Saved backend behaviour |
| --- | --- |
| Report a repair, register, status and timeline | Existing requests, scoped property/tenant access and audit history |
| Operations Upload quotation PDF | Reference, manually entered ZAR amount, optional title/scope, upload timestamp and revision number |
| Send for approval | Makes the uploaded draft visible to the authorized PM/agency administrator |
| Approve / Reject / Request revision | Required comment, acting user/time, permanent decision history, Operations inbox and local email queue |
| Operations Upload revised quotation | A new PDF and numbered revision; supersedes the prior unapproved revision without replacing its file |
| Download quotation PDF | Exact uploaded PDF bytes, authenticated and authorized; nothing is generated |
| Operations Upload invoice PDF | Invoice number, manually entered ZAR amount, due date, upload timestamp and visibility |
| Operations Record manual payment | Append-only payment amount/date/reference/private note; unpaid/partially paid/paid state and outstanding balance |
| Invoice card and download | Authorized PM/agency administrator can view agency invoices and recorded payment progress; private supplier invoices are Operations-only |
| Job conversation/files | Persistent shared comments and private Operations notes; per-job tenant conversation permission |
| Super Admin bell/feed | Important events, agency/job/time/link, persistent per-user read/unread receipts |

Operations access currently means an active Django Super Admin (`is_superuser`). Plain `is_staff` does not grant global access. PMs see their assigned properties, agency administrators their agency, and tenants only their own reports with matching agency and active tenancy. Other agencies, unrelated PMs and cotenants receive no job/document access.

Tenants do not receive quotations, invoices, payment records or commercial activity through API responses or direct downloads. They retain the existing reporting/status workflow and permitted shared conversation. Disabling tenant conversation access hides comment text/activity/comment files and blocks posting/downloading; original report attachments and job status remain accessible.

## Uploaded quotations

Each new quotation requires **exactly one validated PDF**, reference and recorded total in ZAR. Title and public scope are descriptive metadata. Values accept exact positive Decimal amounts with at most two decimal places, within the existing currency range. Sevlink does not read amounts from PDFs, calculate line items, calculate VAT or validate accounting/tax contents: Operations must ensure the entered amount/reference match the external document. No OCR, electronic signature or automatic tax invoice generation exists.

Quotation states remain Draft, Sent for Approval, Approved, Rejected, Revision Requested and Superseded. Operations may edit draft reference/amount/title/scope before sending; the file itself cannot be replaced. A changed document requires a new revision with its own PDF. Rejected/revision-requested/sent unapproved quotations can be superseded by a newly uploaded revision. Revision numbers increase automatically within a series.

Sending freezes public metadata and the document identity/SHA-256 in a saved snapshot. Only authorized PMs/agency administrators can decide the current sent revision, using its current version and a required comment. Decisions are idempotent and transactional. Row locks plus version checks prevent concurrent decisions or stale approvals. Operations cannot approve on an agency's behalf. Approved quotations cannot be edited, superseded or decided again; the original PDF remains downloadable in job history. No ordinary user has a document/history deletion endpoint.

All important decisions (approval, rejection, revision request) create exactly one job activity, Operations inbox item and durable email queue entry in the same transaction. Worker delivery sees only committed events. Failed delivery cannot undo the decision.

**Legacy preservation:** migration 0010 adds document/reference fields without deleting prior quotations, calculations, amounts, decisions, snapshots or action history. Historical line/VAT tables remain solely to preserve earlier development records; current APIs/forms never create or calculate those lines. No legacy PDF is fabricated. Records without uploaded PDFs are clearly labelled and cannot be approved, sent, edited or downloaded as if a document existed. An unapproved sent/rejected/revision-requested legacy record can receive a newly uploaded revision. Legacy drafts/approved records without files remain historical; start a new uploaded quotation for those records instead of silently attaching a document to an old approval. An approved amendment/cancellation workflow is future work.

## Uploaded invoices and manual payments

Operations uploads an external PDF, invoice number, positive ZAR total and due date. Invoice visibility defaults to **Operations only — private subcontractor invoice**, both in the API and upload screen. Agency-facing Sevlink invoices require explicitly selecting **Agency-visible Sevlink invoice**. Visibility, PDF and recorded invoice header cannot be changed after upload, preventing a private invoice being accidentally republished later. Invoice numbers cannot be repeated for the same job/visibility, including case variants.

Invoices may be uploaded after job completion or cancellation, so manually received paperwork can be recorded without reopening the job. An invoice upload does not automatically create any payment, alter the job or notify Operations about its own upload.

Record received payments manually through the invoice card: amount, actual payment date, optional reference and private note. The server appends a user/timestamped ledger entry and updates recorded paid/outstanding amounts and payment status atomically. Unpaid means no recorded payments, Partially paid means some amount remains, and Paid means recorded payments equal the invoice total. Overpayments, nonpositive/excess-precision amounts, future payment dates, duplicate submissions and stale-version submissions are rejected. Two operators cannot record conflicting payments from the same stale invoice state.

These are **manual records**, not bank verification, settlements or automatic payment collection. There is no payment gateway, bank feed, automatic invoice creation, invoice numbering service, receipt generator or automatic tax invoice. PMs/agency administrators cannot change invoices or mark them paid. They see only agency invoice/public payment progress, not private payment references/notes or internal staff identities. Invoice uploads/payments have permanent activity and ledger history; private invoice events are private too.

Corrections, voids, refunds, credit notes, reversing erroneous payments and replacing mistaken invoice headers/PDFs require a future explicit audited workflow; existing ledger/header rows cannot be silently edited/deleted. Double-check manual entries before saving.

## Confidential subcontractor material and storage

Internal supplier quotations and cost/rate details belong in **Operations-only job notes**, with PDFs attached there. Existing private quotation costing/history is retained in `QuotationPrivate` and never included in external serializers. Supplier invoices use the explicit Operations-only invoice option. Private comments/files, invoice rows, payments and associated activity are absent from agency/PM/tenant API responses and direct-download access.

Agency-visible quote uploads are intentionally external-facing. Sevlink cannot infer that someone uploaded the wrong private supplier PDF or pasted confidential costs into shared text. Operations must choose the correct visibility/channel and upload an agency-safe document. No automatic content redaction is claimed.

Commercial documents reuse the existing `maintenance_private` storage alias, validator, UUID paths and protected streaming response. One PDF per upload, up to **5 MiB**; encrypted/active-content PDFs and unsupported types are rejected. Original accepted PDF bytes are preserved. File hashes and uploaded timestamps are recorded. Files have no public media/storage URL and are served with no-store, nosniff and sandbox headers. Filesystem storage uses exclusive creation and restrictive permissions; future S3 integration can reuse the alias but is not enabled.

Quotation/invoice PDFs are separately classified and excluded from **all general job attachment lists and URLs**, including for Operations. Their dedicated download endpoints perform quotation/invoice authorization. Consequently draft quotation or private invoice files cannot bypass permissions through a tenant's attachment download URL. Commercial documents do not consume the tenant's general-photo quota. Failed transactions clean up newly stored files.

Approved PDF retention is enforced in application workflows with protected relationships, immutable document/header guards and append-only history. Actual long-term durability still requires protected backups, restore testing and future object retention/versioning. Database/filesystem administrators retain direct powers; this is not WORM archival storage. Malware scanning/CDR, retention automation, storage-wide quotas and orphan reconciliation remain future work.

## Operations inbox, comments and local email

The existing notification bell, chronological/paginated feed and per-Super-Admin read receipts remain connected. Important events: job submitted; shared tenant/PM/agency-admin comment; quote approved/rejected/revision requested; job cancelled/completed. Private notes and Operations' own shared comments do not create self-notification loops. Invoice uploads/payments create safe activity history, not an Operations self-email.

Read/unread changes create private audit activity and never change job status/version or mail state. Inbox records persist independently of the email queue. Ordinary portal users cannot access the inbox or alter audit/comment/action history.

Email remains **local testing only**. Actual Sevlink mailboxes/SMTP/SES delivery are not active. Keep:

```bash
export SMTP_DELIVERY_ENABLED=0
export OPERATIONS_LIVE_DELIVERY_ENABLED=0
export OPERATIONS_EMAIL_DELIVERY_BACKEND=portal.mail.PrivatePreviewBackend
```

The configurable Operations recipient defaults to `maintenance@sevlink.co.za`. In a second local terminal with the same Django environment, run:

```bash
cd portal/production
python manage.py send_operations_notifications --watch --interval 5
```

Or run a batch with `python manage.py send_operations_notifications --limit 50`. Branded plain-text/HTML MIME previews appear under `portal/production/private-email-preview/`, ignored by Git/Docker and not served publicly. Messages contain safe job/property/agency/event/time/link context, excluding private supplier details, payment notes, tenant contacts and comment bodies. The existing leases, retry/backoff, stable Message-ID and delivery-attempt audit remain. Provider acceptance followed by a worker crash may still duplicate a message; exactly-once SMTP delivery is not claimed. No worker/service has been deployed.

## Run and manually verify later

Follow [the existing local setup and separate review-account instructions](PHASE-1-VERIFICATION.md). Existing local copies need the updated branch/dependencies and `python manage.py migrate`; do not recreate existing review accounts. Use separate browser profiles for tenant A, PM A, Super Admin and agency B. Owner manual acceptance testing remains deferred.

- [ ] Tenant A submits a job/photo. PM A reviews it, tenant signs in again and sees its status; agency B cannot obtain the job or photo.
- [ ] Operations uploads an externally prepared quotation PDF with reference and matching ZAR amount. Confirm it is absent for PM A while Draft, then send it for approval.
- [ ] PM A requests revision with a comment. Check activity, Operations bell and local email preview. Upload a new PDF revision as Operations; the old file remains in history. A stale approval must conflict.
- [ ] On separate revisions/jobs, test Reject and Approve. Confirm each creates one Operations notification. Compare downloaded approved bytes/file hash with the original upload; approved metadata/PDF cannot be changed.
- [ ] Operations uploads an agency invoice PDF with number/amount/due date and explicit agency visibility. PM A can download it; tenant/agency B cannot. Original quotation/invoice files never appear in the tenant's generic attachment list.
- [ ] Operations records a partial payment, then the balance. PM A sees Partially paid then Paid after signing in again; private receipt references/notes stay hidden. Confirm job status does not change. No money is collected.
- [ ] Upload a private supplier invoice and an Operations-only note with supplier quotation PDF/cost details. Check that PM A/tenant/agency B cannot retrieve their metadata, history or copied download URLs.
- [ ] Test duplicate/stale submits, malformed/oversized/non-PDF files and payment overage. No duplicate documents, approvals, payments or emails should result.
- [ ] Bell read/unread persists after sign-out/in and does not affect job or payment state. Original demo/website appearance and browser-local behaviour remain unchanged.

## API contracts

All paths below start `/api/maintenance/`. Existing Django session authentication/CSRF apply. Mutation actions require a UUID `Idempotency-Key`; commercial file uploads are multipart with exactly one `attachments` PDF part. `version` is an integer JSON value, or digit string in revision multipart forms.

- `POST requests/<job>/quotations/`: multipart `reference`, `amount`, optional `title`/`scope`, PDF.
- `POST .../quotations/<quote>/edit/`: JSON `version`, `reference`, `amount`, optional `title`/`scope`; draft metadata only.
- `POST .../quotations/<quote>/send/`: JSON `version`.
- `POST .../quotations/<quote>/revise/`: multipart `version`, `reference`, `amount`, optional `title`/`scope`, **new PDF**.
- `POST .../quotations/<quote>/decision/`: JSON `version`, `status` approved/rejected/revision_requested, required `reason`.
- `GET .../quotations/<quote>/pdf/`: authorized original PDF; 404 if no uploaded document.
- `POST requests/<job>/invoices/`: multipart `number`, `amount`, `due_date` YYYY-MM-DD, `visibility` shared/internal (defaults internal), PDF.
- `POST .../invoices/<invoice>/payments/`: JSON `version`, `amount`, `paid_on` YYYY-MM-DD, optional private `reference`/`note`.
- `GET .../invoices/<invoice>/pdf/`: authorized original invoice PDF.

Job detail/list responses contain role-filtered `quotations` and `invoices`; no line-item/VAT calculation fields are returned. Uploaded document metadata includes date/hash/download URL, never storage keys. Existing comment, conversation-permission and Operations notification APIs are unchanged.

## Validation and remaining work

`scripts/check.sh` runs original demo suites, JS syntax, Django system checks, migration consistency and automated tests. Enable existing Playwright/Chromium coverage with `SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh`. PostgreSQL CI tests concurrent decisions and manual payment entries; SQLite deliberately skips those row-lock tests. PostgreSQL skips the optional browser test, which runs in the SQLite/Chromium job.

Local result with Chromium: **102 passed, two PostgreSQL-only concurrency tests skipped (104 discovered)**. Original demo suites, JS syntax, Django system checks, migration consistency and upgrade-preservation tests passed. See draft PR checks for PostgreSQL results.

Coverage includes required PDF/amount/reference/date validation, exact-byte downloads and approved retention, numbered revision/stale decision/idempotency tests, all decision notifications, private supplier documents and payment receipts, tenant/agency/portfolio isolation, raw-attachment bypass attempts, invoice duplicates/immutability, partial/full payments, overpayment/stale/replay prevention, rollback/file cleanup, migration preservation, comments/inbox/local email queue tests and browser workflows.

Remaining: owner manual acceptance testing; invoice correction/void/refund/credit-note and approved-quote amendment workflows; actual mailboxes/SMTP/SES activation, deployed worker supervision and dead-letter monitoring/replay; provider feedback; file malware scanning/retention/backups; production load/independent security validation. Deposits, bank verification, invoices/payments in the **original static demo**, scheduling, dispatch, budgets and subcontractor planner remain browser-local simulations. Only the authenticated Django upload/payment ledger workflow described here is real. No payment gateway, tax-document generation or paid service was introduced.
