# Saved job events and Operations notifications

Implemented on `development/phase-1-foundations`. The default Operations recipient is **maintenance@sevlink.co.za**. Every supported important backend mutation creates a durable notification entry immediately in the same database transaction as its job activity. No mail delivery runs in the browser or job HTTP transaction.

**Current delivery is local testing only.** No message has been sent to a real mailbox by this implementation, and no AWS/SES resource or paid service has been activated. Running the worker described below is required to process queued mail automatically.

## What is operational in the development backend

| Real saved backend event | Activity record | Operations notification |
| --- | --- | --- |
| Tenant submits a maintenance request, with or without files | Job submitted, actor and timestamp | Yes |
| Tenant or assigned PM adds a shared comment | Comment text, actor and timestamp | Yes |
| Agency administrator adds a shared comment | Comment text, actor and timestamp | Yes |
| Sevlink Super Admin adds a shared comment | Comment text, actor and timestamp | No self-notification loop |
| Sevlink Super Admin issues a quotation | Public scope/amount and issuing Operations actor | No; agency-facing email is not implemented |
| Assigned PM or agency administrator approves/rejects a quotation | Decision, reason, actor and timestamp | Yes |
| Job marked reviewed or in progress | New status, actor and timestamp | No |
| Job cancelled or completed | New status, actor and timestamp | Yes |
| Browser-local demo actions | None | Never |

These comment and quotation notifications are backed by real models and saved authenticated API workflows. They are no longer simulated actions in the Django workspace. The standalone static demo remains unchanged and separate.

## Shared comments and basic quotations

A shared comment belongs to a maintenance request and is visible to everyone permitted to read that request: the reporting tenant with active tenancy, assigned PM, agency administrator and Super Admin. A cotenant or unrelated property/agency user cannot read or add it. Comments are immutable in this slice and may be added after completion for follow-up discussion. They are not a channel for private Operations/subcontractor notes.

Super Admin can issue a basic quotation with a title, public scope and total amount in ZAR. Only the authorized PM or agency administrator can decide it; tenants and Operations cannot approve it on the agency's behalf. Rejection requires a reason. A quotation can move from pending to approved or rejected once, with version checks; decisions cannot be silently overwritten. Closed requests reject new quotations/decisions.

Tenants do not receive quotation payloads or quotation activity entries. Agency-facing serializers do not expose internal user IDs, staff names, uploader identities, subcontractor records, private job notes or private property access instructions. Operations authors are labelled “Sevlink Operations”; responsible user IDs remain in the protected database. Actor names/roles are snapshotted at the time of the event/comment so later account changes cannot expose previously hidden staff identities.

The authenticated portal uses existing quote-card, comment, timeline and form styles. No original demo HTML/CSS/JavaScript, public-site design or assets were changed. Job details show shared comments and quotes appropriate to the account and an actor/timestamp activity timeline. An email's `/maintenance/?job=<uuid>` link opens that job after normal sign-in, and all permission checks still apply. It contains no bearer or login token.

This is a basic quotation foundation, not the complete demo finance system: there are no line-item/tax calculations, quote document links, revisions/expiry workflows, budgets/deposits, contractor dispatch, payments or invoices. Quote approval does not automatically authorize spending, schedule work or advance the job status.

## Central event and outbox architecture

`portal/events.py` is the single event interface. Supported business transactions call `record()` after their validated mutation. It verifies an explicit event/detail schema, stores `JobActivity`, and creates one `OperationsNotification` for each qualifying event. Event and outbox writes share the same transaction as the business state; rollbacks leave neither an event nor an email to send.

`JobActivity` contains the actor FK, actor snapshot, event type, timestamp, minimal event details and job/property/agency snapshots. Existing status history is preserved for compatibility. Migration 0005 backfills the new activity history from existing saved status events using their timestamps. It intentionally creates **no historical email backlog**, avoiding a burst of old notifications on upgrade. Historical names/property text are reconstructed from current related records where the old event did not store a snapshot.

