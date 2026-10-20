# Step 7: quotations, conversations and Operations inbox

Development branch: `development/phase-1-foundations`. Draft PR #1 remains unmerged. No deployment, paid service or live email activation is included. The original public website, demo, branding, styles and assets are preserved.

## What is connected to Django

Use the existing `/login/` and `/maintenance/` workspace with separate tenant, property manager and Super Admin accounts. The static demo in `portal/dist/` still uses browser-local data; it never writes these models or triggers these notifications.

| Screen/control in authenticated workspace | Backend behaviour |
| --- | --- |
| Report repair, photos/documents, repair register and detail | Persisted requests and private attachments, scoped by agency/property/tenant |
| Status selector and timeline | Versioned saved status transitions and timestamped actor activity |
| Operations quotation form | Saves editable drafts with 1–20 lines, quantities, units and ZAR prices |
| Save draft changes / Send for approval | Locks job, checks quotation version, freezes public content on sending |
| PM/agency Approve / Reject / Request revision | Mandatory decision comment, responsible user/time and idempotent decision |
| Operations Create next revision | Supersedes sent/rejected/revision-requested revision; creates next numbered draft |
| Download quotation PDF | Authenticated download rendered only from public quotation data |
| Job conversation and files | Persistent chronological shared comments with protected files |
| Operations-only note option | Private notes and files; server excludes them from all external responses/downloads |
| Enable/disable tenant conversation access | Per-job persisted permission with version check and private audit activity |
| Operations notification bell/feed | Persistent, paginated important-event inbox; per-operator read/unread state |
| Open job from notification | Normal session authorization; no bearer/login token |

The existing account/property/invitation backend remains in place. Payments, deposits, invoices, budgets, scheduling, dispatch and subcontractor assignments shown in the standalone demo are **still simulated**, with no real finance/dispatch integration. Quote approval does not automatically move a job's status, spend money or schedule work.

## Quotations and VAT

States: **Draft → Sent for Approval → Approved / Rejected / Revision Requested**. Operations can supersede an unapproved sent/decided revision by creating the next draft; the preceding revision becomes **Superseded**. Approved revisions cannot be edited, resubmitted, superseded or decided again. A later amendment/cancellation of an approved commercial agreement needs a separate future workflow.

Every revision has its own UUID, series UUID, integer revision number, optimistic version, decision user/time/comment and chronological action history. The parent job and quotation are locked before mutation. Unique revision/action/idempotency keys prevent repeated logical actions; stale versions return 409. Authorization is checked again after taking the parent lock. Approved public content/amounts are frozen JSON snapshots; sent content and lines have model-level immutability guards. History/comments are append-only through the application. A database administrator still has direct database powers; this is not cryptographic/WORM archival storage.

VAT is **not hardcoded**. Set `SEVLINK_VAT_RATE` to the accounting-approved fractional rate in the local server environment. For arithmetic testing only, `SEVLINK_VAT_RATE=0.125` represents 12.5%; it is not a recommendation about Sevlink's legal tax obligations. An empty setting disables taxable quotations and allows “No VAT”. Restart the server after changing environment settings.

Prices accept exact decimal strings (two decimal places), quantities up to three decimal places. Per-line calculations use Python Decimal and ROUND_HALF_UP to cents. Exclusive prices: net = rounded quantity × price, VAT = rounded net × configured rate. Inclusive prices: gross = rounded quantity × price, net = rounded gross ÷ (1 + rate), VAT = gross − net. Totals sum rounded lines. Snapshot the rate on draft calculation; sending/revision-copying and later decisions never silently recalculate it. Explicitly editing a taxable draft uses the currently configured rate. Zero/negative total, excessive precision, nonfinite values, overflow and >20 lines are rejected.

Private costs, commission totals and notes live in a separate `QuotationPrivate` model. Only Operations can write/read them. They are excluded from agency/PM/tenant payloads, public snapshots, quotation PDFs and notification messages. Internal supplier quotations/identities are not exposed or integrated. Staff must put confidential content in private fields, not deliberately paste it into shared scope/comments/files.

PDFs use existing Pillow, require no new service or dependency, and are simple multipage raster documents. They are not tax invoices or an accessible/searchable typeset PDF system. Tenants cannot download quotations, drafts are Operations-only, and another agency gets 404.

