# Phase 1: persistent maintenance requests

Branch: `development/phase-1-foundations`. This is a development implementation, not a production deployment or launch approval.

## What works

1. A tenant signs in using the existing Django login and opens **Maintenance requests** (`/maintenance/`).
2. **Report a repair** uses the existing category/form presentation and lets the tenant select one of their active linked properties. Title, description and category are validated on the server. Agency, reporter and initial status cannot be supplied by the client.
3. Submission creates a `MaintenanceRequest`, initial `MaintenanceStatusEvent` and existing `Audit` record in one database transaction.
4. The assigned PM or agency administrator opens the repair list/detail and changes its status. Allowed transitions are enforced on the server, with a version check to reject stale writes.
5. Status and timeline persist in Django's database. A new authenticated tenant session reads the current value, independent of browser storage.
6. A Django **superuser** is the Sevlink Super Admin and can view/update requests across agencies. A plain `is_staff` flag does not grant global access.

## Permission rules

| User | List/detail | Submit | Update status |
| --- | --- | --- | --- |
| Tenant | Own reports on actively linked properties in their agency | Active linked properties only | No |
| PM | Properties currently assigned to that PM in their agency | No | Own portfolio only |
| Agency administrator | Properties in their agency | No | Agency only |
| Sevlink Super Admin (`is_superuser`) | All agencies, including reports awaiting review | No | All agencies |
| Plain staff without membership, nonmember or unknown role | Denied | Denied | Denied |
| Anonymous/inactive | Denied | Denied | Denied |

Membership is still one agency per user. Tenant reporting is intentionally the only creation path in this slice. Removal/deactivation of a tenancy revokes access, including access to its old reports. A cotenant cannot read another tenant's report. PM reassignment changes which PM can read/review that property's requests.

Unauthorized object lookups return 404 without revealing whether a foreign job exists. API authentication failures return 401; users without a supported workspace role get 403. Django's existing CSRF middleware protects writes. Responses are marked `no-store`.

API serialization uses an explicit allowlist. Agency/tenant payloads never contain `internal_notes`, private property access notes, reporter email, status-event actor identities or subcontractor details. The first slice has no subcontractor assignment integration. The PM name and agency/property information shown are the same public workspace relationships already supported by onboarding.

## Status lifecycle

`awaiting_review` → `reviewed` → `in_progress` → `completed`

`awaiting_review`, `reviewed` and `in_progress` can also move to `cancelled`. Completed/cancelled requests cannot be reopened in this first slice. Reviews/status changes do not dispatch a contractor, authorize spending or send email. Timeline entries expose status/time only; internal actor identity remains in database audit records.

Every write requires the last-read integer `version`; successful updates increment it. Stale versions return 409. The conditional database update and status/audit records share a transaction, preventing silent overwrites and partial audit history.

## Endpoints

All paths use the current Django session, same origin, and existing CSRF protection; no separate backend, API token system or CORS service was introduced.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/maintenance/` | Authenticated portal using the existing shell, assets and CSS |
| GET | `/api/maintenance/context/` | Current role, allowed properties and categories; sets CSRF cookie |
| GET | `/api/maintenance/requests/?page=1` | Scoped results, 50 per page, count and next page number |
| POST | `/api/maintenance/requests/` | Tenant report: `property` UUID, `title`, `description`, `category` |
| GET | `/api/maintenance/requests/<uuid>/` | Scoped request, public timeline, version and allowed next statuses |
| PATCH | `/api/maintenance/requests/<uuid>/` | Manager status update: `status`, `version` |

Writes must send `Content-Type: application/json` and `X-CSRFToken`. Unknown fields, malformed input, invalid categories and invalid transitions are rejected. Public job references derive from the UUID; no browser-generated sequential identifiers are trusted.

## Local setup and use

From the repository root with Python 3.12:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r portal/production/requirements.lock
export DEBUG=1
export SMTP_DELIVERY_ENABLED=0
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
cd portal/production
python manage.py migrate
python manage.py runserver
```