`OperationsNotification` is a durable one-to-one outbox row for the event. The Operations recipient is snapshotted on creation; configuration changes apply to future notifications. `OperationsDeliveryAttempt` separately records attempt number, timestamps, sent/failed/uncertain outcome and a generic error code. Provider exceptions, credentials and email content are never put in attempt errors or console logs.

Direct ORM edits and arbitrary management scripts are not supported mutation workflows and do not magically emit mail: callers must use the domain event interface inside their transaction. There are no frontend-only mail triggers and no post-save signal duplication.

## Deduplication, delivery and retries

- Each logical job event has a unique key; each event has at most one notification.
- Status changes use the job's conditional version update. Repeated/stale writes cannot emit another event.
- Comment posts, quotation creation and decisions require a UUID `Idempotency-Key` header. Replaying the same key/body returns the existing result. Conflicting reuse returns 409.
- The portal also supplies a stable key while a report form is open. Report creation stores the key and a validated field/file fingerprint so an uncertain response/retry does not create a second job, files or notification. Legacy report API calls without the optional header still represent new submissions and cannot be deduplicated across transport retries.
- The worker claims due rows under database locks and records a lease before sending. PostgreSQL supports `skip_locked` workers; local SQLite should use one worker. No provider call holds a job transaction or outbox row lock open.
- Failed sends retry with 1, 2, 4 and 8 minute delays, then become `dead` after five attempts. Attempts are audited. Expired five-minute worker leases are reclaimable and previous attempts are marked uncertain.
- Once accepted and marked sent, a row is not resent. Every retry uses the same event-derived `Message-ID`.

**SMTP cannot promise exactly-once delivery.** If a provider accepts a message but the worker crashes before saving that acceptance, a retry may deliver a duplicate. Leases, unique event/outbox keys and stable Message-ID reduce duplicate risk; they do not guarantee recipient/provider deduplication. `sent` means the backend/provider accepted the message, not that it reached the inbox. SES bounce/complaint/delivery callbacks and provider-specific idempotency are not implemented.

Database availability is required to save the job and its durable outbox entry. A database write failure can roll back the job, as it should to avoid losing its required notification. Email backend/network failures occur later and never roll back a saved job.

## Privacy and message content

Mail is sent only to the configured Operations address. New domain notifications do not automatically email tenants, PMs or agencies, and use no CC/BCC. Invitations/password resets remain separate in the existing account `MailQueue`/`send_mail_queue` workflow.

Operations summaries include job number, property/name/address, agency, event type, relevant summary, actor role, timestamp with timezone and a sign-in link. They exclude comment bodies, tenant email/phone, private access instructions, attachment names/contents, internal job notes, subcontractor identities and private supplier costs. Quote decisions include the public quoted total and decision, not private costing or free-text rejection reasons. Free-form property/title values are normalized to a single line in the message.

All content posted into shared comments, public quote scope and shared attachments is intentionally readable by authorized job participants. The system cannot redact private information someone deliberately pastes into a shared field. Staff-only comments and automatic content redaction remain future work.

## Local automatic delivery testing

After activating the existing virtual environment and local Django settings:

