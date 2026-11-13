# Step 7.5 production and email preparation — not deployed

This is a future deployment runbook, not authorization to provision resources or activate delivery. No AWS resource, live mailbox connection, production migration, DNS change or paid service was created/tested during Step 7.5. Keep the development branch/draft PR unmerged until owner acceptance.

## Release gates

1. Complete [the manual acceptance checklist](STEP-7-5-ACCEPTANCE.md) using separate tenant, PM, Super Admin and agency B accounts. Obtain accountant review for void/correction/credit-note treatment and numbering. Application voiding does not replace statutory accounting documents.
2. Rehearse migrations 0011–0013 against a restored database/private-file backup in isolated staging. They retain existing gross payments/approved snapshots and initialize refunds to zero. New net-balance constraints permit gross receipts above invoice face value after genuine refunds/re-payments; reversing to old constraints after those entries is unsafe. Use reviewed forward fixes or coordinated restore.
3. Choose hosting, cost limits, data region, retention and recovery objectives with the owner. AWS provisioning/deployment requires separate approval. Prefer a suitable South African region where supported and review POPIA/data residency obligations; regional selection alone is not compliance.
4. Resolve the safeguards below. Passing tests is not a claim that production security or operational readiness is complete.

## Future AWS architecture and deployment sequence

- Build the existing `portal/production/Dockerfile`; retain the original frontend assets and existing Django app. No separate backend is required. Do not use Django's development server publicly.
- Use a private managed PostgreSQL endpoint (for example RDS) with security groups allowing only the app/worker, encrypted storage and authenticated TLS. Set `DB_SSLMODE=verify-full` and `DB_SSLROOTCERT` to a trusted current provider CA bundle. The existing bundled Compose DB is a local/self-contained reference with no TLS; its `disable` mode must not be copied to RDS.
- Run app and Operations worker as separate supervised processes/tasks using the same reviewed image and database. Give each only necessary permissions. The app's private upload store must be durable across restarts; never use disposable container disk for financial documents.
- Existing storage uses the named Django `maintenance_private` alias and protected streaming downloads. Current implementation is private filesystem storage. Future S3 requires a tested backend adapter/dependency configuration, IAM task role, Block Public Access, encryption, no public ACL/CDN routes, appropriate object versioning/retention and mapped storage errors. No S3 adapter/bucket was activated here. Rehearse upload rollback cleanup before enabling retention/object lock; do not prevent cleanup of uncommitted uploads inadvertently.
- Inject `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` via the approved secret manager/task secret bindings or mounted `*_FILE` secrets. Do not commit `.env`, credentials, databases, previews or private files. Configure one direct variable or its file per secret, not both. Restrict/rotate secrets and avoid logging values/paths. No AWS SDK access is needed just to read injected secrets.
- Provide HTTPS at a trusted reverse proxy/load balancer, exact `ALLOWED_HOSTS`, HTTPS `SITE_URL`, secure cookies and appropriate proxy trust. Restrict direct Gunicorn access. The proxy must overwrite forwarded-protocol headers. Review HSTS and run `manage.py check --deploy` under the eventual staging/production configuration.
- Take a coordinated encrypted DB/file backup, apply migrations once with a controlled release job, run `collectstatic`, then smoke-test auth/tenant isolation/private PDF downloads and financial actions in staging. Never run migrations independently in every worker replica. Use immutable image versions and a reviewed forward-recovery/restore plan.
- Configure structured/sanitized application and worker logs. Log IDs/status/error codes, not PDF contents, financial free text, tenant contacts, tokens or credentials. Centralize access with limited retention. No monitoring service was provisioned by this work.

## Backups and disaster recovery

Define and prove recovery point/time objectives before launch. Enable encrypted PostgreSQL backups/point-in-time recovery and protected private-file backups/object versions, with access separation and deletion protection. Restore a coherent database/file pair and check document hashes, approved version links, original receipts/refunds, annual counters and pending email outbox. Test recovery into an isolated environment with all outbound delivery disabled, so restoring pending mail cannot accidentally send an old backlog. Document who can restore and audit recovery attempts. Backup schedules, restore drills and cloud durability remain unverified infrastructure work.

## Disabled email configuration and worker references

The default recipient is configurable `OPERATIONS_NOTIFICATION_EMAIL=maintenance@sevlink.co.za`. Actual Sevlink mailboxes, SMTP/SES configuration and genuine delivery tests are still outstanding. Keep:

```text
SMTP_DELIVERY_ENABLED=0
OPERATIONS_LIVE_DELIVERY_ENABLED=0
OPERATIONS_EMAIL_DELIVERY_BACKEND=portal.mail.PrivatePreviewBackend
```

`portal/production/compose.operations.yaml` is an opt-in **local-preview-only** worker overlay; `portal/production/ops/sevlink-operations.service` is a disabled reference service. Neither was installed or started. Both explicitly override live delivery to disabled; changing `.env` alone will not activate those examples. Production task/service configuration must be separately reviewed and owner-approved.

The worker command is `python manage.py send_operations_notifications --watch --interval 5`. Run it only in a properly configured review environment now. It handles committed outbox events, records leases/attempts/retries and updates a heartbeat. Provider calls occur outside job transactions; SMTP failure never undoes a saved job or financial action. Stable event Message-ID and idempotency reduce duplicates, but SMTP acceptance followed by a crash can still duplicate a delivery. `sent` means backend acceptance, not proven inbox delivery.

