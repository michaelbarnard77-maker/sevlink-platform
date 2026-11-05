# Controlled agency launch readiness

This work is development preparation, not launch approval. Keep main untouched,
actual email disabled and all paid services unprovisioned. Run acceptance against
synthetic records first. Never use the static demo for real client data.

## Entry and accounts

- Account/property setup: `/login/`, then `/`. Persistent workflows: `/maintenance/`.
  Delegated scheduling/finance staff are routed into their authorised workspace.
- Public `public-site/dist/portal-config.js` has a deliberately blank
  `SEVLINK_PORTAL_SIGN_IN_URL`. After a real HTTPS portal origin is verified, set
  this to that origin or its `/login/` URL. A separate Agency sign-in link appears;
  the existing demo links remain explicitly labelled. No live origin is invented.
- Agency administrators use **Manage account access**. Super Admin can open the
  same scoped screen from the agency overview. Changes require confirmation and
  a reason; append-only lifecycle records retain the responsible user and time.
- Deactivation ends active tenancies, removes PM allocations, revokes pending
  invitations, and invalidates prior login sessions. Reactivation never restores
  these relationships or old sessions. Reassign properties explicitly afterward.
- Move-out retains tenancy/job history and immediately removes property access.
  Cancelled invitations cannot be accepted; unlinked pending tenancies are ended.
- An existing active tenant may accept a property invitation only within their
  existing agency, after signing in as that exact account. No password reset or
  cross-agency reassignment occurs. Historical tenancies are retained. Transfer
  between agencies and changing an agency administrator require a separately
  reviewed support process; there is no public reassignment shortcut.
- New agency registration defaults to disabled in production. To admit the agreed
  pilot owner, explicitly configure `AGENCY_REGISTRATION_ENABLED=1` and
  `AGENCY_REGISTRATION_ALLOWED_EMAILS` with verified owner email addresses. The
  production deployment check refuses enabled registration without a list.
  No CK owner email is invented or configured. Invitations for existing agencies
  remain separate. Email ownership is not agency vetting.

## Privileged security

Production defaults require authenticator MFA for every staff/Super Admin account
on every authenticated session. Local development defaults leave it off; test
with `PRIVILEGED_MFA_REQUIRED=1`. `/security/mfa/` requires the current password to
start enrollment, then a valid 6-digit authenticator code to confirm. Add the
base32 key manually or use the private setup URI; never paste it into a public QR
website. Confirmed keys are not displayed again. Reused tokens are rejected and
attempts throttled. Setup and verification produce private security audit events.

Trusted staff offboarding is `deactivate_staff USER_ID --actor OTHER_SUPERADMIN_ID
--reason-reference REVIEWED_TICKET --confirmed-offboarding`. It refuses self or
agency accounts, revokes roles and sessions, and retains a timestamped private
security event referencing the externally held reviewed reason. As with recovery,
host/CLI access is trusted; do not grant portal users shell access. Re-granting
staff access requires a fresh privileged approval, not ordinary agency reactivation.

Time synchronisation is essential. TOTP secrets are stored in the private database;
production database/backups must be encrypted with tightly restricted access.
This implementation does not provide self-service recovery codes. Lost-device
recovery uses the trusted CLI `reset_staff_mfa USER_ID --actor OTHER_SUPERADMIN_ID
--reason REVIEWED_REASON --confirmed-identity`. It requires another active Super
Admin, records the private reason/actor and invalidates all existing sessions.
Host/CLI access is trusted: the actor flag is an audit attribution, not CLI login.
No email-based bypass or public MFA-disable endpoint exists. Complete and rehearse
that procedure before relying on MFA operationally. Do not disable MFA globally
to recover one account. Consider phishing-resistant WebAuthn in a later phase.

Production defaults also enable per-user API read/write/upload budgets, using the
shared database and row locks. Configure `PORTAL_READS_PER_MINUTE` (180),
`PORTAL_WRITES_PER_MINUTE` (60), `PORTAL_UPLOADS_PER_MINUTE` (10) for the pilot;
local development can exercise them with `PORTAL_API_THROTTLING=1`. These are not
anonymous edge DDoS protection or per-agency storage quotas. Add trusted proxy
limits, body/time limits, monitoring and a capacity budget before public access.

## Private uploads

Production defaults require scanning; local development retains the original
isolated test mode. `UPLOAD_SCAN_REQUIRED=1` and `UPLOAD_CLAMAV_SOCKET` select a
private Unix-domain ClamAV socket. `UPLOAD_SCAN_TIMEOUT` bounds each socket
operation (default five seconds). Only an exact clean verdict releases bytes.
Scanner failure, unexpected replies or infection block writes/downloads, including
historical files. Raw pending uploads are not published or saved as approved
attachments; the request fails safely. Existing structural/size checks remain.

Provisioning ClamAV, fresh signature updates, scanner identity/socket permissions,
resource isolation, monitoring and an actual clean/EICAR integration test are
still required. Mock protocol tests do not prove a deployed engine works.
File storage remains private local storage. A future S3 backend must retain
scan-before-release enforcement; swapping the storage alias alone is insufficient.
No scanner or AWS service has been deployed. Decide legal retention, deletion,
immutable approved-document backup, orphan reconciliation and storage quotas.

## Supplier finance privacy — mandatory business rule

Only authorised Sevlink personnel may see what Sevlink pays subcontractors.
Supplier invoice PDFs, payment amounts/dates/references, balances, negotiated
rates, commissions and internal notes must be denied to agencies, PMs, tenants
and private clients in screens, APIs and document downloads. Scheduler access
alone does not grant supplier-finance access. Customer-facing invoice records
must never include supplier costs or payment records. Existing privacy and
cross-agency regression tests remain mandatory for every release.

## Both email queues

