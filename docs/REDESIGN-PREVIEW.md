# Corporate redesign: local review

This branch restyles the existing application. It is not a production deployment.
The original logo, role-scoped APIs, original documents, numbering and financial
workflows are retained. No application schema migration is introduced by the redesign.

## Windows CMD

Install Git and Python 3.12 or newer (including the Python launcher). For a separate
checkout that cannot overwrite your existing checkout, run in CMD:

```cmd
cd /d "%USERPROFILE%"
git clone --branch redesign/dark-corporate https://github.com/michaelbarnard77-maker/sevlink-platform.git sevlink-redesign-preview
cd sevlink-redesign-preview
Preview-Redesign.cmd
```

The first run installs the locked dependencies into a separate virtual environment.
Choose a strong local preview password when prompted; it is never displayed.
Open http://127.0.0.1:8000/ in your browser. Keep CMD open; Ctrl+C stops the server.

Preview logins share only the password you chose:

- Super Admin: `superadmin@sevlink.example`
- Agency Admin: `admin@sevlink.example`
- Property Manager: `pm@sevlink.example`
- Tenant: `tenant@sevlink.example`

Use separate browser profiles to compare roles simultaneously. Separate Incognito
windows in the same browser share a session.

On later runs, start `Preview-Redesign.cmd` again. To update this separate checkout:

```cmd
git fetch origin
git merge --ff-only origin/redesign/dark-corporate
Preview-Redesign.cmd
```

If the clone folder already exists, do not delete it or reset another checkout.
Open that folder and use the update commands above if it is the preview checkout.

## Isolation

`config.redesign_preview` requires an explicit local-preview flag. Its database,
private attachments and stable local session secret live under
`%LOCALAPPDATA%\Sevlink\RedesignPreview`, separate from `development.sqlite3`,
existing private files and any PostgreSQL configuration. It binds to loopback only.
Both live mail delivery flags are disabled. MFA and scanning are disabled only in
these explicit local preview settings; normal production defaults are unchanged.

`create_redesign_preview` refuses normal settings and creates four synthetic users
only in a new, empty preview database. Rerunning it preserves preview records and
passwords. A second fictional agency provides a visible isolation check for staff.
No accounts, jobs or invoices are inserted into a real application database.

The browser-local `portal/dist` demo is retained separately. Use the Django preview,
not a static HTTP server, to inspect real permissions and workflows.

## What changed

- Corporate CSS shared by authenticated, account, private-client and public views.
- Recent activity uses existing role-scoped feeds; opening the dashboard does not
  mark any notification read or grant access to another portfolio.
- Professional category SVGs and all 19 categories shown, retaining PM/Admin-only
  renovations submission and the existing server-side restriction.
- Repair details, access/authorisation and review steps retain selected files,
  submit once through the original multipart endpoint, and retain backend validation.
- Job header, prominent address, role-aware progress guide, shared-file previews,
  key information and shortcuts enhance the original tabs and forms.
- Private Costs remains Super Admin-only. Internal notes remain staff-only.
- Public subcontractor interest is a saved Website enquiry, not an account or
  supplier approval; it reuses the existing enquiry inbox and mail queue.

## Verification

Use `scripts/check.sh` with the repository's locked Python dependencies. Real
browser suites require Playwright, Chromium and `SEVLINK_BROWSER_TESTS=1`.
The optional PostgreSQL suite remains necessary for concurrency-specific checks.
No checks in this change require production access or real email delivery.

Legacy test assertions were aligned with already-existing behaviour: selected
actionable emails, the internal-note capability flag, owner-led onboarding,
property folders, unread-only inbox display and appointment-driven job progress.
These corrections do not change those business rules.