Private local MIME previews use `OPERATIONS_PREVIEW_DIR` or the existing private-preview directory (0700 directories/0600 files). They are not public. Account invitation/reset mail retains its separate `MailQueue` and disabled `send_mail_queue` workflow; its production worker/delivery must also be validated before onboarding real users.

## Future SMTP / SES setup and genuine test

After the owner supplies configuration **and explicitly approves activation**:

1. Verify the sender/domain and intended Operations mailbox ownership. For SES, choose an approved region, verify the sending identity, satisfy sandbox/production-access requirements and confirm recipient rules. SES SMTP credentials differ from generic AWS access keys. Store the credentials in secret management.
2. Configure the provider's SMTP hostname/port and exactly one TLS mode: STARTTLS (commonly 587) or implicit TLS (commonly 465). Set `EMAIL_HOST`, `EMAIL_PORT`, secret-backed `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, and an approved `DEFAULT_FROM_EMAIL`. Do not disable certificate verification. Runtime live-SMTP checks require host/secrets and one TLS mode.
3. Publish the provider-issued DKIM CNAMEs exactly. Configure SPF for the correct MAIL FROM domain without creating multiple competing SPF records; SES custom MAIL FROM may require its own MX/TXT records. Check alignment with the visible From domain.
4. Add a reviewed DMARC policy and a working authorized aggregate-report mailbox. Start with a monitoring policy only after deciding who will inspect reports, verify SPF/DKIM alignment, then progress to quarantine/reject when legitimate senders are aligned. Do not paste placeholder records blindly or activate reporting to a mailbox that does not exist.
5. Wire authenticated provider feedback. SES correlation tags are opt-in with `OPERATIONS_SES_TAGGING_ENABLED=1`. A future SNS/SQS/provider adapter must verify signatures, account/topic/region, event IDs and recipient correlation before normalization. No public webhook, SNS subscription or continuously running feedback consumer is implemented here.
6. Approve a controlled staging delivery test to an owner-authorized mailbox, enable only the reviewed worker's explicit gate, inspect received headers/inbox and verified delivery/bounce feedback, and record evidence. SMTP acceptance alone is insufficient. No successful real test is claimed by the existing local tests.

## Monitoring, retry and trusted feedback operations

`python manage.py operations_mail_status --fail-if-unhealthy` returns sanitized counts and fails for stale heartbeat, overdue pending messages, dead letters, expired leases or unresolved negative feedback. Connect that exit status/metrics to the future monitoring/alerting system. No alert transport was configured. Inspect state without logging message bodies; only authorized Operations/system administrators should run management commands.

A dead item can be replayed with `replay_operations_notification <id> --actor <superadmin-id> --reason <reviewed-reason>`. This audits the user/reason, retains prior attempt numbers and stable Message-ID, and adds five eligible attempts. It refuses successful/confirmed-delivered or suppressed messages. It never enables delivery itself.

The trusted importer accepts one normalized JSON object (not raw arbitrary SNS payload):

```json
{"event_id":"saved-job-activity-uuid","provider_event_id":"unique-verified-provider-event","kind":"bounce","occurred_at":"2026-10-21T10:00:00+00:00"}
```

Use `import_operations_feedback <local-file> --verified` only after external signature/account/topic/recipient verification. Kinds are delivered, bounce or complaint. The importer deduplicates events and records no message bodies/provider secrets. Any unresolved bounce/complaint suppresses future messages to that recipient. After investigating actual deliverability, `resolve_operations_feedback <id> --actor <superadmin-id> --reason <reviewed-reason> --confirmed-investigation` creates an append-only resolution; other unresolved feedback still suppresses. It does not send a message or prove a mailbox works. This operator interface is ready for a future verified adapter, not an active provider integration.

## Remaining safeguards and limits

- Privileged-user MFA now uses django-otp with production enforcement, audited enrollment and trusted administrator recovery; explicit scheduler/finance roles exist. Rehearse staff enrollment/recovery and review remaining Super Admin-only administration before launch. Refund/void confirmations prevent accidental clicks, not stolen-account abuse or independent dual authorization.
- Rate limits: authentication and per-user API/read/write/upload budgets exist. Per-agency quotas, trusted edge abuse protection and production capacity testing remain required.
- Upload scanning now has a fail-closed private ClamAV socket adapter for saves and historical reads. A real engine, signature updates, integration probes, monitoring and operational quarantine handling still require infrastructure verification. Structural PDF checks alone are not antivirus. Retention, immutable approved-document storage, orphan reconciliation and full storage quotas remain future work.
- Financial adjustments: no automatic bank refunds, credit allocation/transfers between invoices, or reversal of incorrectly recorded refunds. Invoices requiring allocation remain held. Do not fabricate a refund to clear a hold; use accountant-reviewed real records and design a separately audited allocation/reversal workflow if needed.
- Legal/tax retention, accounting correctness, backup/restore, multi-worker/load/security validation and independent review remain launch gates. Test suites cannot certify them.
- Original browser demo finance/deposit/dispatch/scheduling/subcontractor planner remain simulated. Real authenticated Django features are described in the Step 7.5 acceptance guide.

Current implementation and owner gates: [controlled launch readiness](CONTROLLED-LAUNCH-READINESS.md).
