# Sevlink source review

Reviewed 20 October 2026 from `sevlink-codex-source-export.zip`. This is a source and local-runtime review, not an audit of a running production server. No deployment credentials, production database, server inventory or production logs were supplied. The `production` directory name describes intended use, not demonstrated deployment status.

## Current structure

| Component | Location | Runtime and responsibility |
| --- | --- | --- |
| Agency/Operations portal | `portal/dist/` | Static HTML, CSS and plain JavaScript; browser-local workflow demo |
| Portal regression suites | `portal/tests/` | Node VM harness exercising real workflow functions with browser/persistence adapters |
| Public website | `public-site/dist/` | Static marketing pages, service selection and enquiry draft generation |
| Backend foundation | `portal/production/` | Django 5.2, server-rendered templates, custom user model and account/property onboarding |
| Proposed deployment | `portal/production/{compose.yaml,Dockerfile,Caddyfile}` | Caddy HTTPS proxy → Gunicorn/Django → PostgreSQL 17; named database/static/TLS volumes |

There is no missing frontend build command: the exported `dist/` files are the available editable source. No React, TypeScript, npm package manifest or bundler was supplied. Keep both `dist/` trees tracked.

## Portal

`index.html` loads 24 classic scripts in a fixed order. `app.js` owns state, IndexedDB, rendering and base records. Later scripts extend/reassign functions in the shared global scope; these are not independent ES modules. Moving or bundling them without regression checks can change behavior.

Feature scripts cover repair reports and PM review, quotes, authority, finance, deposits, a single invoice, bookings, attendance, private subcontractor planning, operations calendar, cancellations, team management, repair register, support issues and mobile presentation. CSS is partly inline and partly in additional files.

`agency-start.js` enables a clean initial agency workspace. Illustrative seed records remain in source and tests, but the default fresh workspace is empty. IndexedDB database `sevlink-agency-demo` stores the state under `sevlink-zero-launch-v1`. Photos/documents and private planning state are browser data, not central storage. Changing browsers/devices or clearing storage loses access to those records.

Role selection and client-side filters demonstrate intended access rules. Anyone with browser developer tools can inspect browser-local state. These controls cannot protect real tenant, financial or subcontractor data. There is no Django API integration; the fetch of the logo is an asset request.

## Public website

`index.html` and `styles.css` contain the existing marketing layout and branding. `app.js` populates services, category search, dialogs, mobile navigation and enquiry previews. The enquiry form generates `mailto:` and WhatsApp links; the visitor sends the message in their chosen app. It neither stores leads nor sends email, uploads photographs or provisions portal accounts. Agency portal links point to the hosted demo, not the Django login. Existing contact information and links were preserved.

## Backend

- `config/settings.py`: environment-based configuration, SQLite in development, PostgreSQL when `DB_HOST` is set; production HTTPS checks, secure cookies, CSRF, HSTS and password validation.
- `config/urls.py`: registration, sign-in/out, verification resend, invitation acceptance, password reset and property/team pages. No repair/payment API is present.
- `portal/models.py`: User, Agency, Membership, Property, Tenancy, Invitation, MailQueue, Audit and RateBucket. Membership is one agency per user; existing accounts cannot be silently reassigned by invitation.
- `forms.py`, `views.py`, `services.py`: validation, transactions, server-side role/agency/portfolio filtering, hashed 48-hour invitation tokens, single-use acceptance and database-backed throttling.
- `mail.py` and `send_mail_queue`: queued outbound email. SMTP is disabled until explicitly configured/enabled. The proposed worker is external to Compose and must be scheduled separately.
- `templates/` and `static/portal.css`: separate server-rendered onboarding UI; it is not the full static portal connected to a database.
- `migrations/0001_initial.py`: initial database schema. No production data was exported.

## Findings and remaining work

1. **Launch blocker: backend workflow coverage.** Repair, quote, invoice, payment, deposit, appointment, attendance, cancellation and subcontractor workflow persistence are absent. Implement and authorize these on the server before exposing the demo as a client service.
2. **Launch blocker: frontend integration.** Replace simulated roles/browser persistence with authenticated server workflows while preserving the approved interface. Browser test isolation does not establish backend authorization for those missing features.
3. **Launch blocker: document privacy.** Add private uploads, file validation, size limits, controlled download authorization and retention. Do not treat browser-local documents as shared records or durable backups.
4. **Operational validation outstanding.** The supplied deployment is a proposal. PostgreSQL concurrency, Docker/Caddy behavior, SMTP delivery, DNS, backups/restore, monitoring, load and production configuration need staging verification. No live deployment was changed or certified.
5. **Proxy-aware throttling needs verification.** IP limits use `REMOTE_ADDR`, which behind Caddy normally identifies the proxy. Configure trusted client-IP handling before launch; do not blindly trust client-supplied forwarding headers. Current aggregate limits could throttle unrelated customers together.
6. **Mail queue lifecycle needs an operating policy.** Pending bodies contain usable invitation/reset links. Delivered bodies are scrubbed, but expired/failed entries require retention and cleanup. Use one worker as documented; SMTP acceptance followed by worker failure can cause duplicate delivery. No recurring worker is included in Compose.
7. **Maintainability risk.** Shared globals and layered function replacements make frontend script order significant. Preserve that order and run the existing workflow suites for future edits.
8. **Local setup documentation corrected.** Django does not load `.env` itself. The root quick start now exports local settings and installs the lockfile used by Docker/CI. Compose still loads its deployment `.env` as documented.

No HTML, CSS, frontend JavaScript, backend application code or deployment behavior was changed during this review. Both original hosting configurations are retained for the private GitHub import; their project IDs are not credentials.

## Verification

The repository verification script checks JavaScript syntax, both supplied Node workflow suites, Django system checks, migration drift and all supplied Django tests. See the final local result below. Django tests use SQLite; they do not establish PostgreSQL concurrency or production readiness.

Chromium startup smoke checks passed for both static sites at 1440px and 390px: no page JavaScript errors or horizontal overflow on initial load. This was a startup check, not exhaustive visual or interaction QA. No outbound enquiry or email was sent.

Local result: both Node suites passed; all 6 Django tests passed; JavaScript syntax, Django system checks and migration consistency passed. Comparison against the input archive confirms only the original root README changed; all supplied application/assets/configuration files remain byte-for-byte identical. A limited recognizable private-key/token pattern scan of intended tracked files found no matches; this is not a guarantee that every possible secret format is absent. Git whitespace checks flag pre-existing trailing blank lines in nine supplied JavaScript files, retained to preserve the source.