```bash
cd portal/production
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

In a **second terminal**, activate the same environment, export the same local settings (`DEBUG=1`, a local `DJANGO_SECRET_KEY`, `SMTP_DELIVERY_ENABLED=0`, no `DB_HOST`), and run:

```bash
python manage.py send_operations_notifications --watch --interval 5
```

Or process one batch with `python manage.py send_operations_notifications --limit 50`.

The default `portal.mail.PrivatePreviewBackend` writes MIME messages under `portal/production/private-email-preview/`. New directories use mode 0700 and files 0600 on Unix. This directory is Git/Docker-ignored, excluded from known public/static/media paths by system checks, and has no web outbox endpoint. Open a preview file locally in an editor/mail client; the To header should show maintenance@sevlink.co.za. Messages are not delivered externally. The worker must run continuously (or be scheduled later) for automatic delivery/retries; no cron/service was deployed.

Inspect delivery state without exposing message contents:

```bash
python manage.py shell -c "from portal.models import OperationsNotification; print(list(OperationsNotification.objects.values('id','event__kind','state','attempts','next_attempt_at','error_code')))"
```

Pending rows become eligible at `next_attempt_at`; dead rows need operator investigation. A safe audited dead-letter replay/monitoring interface is not yet implemented. Do not reset attempt numbers manually: delivery attempt numbers are unique audit records.

Local test sequence (human end-to-end review remains deferred): tenant submits; tenant/PM comments; Super Admin issues two basic quotations; PM approves one and rejects the other; PM completes/cancels separate jobs. Verify one preview/notification per qualifying saved event, no previews for rejected/unauthorized/duplicate mutations, and authorized job links. Automated tests perform these workflows now.

## Configuration and future SES

| Setting | Default |
| --- | --- |
| `OPERATIONS_NOTIFICATION_EMAIL` | `maintenance@sevlink.co.za` |
| `OPERATIONS_EMAIL_DELIVERY_BACKEND` | `portal.mail.PrivatePreviewBackend` |
| `OPERATIONS_LIVE_DELIVERY_ENABLED` | `0` / false |
| `SITE_URL` | Local origin in development; must be trusted HTTPS in production |
| `DEFAULT_FROM_EMAIL` | Existing Django sender setting |

The recipient must be one valid address. SITE_URL must not contain credentials, query or fragment; links use this trusted setting, never the HTTP Host header. Local tests can use Django's locmem backend. A non-local backend is refused unless live delivery is explicitly enabled; the account QueueBackend is also refused to prevent queue recursion.

SES can later use Django's SMTP backend with a verified From identity and the appropriate regional SES SMTP endpoint/TLS credentials through existing `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and TLS settings. No AWS SDK, IAM user, SES account, SMTP credential or DNS record has been created here. Sender verification, sandbox exit/recipient rules, DKIM/SPF/DMARC, least-privilege credentials, encrypted transport, bounce/complaint handling, monitoring and a staging delivery test must precede activation. No live flags or credentials are enabled by this change.

## APIs and migrations

- Existing report POST: optional UUID `Idempotency-Key`, JSON or multipart supported.
- `POST /api/maintenance/requests/<job>/comments/`: JSON `text` plus required UUID `Idempotency-Key`.
- `POST /api/maintenance/requests/<job>/quotations/`: Super Admin JSON `title`, `scope`, `amount` plus required UUID key.
- `POST /api/maintenance/requests/<job>/quotations/<quote>/decision/`: authorized PM/admin JSON `status` (`approved`/`rejected`), integer `version`, optional `reason` (required for rejection), plus UUID key.
- Existing detail/list API adds public `comments`, role-filtered `quotations` and `activity`; internal delivery state is never serialized.

All mutations use existing Django sessions, CSRF and agency/property scoping. New migrations 0004–0006 add comments/quotes/events/delivery records, backfill legacy activity without mail, and add report deduplication metadata. They do not modify migrations 0001–0003. Rolling back new tables would lose their records, so production migration/backup planning remains necessary.

## Validation and remaining work

Local result: **72 Django/API/outbox/migration/browser tests passed**, plus both original Node demo suites, JavaScript syntax, system checks and migration consistency. Tests cover every required notification event, saved-only/rollback behavior, configurable recipient, privacy, secure links, actor snapshots, permission/agency isolation, idempotent replays, failed delivery/backoff/exhaustion, worker leases/recovery, local previews, live-delivery gates and upgrade preservation. Chromium covers real shared comments, Operations quote issue, PM approval and deep links alongside existing uploads/status tests.

GitHub Actions also runs PostgreSQL 17 and SQLite/Chromium checks; see the current development branch/draft PR checks for remote results.

Still unfinished: actual SES/SMTP activation and deliverability; worker deployment/supervision and dead-letter alert/replay UI; provider delivery/bounce feedback; retention and scalability/pagination/quotas; staff-only communications; full quote revisions, documents/tax/budget/finance/dispatch workflows; production concurrent-load/security/backup validation. Earlier private-upload malware/retention requirements still apply.

Main, production deployment, paid services and manual verification remain untouched/deferred as instructed.
