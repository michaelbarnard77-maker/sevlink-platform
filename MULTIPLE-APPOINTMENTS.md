Multiple appointments and manual rescheduling
============================================

Attendance confirmation initially puts the job in Booked. Operations can add visits to the same job and choose a different subcontractor for each visit. A full working day is 09:00–17:00 South African time; hourly bookings offer one through seven hours.

Each appointment starts Booked and has three manual planner choices: On site (blue), Complete (green), and Cancelled (red). Attended is no longer a new choice; historical records remain. Changing an appointment does not move the overall job status. Cancelling one appointment preserves the other visits and adds a Sevlink-only Needs rescheduling alert. Operations manually books its replacement; the original cancellation remains in history and its alert clears. PM attention rules remain unchanged.

Migration 0036 adds appointment progress and optimistic concurrency versions, with a history-preserving backfill. Status updates require scheduling access, reject stale versions and use idempotency keys. Private cancellation reasons stay in Operations.

Local Windows installation: stop runserver with Ctrl+C, run scripts/update-windows-multiple-appointments.ps1 in PowerShell, wait for green SUCCESS, then restart the existing server and refresh with Ctrl+F5. The cumulative updater verifies all embedded files, backs up SQLite and source, applies migrations through 0036 and restores the previous local version on failure. Accounts, payments and attachments are preserved. Live email remains disabled. No hosting deployment is included.

Validation: Django system and migration-drift checks passed. The 61 scheduling/workflow tests passed (six database-concurrency checks skipped on SQLite); all eight completion-delivery tests passed after updating historical Attended fixtures to On site. Authenticated Chromium proof captured 40 screens and exercised multi-day booking with two suppliers, all three independent statuses, private rescheduling alerts, and manual replacement. Installer payload integrity verified for all 27 files.