Keep `SMTP_DELIVERY_ENABLED=0`, `OPERATIONS_LIVE_DELIVERY_ENABLED=0` and the private
local Operations backend. Real sender/domain/mailbox configuration and explicit
owner approval are still required before any activation.

- Operations: existing `send_operations_notifications --watch --interval 5` and
  `operations_mail_status --fail-if-unhealthy` retain retries, leases, audit,
  duplicate protection and trusted feedback tooling.
- Accounts: `send_mail_queue --preview` writes one private local preview without
  marking delivery or consuming live retry budget. `--preview --watch` previews
  eligible records over time. Do not expose preview directories or log their
  contents: invitation/password-reset links grant account access.
- The account worker now claims committed rows with leases, sends outside the
  claim transaction, retries with delay, audits sanitized attempt outcomes and
  scrubs accepted/expired link bodies. `account_mail_status --fail-if-unhealthy`
  reports overdue/dead records, stale heartbeat and expired leases. Production
  supervision must run **both** workers and alert on both health commands.
- Account links expire. Failed/exhausted invitations should be replaced through
  the invitation flow; password resets should be requested again. Do not replay
  an expired password-reset token. Existing legacy queued messages need expiry
  review before activation. Never enable a backlog blindly.
- SMTP acceptance is not inbox delivery. A provider acceptance/crash window can
  still duplicate mail despite stable Message-ID and claims. Operations has a
  trusted feedback importer; continuously verified provider feedback ingestion
  and account-email bounce processing remain deployment/integration work.

See [production preparation](PRODUCTION-PREPARATION.md) for sender verification,
SPF/DKIM/DMARC, secret files, SES/SMTP, monitoring and safe feedback handling.

## Infrastructure verification and release procedure

No production resource is created by this branch. The CI PostgreSQL job rehearses
an ephemeral dump/restore with matching server tools, checks the migration history,
tests a write/rollback on the restored database and confirms Django deleted its
test database normally. That is a development database rehearsal, not evidence of
encrypted production backups or a coherent real database/file recovery.

Before release, the responsible infrastructure operator must provide evidence of:

1. A reviewed HTTPS/private-network deployment, secret management, supported
   PostgreSQL with certificate verification and least-privilege database access.
2. Private file storage, scan enforcement, encryption and denied anonymous reads.
   `python manage.py verify_private_files` verifies saved file sizes/hashes for
   both job documents and supplier compliance records without printing private
   metadata. `check_upload_scanner` probes a real local engine when provisioned.
3. Coordinated encrypted database/private-file backups, object hashes, retained
   approved PDFs and an isolated restore drill with outbound email disabled.
4. Agreed recovery point/time targets, retention, lawful deletion, access logs and
   a tested forward-recovery plan for migrations. Rehearse legacy banking-data
   guard 0018; do not bypass it or discard old records without approved handling.
5. Supervised workers, restricted logs, alerts, dependency review, resource limits,
   load testing and an independent permission/security review.

Do not automatically reverse financial/schema migrations. Take a verified backup,
run migrations once, check schema drift and permissions, then run the acceptance
checks below. TOTP migrations ship with django-otp; portal migrations 0020–0024
add audit/outbox metadata and session invalidation without removing business data.

## Owner acceptance checklist

Use fresh accounts and separate browser profiles, with synthetic Gauteng and Cape
Town properties and confirmed synthetic team coverage. Do not invent real contacts.

1. Register/verify the agency; invite PMs and tenants; accept using real passwords;
   reset a password locally; cancel/expire an invitation; refuse wrong-account and
   other-agency acceptance. Verify delegated staff login and staff MFA enforcement.
2. Create a job/photo/PDF, review, exchange authorised comments, check Operations
   notification/read state and local email previews. Refresh/relogin to prove data
   persists. Check another PM's portfolio and another agency cannot read or download.
3. Upload quotation PDFs, decide/revise/amend, reject stale/duplicate decisions and
   confirm previous approved PDFs and amounts are retained without private costs.
4. Upload invoice/replacement PDFs, record partial/full payments/refunds, void and
   reconcile appropriately. Check held invoices refuse collection; retain history.
   Have the accountant approve reference, credit-document and retention procedures.
5. Schedule both regions and teams, compare proportional times, try overlaps and
   unavailable days, reschedule/cancel, and inspect override/history. Public status
   changes must contain no supplier/schedule/finance information. Cancel appointments
   separately when closing/cancelling jobs; this remains an explicit manual step.
6. Check Monday cutoff, overdue totals, partial payments and invoice PDFs. No money
   moves and Monday never marks an invoice paid automatically. Verify finance versus
   scheduler permissions and agency/tenant denial of every private endpoint.
7. Move a tenant out, invite their existing account to another same-agency property,
   deactivate/reactivate a PM/tenant, test old browser sessions, and confirm retained
   history with immediate access revocation. Inspect the lifecycle audit.
8. Perform a clean/infected/scanner-down integration test, deny direct private-file
   URLs, run backup restoration and review alert handling. Record actual evidence,
   approver, date, defects and decisions. Automated results are not owner sign-off.

## Pilot approval record — pending, not inferred

Owner has nominated **CK Properties, approximately 80–100 properties**. This is
planning scope, not approval to onboard live data. Actual property/user lists and
regional allocation are still required. Owner must nominate: permitted users/regions; start/end
review dates; named Operations and finance owners; support contact and hours;
emergency/incident handling; backup and recovery owners; daily monitoring checks;
stop/rollback criteria; accounting/privacy sign-off. Default state is **NO LAUNCH**.
A sensible proposal is CK Properties, a named subset first within the 80–100
property portfolio, daily review
and no live customer data until every required gate has evidence and owner approval.
No dates, property records, contact information, consent or launch approval have
been invented. Operations/finance owners remain pending.
