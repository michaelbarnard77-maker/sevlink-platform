> Step 7 is now implemented on the development branch: externally uploaded quotation PDFs/revisions/decisions and invoice PDFs/manual payment records, private Operations conversations/files and notification bell/read receipts. See [the Step 7 checklist](STEP-7-QUOTATIONS-AND-OPERATIONS.md). Local setup and review accounts below still apply.

> Current development update: shared comments, basic quotation issue/decisions and
> durable Operations notifications are now real Django workflows. Delivery remains
> local-only. See [Operations notifications](OPERATIONS-NOTIFICATIONS.md) for the
> current workflow, worker instructions and delivery limits. The original demo's
> advanced financial/dispatch behavior remains simulated.

> Private attachment follow-up is implemented on this same development branch.
> After installing the updated lockfile and running migrations, you can attach photos
> or PDFs in the report form or job details. The original test instructions remain valid.
> See [private attachments](PRIVATE-ATTACHMENTS.md) for current file limits and tests;
> the historical simulated-upload description below applies to the standalone demo.

# Verify Phase 1 locally

Use the `development/phase-1-foundations` branch. This guide runs the real Django portal on your own computer. It does not deploy or enable email, AWS or any paid service. Commands below are for Bash/macOS/Linux with Python 3.12 and Node 24 installed. Authenticate Git locally to access the private repository; do not put GitHub tokens into commands or source files.

## Start a local review copy

```bash
git clone --branch development/phase-1-foundations https://github.com/michaelbarnard77-maker/sevlink-platform.git sevlink-phase1-review
cd sevlink-phase1-review
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r portal/production/requirements.lock
export DEBUG=1
export SMTP_DELIVERY_ENABLED=0
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export ALLOWED_HOSTS=localhost,127.0.0.1
export SITE_URL=http://127.0.0.1:8000
unset DB_HOST
cd portal/production
python manage.py migrate
python manage.py shell -c "exec(open('../../scripts/create-phase1-review-accounts.py').read())"
python manage.py runserver 127.0.0.1:8000
```

The setup helper prompts you to choose and confirm five passwords, applies Django password validation and stores only Django password hashes. Use at least 12 characters and follow the prompts. No passwords are embedded in code, printed, or emailed. It refuses non-development settings, non-SQLite databases, enabled SMTP, or existing review accounts; it never overwrites existing accounts or resets their passwords. It creates only synthetic local test records. Do not add the resulting database to Git.

| Login email | Role | Agency / property |
| --- | --- | --- |
| `tenant-a@review.example.test` | Tenant A | Agency A / Home A |
| `pm-a@review.example.test` | Property manager A | Agency A / Home A |
| `tenant-b@review.example.test` | Tenant B | Agency B / Home B |
| `pm-b@review.example.test` | Property manager B | Agency B / Home B |
| `superadmin@review.example.test` | Sevlink Super Admin | All agencies |

The helper creates active local accounts so you can test maintenance without SMTP. This intentionally bypasses the onboarding/invitation flow for these synthetic records; it does not verify email delivery or invitation UX. Normal registration/invitations remain implemented in Django and covered by the original tests.

Open **http://127.0.0.1:8000/login/** and enter the email and password for the account you want to test. After login, click **Maintenance requests** or open **http://127.0.0.1:8000/maintenance/**. There is no `/admin/` site in this project; Super Admin uses the same login and maintenance URL, with global permissions.

Use three separate browser profiles or different browsers for Tenant A, PM A and Super Admin. Normal tabs share a login cookie; multiple private windows in the same browser may also share a session. Keep the hostname consistent (`127.0.0.1`) across all steps. Browser role selectors belong to the static demo and must not be used for this verification.

To restart, keep the same terminal environment and run `python manage.py runserver 127.0.0.1:8000` again. The SQLite file at `portal/production/development.sqlite3` retains accounts and requests. A new shell requires activating the venv and exporting the local settings again; generating a new secret invalidates old sessions, so sign in again. Do not rerun the account helper after accounts exist.

## Simple manual checklist

- [ ] **Anonymous access:** a logged-out browser opening `/maintenance/` is sent to login. `/api/maintenance/requests/` returns 401 without listing jobs.
- [ ] **Tenant submission:** sign in as Tenant A, choose Report a repair → Plumbing, enter a title/description, and submit for Home A. It appears in Repair jobs with Awaiting property manager review.
- [ ] **Correct property:** Tenant A can choose Home A only; Home B does not appear. Tenant A has no status-update control or role-switch dropdown.
- [ ] **PM review:** sign in as PM A, open the job and save Reviewed. The timeline updates. PM A cannot create a tenant report.
- [ ] **Persistence:** sign out Tenant A, sign in again and open the report. Reviewed remains visible. Restart the local server and verify it remains.
- [ ] **Progress:** PM A can move Reviewed → In progress → Completed. Test cancellation on a separate new report; completed/cancelled jobs cannot be reopened in Phase 1.
- [ ] **Second agency:** Tenant B submits a report for Home B. PM B sees that report but not Agency A's report. PM A sees Agency A's report but not Agency B's.
- [ ] **Direct URL isolation:** while signed in as PM A, open `/api/maintenance/requests/` and copy Agency A job's full `id`. In PM B's browser, open `/api/maintenance/requests/PASTE-ID-HERE/`. Expect 404, with no Agency A job data. Repeat in Tenant B's browser.
- [ ] **Global visibility:** Super Admin sees both agencies' jobs at `/maintenance/`, including requests awaiting review. No ordinary staff flag is required for tenant/PM accounts.
- [ ] **Private data:** inspect request/detail and context JSON as Tenant A and PM A. There must be no `internal_notes`, event `actor`, subcontractor identities, or the helper's `LOCAL PRIVATE ACCESS TEST` value. PMs may see their property's access notes in the older account/property dashboard; tenants must not.
- [ ] **Stale update:** open the same job in PM A's browser and Super Admin's browser before updating. Save Reviewed in one; try a status save from the stale dialog in the other. Expect a refresh/conflict message, not a silent overwrite.
- [ ] **Validation and mobile:** empty report fields cannot submit. Check the portal at phone width: Menu, Jobs, Report, form, detail and sign-out remain usable.
- [ ] **Demo separation:** the authenticated workspace says SIGNED IN and has no demo role switch. The standalone static demo still behaves as before and its records do not appear in the real Django portal.