## Conversation rules and files

Existing ownership rules remain: tenant access requires their own submitted job, active tenancy and matching agency; PM access requires the assigned portfolio; agency administrators see their agency; Super Admin sees all agencies. A cotenant is not automatically a participant. Plain `is_staff` grants no Operations access.

`tenant_comments_allowed` defaults to true to preserve the existing reporting-tenant conversation behaviour. Operations can disable it for an individual job: comments, comment activity and comment-linked files then disappear for that tenant, and posting/downloading is forbidden server-side. Job status and original report attachments remain accessible under the existing rules.

Only Operations can create internal notes. Notes and their attachments inherit server-enforced internal visibility. PMs/agencies/tenants cannot request internal visibility, enumerate these files or download guessed file URLs. Shared comments are readable by authorized participants. Visibility cannot be changed after posting. Text-only follow-up comments can be added to closed requests; new files and quotation actions cannot.

Comment uploads reuse the existing JPEG/PNG/WebP/PDF validator, size/type checks, sanitized UUID paths, private storage alias, authenticated downloads and rollback cleanup. Limits: five files per batch, 5 MiB each, ten shared files and ten internal files per job. Separate limits prevent hidden internal file counts reducing an external user's quota. Images are decoded/re-encoded to remove metadata; PDFs use conservative content checks. Antivirus/CDR, retention and automated orphan reconciliation are not implemented; do not treat validation as malware scanning.

## Operations inbox and local email

Important events: saved job submission; shared tenant/PM/agency-admin comment; quotation approval, rejection or revision request; job cancellation or completion. Operations' own comments/internal notes do not cause self-notification loops. Quotation creation/edit/send/revision and all decisions remain in activity/action history.

Each important event writes **one inbox item and one email outbox row in the same transaction**. Rollback removes all three. The separate worker sees only committed records; the request never sends email. Inbox records remain independent of delivery failures, retries or email configuration. Each Super Admin has separate persistent read receipts; marking read/unread adds private audit activity and never changes job status or version. No inbox API is available to external users, including agency administrators.

Default recipient: configurable `OPERATIONS_NOTIFICATION_EMAIL=maintenance@sevlink.co.za`. Branded plain-text + HTML messages contain job number, agency, property, event summary, timestamp and authenticated job link. No tenant contacts, comment body, private notes, subcontractor identity, supplier costs or commissions are included. No agency-facing notification emails are introduced.

**Actual Sevlink mailboxes and SMTP/SES delivery are not operational here.** Keep:

```bash
export SMTP_DELIVERY_ENABLED=0
export OPERATIONS_LIVE_DELIVERY_ENABLED=0
export OPERATIONS_EMAIL_DELIVERY_BACKEND=portal.mail.PrivatePreviewBackend
```

With the same environment as the local server, run in a second terminal:

```bash
cd portal/production
python manage.py send_operations_notifications --watch --interval 5
```

Or process one batch with `python manage.py send_operations_notifications --limit 50`. Private MIME previews appear in `portal/production/private-email-preview/` (Git/Docker ignored, directories 0700/files 0600, not web-served). Open them locally in a mail client/editor to inspect both formats. The manual sequence below produces previews of **all seven event types** using real saved test-account actions; automated tests also inspect every type. No synthetic frontend action queues mail.

Existing leases, stable Message-ID, five delivery attempts, exponential backoff and sanitized attempt audit remain. The inbox does not depend on the worker running. No worker was deployed/scheduled. SMTP acceptance followed by a worker crash can still cause a duplicate; exactly-once delivery is not claimed. Future SES SMTP configuration can use the existing settings, after sender/DNS verification and delivery/bounce/complaint monitoring are implemented. No AWS resource or credential is created.

## Run and test locally

Follow [the existing review-account setup](PHASE-1-VERIFICATION.md) to install dependencies, migrate, create synthetic accounts and start Django. Existing local review accounts need only `python manage.py migrate`, not recreation. Use distinct browser profiles for tenant A, PM A, Super Admin and agency B. Keep live mail disabled. No manual end-to-end testing was performed on the owner's accounts; that remains deferred.

