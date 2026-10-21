# Safe Windows local test update

This updates an existing **local development** installation. It does not deploy,
merge main, send real email or create cloud services. Use synthetic test data.
Do not delete the existing database, private attachments or account history.

## 1. Stop and inspect

Stop Django with Ctrl+C and stop any local email workers. Close other processes
using this test database. Open PowerShell in the existing repository folder:

```powershell
git status --short --branch
git branch --show-current
```

The branch must be `development/phase-1-foundations`. If there are local edits,
stop and preserve/review them; do not reset, clean, force checkout or overwrite them.
Keep your existing local configuration and secret key. Never paste secrets into
GitHub, screenshots, commands sent to other people or a public backup folder.

## 2. Back up the local database and private files

The examples assume your existing Python environment is
`portal\production\.venv`. Substitute the actual existing environment if different;
activation is not required. From the repository root:

```powershell
$repoRoot = (Get-Location).Path
$python = Join-Path $repoRoot 'portal\production\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Locate your existing virtual environment before continuing.' }
$backupRoot = Join-Path $env:LOCALAPPDATA ('Sevlink\Backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupRoot -ErrorAction Stop | Out-Null
git rev-parse HEAD | Set-Content (Join-Path $backupRoot 'previous-commit.txt')
```

Check your existing database configuration first. If `DB_HOST` selects PostgreSQL,
use a verified PostgreSQL backup procedure for that local database and stop here
until it has been checked. The following is **only for the default local SQLite
file**, not PostgreSQL. It uses SQLite's backup API instead of copying an open DB:

```powershell
@'
import sqlite3, sys
from pathlib import Path
source = Path('portal/production/development.sqlite3')
if not source.is_file():
    raise SystemExit('Expected existing SQLite database missing. Stop and check configuration.')
with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as original:
    with sqlite3.connect(Path(sys.argv[1]) / 'development.sqlite3') as backup:
        original.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SystemExit('Backup integrity check failed.')
print('Local SQLite backup integrity verified.')
'@ | & $python - $backupRoot
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed; do not update.' }

foreach ($name in @('private-attachments', 'private-email-preview', '.env')) {
    $sourcePath = Join-Path $repoRoot ('portal\production\' + $name)
    if (Test-Path $sourcePath) { Copy-Item $sourcePath $backupRoot -Recurse -ErrorAction Stop }
}
```

If private files/configuration are located elsewhere, back up those actual paths
instead. Protect this backup: it contains personal documents and potentially
login links/secrets. Do not commit or serve it. A tested coordinated database/file
restore is still required for production; this local backup is not cloud readiness.

## 3. Update the development branch

Only after a successful backup and a clean working tree:

```powershell
git fetch origin
git switch development/phase-1-foundations
git pull --ff-only origin development/phase-1-foundations
Set-Location (Join-Path $repoRoot 'portal\production')
& $python -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
```

Reuse your existing local environment configuration. Django does not automatically
load `.env`; use the same safe configuration method you already use. Confirm it
points to your local test database, then keep outbound sending disabled:

```powershell
$env:DEBUG = '1'
$env:SMTP_DELIVERY_ENABLED = '0'
$env:OPERATIONS_LIVE_DELIVERY_ENABLED = '0'
$env:OPERATIONS_EMAIL_DELIVERY_BACKEND = 'portal.mail.PrivatePreviewBackend'
& $python manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Configuration check failed.' }
& $python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Unexpected schema drift; stop.' }
& $python manage.py migrate --plan
if ($LASTEXITCODE -ne 0) { throw 'Migration plan failed.' }
```

Review the plan, then:

```powershell
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; retain the backup and stop.' }
& $python manage.py test portal
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not use the updated application.' }
& $python manage.py runserver
```

Local browser and PostgreSQL-only tests may be skipped without their installed
tools/database. GitHub runs those checks separately. Never aim a local test run
at production. If migration 0018 finds legacy banking records, follow the reviewed
bank-removal procedure; do not bypass the guard or silently discard them.

## 4. Test the real portal

Open `http://127.0.0.1:8000/maintenance/` and hard-refresh the browser (Ctrl+F5).
Use separate browser profiles for PM, tenant and Sevlink staff. The public hosted
demo link is a different, browser-local application.

- PM: confirm the ten navigation pages, Needs Your Attention, a reviewed request
  disappearing, quotation decisions, invoice/deposit filters and amounts.
- Only authorised Sevlink staff may record confirmed customer payments. PMs cannot
  mark their own invoices paid. Supplier invoices/payments/rates remain private.
- An Ops booking needs a confirmed 50% deposit or a recorded, authorised scheduling
  arrangement. A statement or uploaded receipt from a customer is not a payment.
- Staff must explicitly share confirmed appointment dates/times. Existing private
  bookings stay private after migration. PMs see their portfolio; tenants see only
  their own reported repairs and their shared appointments, never team calendars.
- Check another PM/agency and co-tenant cannot access the same documents/calendar.
- Changes remove resolved attention cards on refresh, modal close, navigation, or
  the one-minute visible-page refresh. Acknowledging an appointment marks it
  reviewed; it does not cancel it or change the job status.

Migration 0025 adds immutable sequential `SV-000001` style job numbers, backfilled
in saved creation order. UUIDs and legacy SV-UUID links remain available. SQ/SI
numbering, external PDF references and existing financial records are unchanged.
0026 prevents duplicate unresolved information requests. Stop all app writers
while migrating. Do not reverse these migrations or restore only half a backup.
If recovery is needed, stop the server and have the matching code/database/files
restored together through a reviewed procedure.