Only test with synthetic records and locally chosen review credentials. There is no subcontractor assignment model/UI connected in Phase 1; privacy tests also inject synthetic internal notes directly into the temporary test database to verify they are excluded.

## Automated checks

From the repository root, with the virtual environment activated:

```bash
bash scripts/check.sh
```

The default run executes the original demo suites, syntax/system/migration checks and all Django/API/migration tests. It skips the optional browser test unless enabled. For the full Chromium test:

```bash
npm install --prefix /tmp/sevlink-browser-tools --no-save playwright@1.62.1
/tmp/sevlink-browser-tools/node_modules/.bin/playwright install chromium
export NODE_PATH=/tmp/sevlink-browser-tools/node_modules
SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh
```

On Linux, missing Chromium system libraries may require Playwright's documented `install --with-deps chromium` setup. A system Chromium is also supported through `SEVLINK_CHROMIUM_PATH`. Automated fixtures use a separate temporary test database and do not reuse your manual review accounts.

Local verification after the review fixes: **28 tests passed**, including the real Chromium workflow and additive migration preservation test; both original Node suites also passed.

GitHub Actions runs the full SQLite/Chromium suite and a PostgreSQL 17 job. PostgreSQL CI applies migrations and runs Django tests, but does not run the Chromium test. Check the PR's checks for the latest result.

## Review findings and limits

- **Fixed in review:** the original account dashboard allowed any `is_staff` user to see global agency names/counts. It now requires `is_superuser`, consistent with the maintenance API. Unknown membership roles also fail closed. Regression tests cover both.
- **Fixed in review:** PM permission was initially checked before reading the request but not repeated in the conditional database write. The update now also scopes the SQL write by the currently authorized property set. A test reassigns the property between read and write and verifies the former PM cannot update it.
- **Authentication:** existing Django sessions, hashed passwords, active-account checks, CSRF and POST logout are reused. Superuser access is deliberately global; ordinary staff does not qualify. No separate backend or token login was introduced.
- **Data isolation:** job list/detail/create/update are scoped by agency and role. Tenants see their own reports on active linked properties; PMs see their assigned portfolio. Explicit response fields omit internal notes and actor identities. PM names and agency/property information are intentional workspace data.
- **Migrations:** 0002 is additive; it adds two tables, a status constraint and index, without editing 0001. The upgrade regression test creates account/property/tenancy records at 0001, upgrades, and checks they survive. Reversing 0002 would delete new request/history tables and their contents; back up data before any real migration or rollback.
- **Demo separation:** `/maintenance/` strips all demo scripts and loads only the Django adapter. No localStorage, sessionStorage or IndexedDB persistence is used there. Search and page/view selections are temporary UI state; searches cover the current 50-row page. Original demo files remain unchanged and browser-local.
- **Remaining hardening:** maintenance submission has no dedicated per-account rate limit or retry/idempotency key; an uncertain network retry can create a duplicate. PostgreSQL concurrent-load and account/tenancy-change race testing, Docker/Caddy deployment validation, MFA for privileged users, production secret/storage policy, backups/restore and monitoring remain outstanding. Existing login IP throttling needs trusted reverse-proxy handling before deployment.
- **Scope limits:** one agency per user, no reopening completed/cancelled requests, no online uploads, no emails on status changes and no financial/dispatch authorization. No production-readiness or live-security certification is implied by passing these tests.

## Real versus simulated

| Area | Current behavior |
| --- | --- |
| Django account registration, invitations, password hashing, login/logout/reset, agency/property/tenant links | Real server-side implementation; SMTP delivery remains disabled until configured |
| `/maintenance/` tenant submission, scoped job lists/details, PM status changes, tenant status/timeline, Super Admin view, audit records | Connected to Django and its configured database |
| Original `portal/dist/` demo, role switching, uploads, quotes, payments, bookings, operations/subcontractor planner, invoices | Preserved simulation; browser-local, separate from Django |
| Public marketing site | Real static website; enquiry links prepare email/WhatsApp drafts, not stored leads or automatic delivery |
| Other demo features in authenticated mode | Not connected or exposed yet; no hidden background simulation |

No design change, merge, AWS deployment or paid service is part of verification.
