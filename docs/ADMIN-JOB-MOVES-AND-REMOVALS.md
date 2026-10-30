# Sevlink manual job moves and removal controls

The owner's approved choices are a Sevlink-only manual override with a recorded reason, and tenant account/contact removal while retaining jobs and financial history. These controls are restricted to authenticated Super Admins; PM, agency-admin and tenant roles cannot invoke them.

## Manual job movement

Each staff job header has **Move job manually**. The operator selects a pipeline stage, records a required reason and confirms the override. The server locks the job, checks its version and retry key, updates its status/closed timestamp, saves an immutable WorkflowDecision and status event, and refreshes the dashboard/register. Staff can move to Booked or Closed despite missing normal prerequisites, or reopen a job.

Moving a stage does not create a calendar appointment, approve expenditure, verify a payment or invent completion evidence. Existing invoice balances, PDFs, official/request numbers and confirmed appointments remain unchanged. Subsequent ordinary actions still apply their normal financial/scheduling checks; reconciliation can reopen a closed job. Override reasons are staff-only, while authorised participants receive a generic stage update. The stage override applies at its saved job version and later normal status changes can recalculate the stage.

The selected Operations Overview number is now white on navy. Unselected numbers remain readable on their white cards.

## Removal workflow

Under **Agencies**, each agency has Remove agency. Expand a property for Remove property and its tenants' Remove tenant buttons. Read the preview, review the scope/counts and type **REMOVE**. Preview GETs do not mutate data. The signed, ten-minute token is bound to the operator, entity and current records; concurrent/stale changes require a fresh preview.

**Remove tenant** disables login, invalidates sessions, removes OTP devices, replaces the username/email/names with non-identifying placeholders, clears tenancy name/email/phone, revokes and anonymises invitations, retires/clears account messages and replaces captured activity actor names. An inactive actor stub preserves the original job/ledger foreign keys. Jobs, original text, photographs, quote/invoice PDFs and financial facts remain. This clears structured account/contact information; it does not redact personal information contained in retained job text or original documents.

**Remove property/agency** permanently removes the selected entity and its linked repair, quote, invoice/payment, calendar, document, notification and history rows. The preview follows incoming foreign keys/M2M links, explicit completion-message ownership, document reference reservations and exact legacy audit references. Shared or protected staff accounts and global location/supplier catalogues are retained. Exclusive tenant accounts (and agency accounts for agency removal) are cleared. Cross-property/agency relationships are rejected before removal rather than expanding the selection. Agencies with staff/customer membership conflicts require an account-access review, so deleting a membership cannot activate previously blocked staff capabilities. Interactive removal is capped at 20,000 linked rows. Numbering counters are not reset.

The explicit scoped purge uses raw deletes only after the full signed preview/confirmation and row locks; ordinary PROTECT/append-only methods remain unchanged. Database FK constraints remain enabled. All row removal and account clearing share one transaction. Private files are deleted after commit. A new **RemovalReceipt** stores the operator, type, counts and any pending private-storage cleanup keys, without keeping the removed entity's name/contact details. Storage failures remain retryable in Agencies, including after a page reload. Backups and already delivered emails are not erased.

## Schema, local installation and limits

Migration **0034_removal_receipt** creates one audit/cleanup table without rewriting existing customer rows. The verified updater `scripts/update-windows-admin-controls.ps1` backs up the current SQLite DB/source, checks the existing 0032+ baseline, installs twenty source files and migrates through 0034. On failure it restores the previous database/source. Stop the owner's local runserver first, run the Raw script in PowerShell, wait for SUCCESS, restart the original server and Ctrl+F5. Installation does not execute a manual move/removal, delete existing records, enable email or deploy anywhere. Payloads are verified here; Windows execution requires confirmation on the owner's computer.

## Verification

Full regression: **282 tests; 264 passed and 18 PostgreSQL-only skipped**, with source scenarios, JS syntax, Django system and migration-drift checks passing. The final seven focused tests additionally cover malformed cross-property invoice links, retained unrelated invoice PDFs, removal of quote-reference reservations, multiple invitation anonymisation, login/session revocation, retry-deduplicated manual Booked/Closed/reopen actions, private reasons, stale previews, transactional rollback and storage cleanup retries.

Actual authenticated browser acceptance: **95 screenshots** across all four profiles and source reference, including white selected counts, job moves without fictional appointments/receipts, tenant removal with job/invoice access retained for staff, and property/agency previews. The final scoped administrator walkthrough also passed with 15 captures. Screenshots and logs are in `visual-proof/admin-controls-2026-10-29/`.

All removal/move tests use synthetic persisted records and isolated temporary SQLite/private storage. No owner/customer records were removed or moved. PostgreSQL-only cases and current GitHub CI are not claimed to have passed. No merge, AWS update, public deployment or live-email activation occurred.