Use existing onboarding to create/verify agency accounts, invite PMs, assign properties and link tenants. Real SMTP remains disabled; the existing account tests exercise invitations without sending mail. Do not bypass verification on an exposed server. For controlled local administration, use `python manage.py createsuperuser` and set the username to the same email used for login. No shared credentials or seeded business records are added.

Log in at `/login/`, then open `/maintenance/` or the **Maintenance requests** account link. The static demo is still separately runnable from `portal/dist/`, and public-site files/links are untouched. Existing browser records are not imported into authenticated accounts.

`0002_maintenancerequest_maintenancestatusevent_and_more.py` adds the request/history tables, property/status index and status constraint. It does not rewrite `0001` or modify existing account/property records. Database persistence requires retaining the configured database file/volume; migrations do not provide backups.

## Frontend and deployment packaging

`portal/production/static/maintenance.js` is a small same-origin adapter. Django serves the original `portal/dist/index.html` shell at `/maintenance/`, retaining its inline styles and linked stylesheets while replacing demo scripts with this adapter. It fills the existing category/report, repair list and detail/timeline layout. Mobile header, menu and bottom navigation reuse the original markup/classes. No original demo HTML, JavaScript, CSS, images or public website files were edited.

Features outside this slice are not connected in live mode. The live interface has no role impersonation, sample identities, local demo persistence, attachment controls or unsupported financial actions. A failed save preserves form entries; errors and stale status conflicts are visible. Refresh reads persisted server state.

Static discovery includes the original assets under `maintenance-ui/`. Docker's proposed build context now uses the repository root to include both Django and portal assets, copying the latter to `/app/frontend/`; root `.dockerignore` excludes secrets and local state. Compose, ports and services are otherwise unchanged. Docker deployment is not exercised or executed by this work. Continue using Compose from `portal/production/`; manual Docker builds would use `docker build -f portal/production/Dockerfile .` from the root. This is packaging guidance, not a deployment instruction for this phase.

## Verification

Run the default source/API checks:

```bash
bash scripts/check.sh
```

To include the real Chromium workflow, install Node Playwright 1.62.1 and its Chromium browser, then run:

```bash
SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh
```

If using a system Chromium, also set `SEVLINK_CHROMIUM_PATH` to its executable. The optional browser test uses Django's isolated temporary test database and test sessions. It creates no production accounts and leaves no runtime database fixtures. Default runs skip that one test when browser tooling is unavailable.

Local result: **25 Django tests passed including the browser workflow**, comprising six original onboarding tests, eighteen maintenance/API tests and one browser test. Both original Node demo suites, all JavaScript syntax checks, Django system checks and migration consistency passed. Chromium covers tenant submission, PM update, logout/new tenant session, Super Admin view, mobile navigation/layout, loaded assets and absence of demo role switching/IndexedDB use in live mode.

Maintenance API coverage includes agency/PM/cotenant isolation, invalid memberships and inactive users, forged ownership/status/private fields, invalid/malformed input, pagination, CSRF, method restrictions, status transitions, stale writes, transaction rollback, private-field serialization and protected parent records. Local tests use SQLite. CI additionally runs Django tests against PostgreSQL 17 and a separate SQLite/Chromium job; check the branch's Actions run for remote results.

## Remaining work

- Photos/private uploads and document access controls.
- Tenant/PM editing, richer review notes, operational dispatch and a complete staff permission model.
- Quotes, approvals, deposits, payments, attendance, appointments, invoices, subcontractor assignments and cancellation rules beyond the basic request lifecycle.
- Notifications, verified email delivery, background workers and retention policies.
- Full frontend integration for other portal screens; current browser-demo records remain separate.
- Deployment/staging validation, PostgreSQL concurrent-load tests, Docker/Caddy testing, proxy-aware throttling, backups/restore, monitoring and production security/operational review.

No production deployment, paid AWS service or merge to main is part of this phase.
