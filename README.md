# Sevlink source export for Codex

This archive contains the complete source currently available for the Sevlink work completed in the hosted demos and the available backend foundation. It preserves the existing design, branding, pages, navigation, styling, assets, tests and demo behaviour.

## Contents

- `portal/` — the existing Sevlink agency and Sevlink Operations portal demo.
  - The browser app is in `portal/dist/`.
  - Its scripts are plain JavaScript and its styling is plain CSS.
  - The portal has no React, TypeScript or `package.json` source available in the exported project. It is a static browser demo with multiple JavaScript modules loaded by `dist/index.html`.
  - Tests are in `portal/tests/`.
  - The available backend foundation is in `portal/production/`.
- `public-site/` — the existing public Sevlink marketing website demo.
  - The site is in `public-site/dist/`.
  - It is also plain HTML, JavaScript and CSS with no build dependencies, React source, TypeScript source or `package.json` available.

## Run the portal demo locally

From `portal/dist/`, start any static web server. For example, with Python:

```bash
cd portal/dist
python3 -m http.server 8080
```

Open `http://localhost:8080` in a browser. The portal demo stores its records in browser storage. It does not create shared accounts or synchronise data between browsers or devices.

## Run the public website locally

```bash
cd public-site/dist
python3 -m http.server 8081
```

Open `http://localhost:8081` in a browser. The public enquiry form prepares WhatsApp and email drafts; it does not send messages or create portal accounts automatically.

## Run the available backend foundation

The backend foundation is a Django project in `portal/production/`. It includes account, agency, property, property-manager invitation, tenant invitation and basic role-scoped dashboard foundations.

Requirements are listed in `portal/production/requirements.txt` and locked in `requirements.lock`. A quick local setup is:

```bash
cd portal/production
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
export DEBUG=1
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
# Django reads process environment variables; it does not load .env automatically.
python manage.py migrate
python manage.py runserver
```

The production settings require real secrets, HTTPS, a PostgreSQL database and a configured site URL. Do not use the example values in production.

## What is a demo or still needs production work

The portal UI already demonstrates the intended workflow, including agency and property-manager views, tenants, repair categories, quote and invoice screens, deposits and payments, scheduling, attendance, operations calendar, subcontractor planning, job cancellation and website issue reporting. In the current hosted demo these records are browser-local and the role selectors are a simulation.

The Django backend is not yet connected to the portal UI and is not a complete production backend. The following still need implementation and integration before launch:

- Repair, quote, invoice, payment, deposit, appointment, attendance and cancellation models and API/views.
- Centralised document and photo uploads with private object storage and access control.
- The Operations calendar, subcontractor assignments and private Sevlink-only data.
- Production email delivery for invitations, updates, quote links and invoices.
- Online payment-gateway integration, if required.
- Full production frontend-to-backend authentication and permissions.
- Production database deployment, backups, monitoring, restore testing and load testing.
- Final DNS/domain connection and production security review.

The available source does not silently claim these items are finished.

## Hosted demo references

- Agency portal demo: https://sevlink-maintenance-demo.ableisle4.chatgpt.site
- Public website demo: https://sevlink-public-demo.ableisle4.chatgpt.site

The hosted demos were private review sites at the time of export. The custom domain was prepared but was not assumed to be connected or publicly enabled.

## Export provenance

- Export date: 2026-10-20 (South Africa time)
- Portal repository: `/workspace/sites/sevlink-maintenance-demo`
- Public site repository: `/workspace/sites/sevlink-public-demo`
- The export excludes `.git` directories, Python cache files and `portal/production/development.sqlite3` (local generated database state).

## Phase 1 development workflow

On `development/phase-1-foundations`, Django now supports tenant maintenance reports,
PM/agency status review, persistent status history and Super Admin visibility.
After migrating and signing in, open `/maintenance/`. The authenticated workspace
reuses the existing portal layout/CSS and reads scoped Django APIs; the original
static demo and public site remain unchanged. See [Phase 1 workflow](docs/PHASE-1-WORKFLOW.md)
for permissions, endpoints, setup, tests and unfinished features.
Use [Phase 1 verification](docs/PHASE-1-VERIFICATION.md) for local review accounts and a manual checklist. This is not a
production deployment or a completed port of every demo feature.

The earlier export description and review document the baseline before this phase.

## Repository preparation and review

- [Architecture and review](docs/PROJECT-REVIEW.md): current components, boundaries and launch gaps.
- [Private GitHub setup](docs/PRIVATE-GITHUB.md): safe first push and repository settings.
- `scripts/check.sh`: JavaScript syntax, supplied portal tests, Django checks and tests.
- `.github/workflows/checks.yml`: runs these checks on pushes and pull requests without production secrets.

The `dist/` directories are the available editable frontend source. Keep them in Git.
No design, branding, page, script-loading order or application behavior was changed during repository preparation.

## Private attachments development update

The development branch now supports authenticated private photo/PDF uploads and
downloads using local Django storage. See [private attachments](docs/PRIVATE-ATTACHMENTS.md)
for limits, permissions, storage/S3 architecture, tests and production prerequisites.
The original static demo remains separate and unchanged.
