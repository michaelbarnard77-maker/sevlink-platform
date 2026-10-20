> Development branch update: Phase 1 now includes persistent maintenance requests,
> authenticated API endpoints and a portal adapter at `/maintenance/`. See
> [Phase 1 workflow](../../docs/PHASE-1-WORKFLOW.md) for current behavior and tests.
> The baseline notes below describe the original onboarding implementation; the
> remaining repair/financial/operations features are still incomplete. Not deployed.

# Sevlink server application — first implementation stage

This is real server-side account and property setup code for a future xneelo
Cloud deployment. It is separate from `../dist`, the browser-local demo.
**It is not yet deployed, integrated with the repair system, or ready for clients.**

## Implemented and tested

- Agency registration creates an inactive agency admin with a hashed password.
- A 48-hour single-use email verification link activates the admin.
- Admin invites PMs. PMs set their own password and enter their own portfolio.
- Admin adds/assigns properties; PM-created properties belong to that PM.
- Admin/PM links tenants only to properties they can manage.
- Tenant accepts email invitation, sets a password and sees only their property
  and PM contact. No cotenant or private access-note disclosure.
- Agency isolation and role checks run on the server for each request.
- CSRF protection, secure sessions, login/reset/invitation throttling and audit records.
- Password reset and replacement agency verification links.
- Transactional email queue. No real email has been sent during development.
- No sample business records are inserted into a new database.

First-stage limitation: each email account belongs to one agency. Existing accounts
cannot be silently moved by an invitation. Multi-agency membership and multiple
property invitations for an existing tenant require a deliberate later workflow.

## Still required before launch

Repair reporting and PM submission, operational pipeline, quotes/approvals,
deposits and payment verification, appointments, reports, invoices, secure file
uploads and private subbie planner must be ported from the demo to server-side
models and transactions. The demo's role switch must never be used for real access.

Also required: SMTP verification and deliverability testing; PostgreSQL integration
and concurrent-request testing; visual phone/browser QA; server hardening and
monitoring; automated encrypted backups to a separate recovery destination with
retention and restore test; load testing against expected usage; final review of
company disclosures, privacy and retention settings. Snapshot allowances in the
cost calculator do not configure any of these tasks.

## Local development (no live accounts or email)

Use Python 3.12:

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
export DEBUG=1
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
python manage.py migrate
python manage.py test portal
python manage.py runserver
```

Open `/register/`. SQLite is for local development only. Email is queued in the
local database and the delivery command refuses to run until explicitly enabled.
Do not expose this development server on the internet. To inspect a test invite,
use a local test fixture or the Django test suite, never a public outbox endpoint.

## Proposed xneelo deployment (do not run before the remaining launch work)

The proposed host is a 2-vCPU / 4-GB Ubuntu LTS server with PostgreSQL on its
premium boot disk. The proposed 50-GB data volume is reserved for the future
private upload service; it is not currently exposed or used by this first stage.
The sizing is provisional until workload tests are complete. This is a single
server, so maintenance or host failure can interrupt service.

A server administrator needs to install and maintain Docker Engine/Compose,
SSH keys, host firewall, patching, disk monitoring and backups. Only 80/443 should
be public; SSH should be restricted. Do not expose PostgreSQL or Gunicorn.
Do not send root passwords, private SSH keys or SMTP credentials through chat.

After configuration review, copy `.env.example` to `.env` on the controlled host,
replace placeholders and protect it with mode 600. Point only the portal DNS
record to the server; preserve existing email MX/SPF/DKIM/DMARC records.

The included Compose/Caddy files are a deployment starting point, not a record of
anything executed. Verify them in staging with PostgreSQL before production:

```
docker compose build
docker compose up -d db
docker compose run --rm --user root web sh -c 'chown 10001:10001 /app/collected-static'
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python manage.py check --deploy
# Create the owner/staff account interactively on the host; use its email as username.
docker compose run --rm web python manage.py createsuperuser
docker compose up -d
```

Set SMTP values from the actual email host. Test delivery to a controlled mailbox
before enabling `SMTP_DELIVERY_ENABLED=1`. After approval, schedule **one** worker
for `python manage.py send_mail_queue` every minute. The worker retries up to five
times. Monitor failures. A crash after SMTP accepts a message can cause duplicate
delivery on retry; invitation acceptance is still single-use. Purge expired,
undelivered verification messages under a documented retention policy.

Before any launch, back up PostgreSQL and files to a separate recovery location,
verify restore, and test all role boundaries on the deployed HTTPS hostname.

## Verification so far

Automated Django tests use SQLite locally. They cover complete registration,
verification, PM invitation, PM property ownership, tenant invitation, role
escalation denial, cross-agency/PM isolation, tenant privacy, expired/reissued/
reused links, CSRF, POST-only logout, login throttling and queued password resets.
PostgreSQL and Docker deployment have NOT been exercised in this environment.