- [ ] Tenant A submits a repair with a photo. Restart/sign in again and confirm persistence. Operations sees the submitted-job inbox item.
- [ ] Tenant A and PM A each add a comment/file. Both persist and produce local Operations previews. Agency B cannot read the job or copied file URL.
- [ ] Operations creates a quotation draft with multiple lines. Confirm it is absent for PM A. Edit it, then send for approval. Compare line totals, configured VAT and ZAR total.
- [ ] PM A requests revision with a comment. Check the inbox and local revision-request email. Operations creates revision 2; old revision is Superseded. A stale revision-1 approval returns a conflict.
- [ ] Send revision 2, reject it as PM A, and confirm the rejection event/preview. Create/send revision 3 and approve it. Confirm it cannot be edited/decided again. Download its PDF as PM A; agency B and tenants cannot download it.
- [ ] Put a unique synthetic subcontractor/cost marker in private quotation fields and an internal note/file. Confirm these appear only for Operations and cannot be retrieved through external API/download URLs.
- [ ] Disable tenant conversation access: tenant can still follow job status but cannot see/post conversation messages or obtain comment files. Re-enable to restore access.
- [ ] Operations opens the bell, marks an item read, signs out/in and sees persisted state. Mark unread. Job status/version and email state must remain unchanged. Another Operations user has their own receipts.
- [ ] Cancel one request; complete another via Reviewed → In progress → Completed. Confirm corresponding inbox items/previews. Keep the worker running to process saved events; no messages reach real mailboxes.
- [ ] Original static demo appearance/workflows remain unchanged and never create Django records.

Automated checks from repo root, with venv activated:

```bash
bash scripts/check.sh
# Enable existing optional Playwright/Chromium integration when installed:
SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh
```

Local validation: **90 passed, one PostgreSQL-only concurrency test skipped (91 discovered)** with Chromium enabled. Both original demo Node suites, all JavaScript syntax checks, Django system checks, migration consistency and upgrade-preservation tests passed. Original public/demo assets have no diff.

SQLite cannot verify PostgreSQL row-lock concurrency: the concurrent approval/rejection test deliberately skips there. GitHub Actions runs the complete suite against PostgreSQL 17 and the browser workflow against SQLite/Chromium. See PR checks for actual results.

## API extensions and upgrade

All use existing session authentication/CSRF. Create/edit/send/revise/decision/comment actions require UUID `Idempotency-Key`; stale writes return 409. Decimal values are strings in API responses.

- `POST requests/<job>/quotations/`: `title`, `scope`, `lines` (description, quantity, unit, unit_price), `tax_treatment`, optional Operations `internal`. Legacy `amount` becomes a one-line **draft**, never auto-sent.
- `POST .../quotations/<quote>/edit/`: complete draft content plus integer `version`.
- `POST .../quotations/<quote>/send/` or `revise/`: integer `version`.
- `POST .../quotations/<quote>/decision/`: integer `version`, `status` approved/rejected/revision_requested, required `reason`.
- `GET .../quotations/<quote>/pdf/`: authorized private PDF.
- `POST requests/<job>/comments/`: JSON or multipart `text`, `visibility` shared/internal, multipart `attachments`.
- `POST requests/<job>/conversation-permissions/`: Operations-only integer job `version`, boolean `tenant_comments_allowed`.
- `GET notifications/?before=<item-id>`: Operations-only newest-first feed, up to 50 items, unread count and next cursor.
- `POST notifications/<item>/`: boolean `read`; only receipt/audit state changes.

Paths above are under `/api/maintenance/`. External serializers explicitly filter drafts, internal notes/files/activity, private money and tenant financial data.

Migrations 0007–0009 extend existing tables and backfill old quotations as single-line no-VAT snapshots, preserving amounts, decisions and timestamps. Each legacy quotation receives a distinct series UUID; pending becomes Sent for Approval. Existing outbox events become inbox items without queuing old email again. Upgrade tests cover multiple pending/approved/rejected records and the existing onboarding/status history. Back up before any eventual non-development migration; reverse migration with newly introduced states/data is not supported as a production rollback strategy.

Remaining work beyond this step: owner manual acceptance testing; actual SMTP/SES/mailbox setup, worker supervision and dead-letter monitoring/replay; provider feedback; quote expiry/approved amendments and finance/budget/dispatch integration; file malware scanning/retention; production backup/restore, load validation and independent security review. No original demo finance or scheduling feature should be assumed real merely because quotations now persist.
