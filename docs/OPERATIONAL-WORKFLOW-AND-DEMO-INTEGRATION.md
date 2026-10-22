# Authenticated Operations workflow and demo design integration

This extends the existing Django platform and reuses the demo shell, branding,
styles, existing UUID/job/document records, secure storage, event outbox, manual
ledger, private suppliers/teams and proportional calendar. The public website
and original browser-local demo are unchanged. No production deployment or live
email activation is part of this update.

## What the authenticated screens do

- Agency managers land at `/maintenance/`, not the old account-summary landing.
  Properties, tenants, invitations and access management remain available.
- PMs can report their own portfolio repairs. Tenants can report their linked
  property repairs and flag a safety concern; that flag cannot set official
  urgency, work type or spending authority.
- Operations retains ten saved-data stages and drill-down lists:
  New Requests, Quoting, Awaiting Quotation Approval, Awaiting Deposit, Ready to
  Schedule, Booked Appointments, Work Underway, Ready to Invoice, Awaiting Final
  Payment and Closed Jobs. No totals come from browser-local records.
- PM/Agency Admin dashboards show exactly eight cards: Needs Your Attention, New
  Requests, Awaiting Quote Approval, Awaiting Deposit, Booked, Work Underway,
  Awaiting Final Payment and Closed. The attention banner stays above the cards;
  its action count may exceed the unique-job count in the first card. Card clicks
  open scoped job lists. Only confirmed, non-cancelled shared appointments enter
  Booked; authorised call-outs and deposit-ready jobs await PM attendance action.
- Needs Your Attention includes reviews, quote decisions, additional spending,
  attendance requests, customer balances and unread job comments. Saved state
  resolves the underlying action; read state is separate from work status.
- The sidebar, category cards, navy/blue styling and outline icons use reusable
  styling. All 19 repair categories have different outline artwork. Properties
  have Add Property, Edit Property and Link Tenant buttons.
- Job detail has functional Overview, Comments, Quotations, Invoices, Attendance,
  Reports & Photos and Activity / Timeline tabs. Super Admin alone also gets
  Private Costs and the FINANCE navigation section.
- Operations can drill into registered agencies, properties, managers, active
  tenants and maintenance jobs. The existing region/supplier directory, teams,
  compliance, private rates and weekly calendar remain in place.

## Authorisation and references

New requests use REQ-0001; UUID relationships and secure links remain unchanged.
Review and Route Request saves the assigned PM/agency admin's work type, official
Normal/High/Urgent urgency, access responsibility, further information and reason.
Material actions record actor, timestamp, version, immutable decision snapshot
and event. Operations cannot silently edit the PM's decision through the old
urgency shortcut.

A Call-Out approval requires a positive VAT-inclusive total ceiling and allocates
one global non-annual SV number. There is no quotation or deposit gate for that
call-out. Agency invoice totals cannot exceed its approved ceiling. Higher work
requires a fresh PM decision. A declined increase does not raise the ceiling.
Requesting a formal quotation creates a separately linked request with its own
REQ; its future approval allocates its own SV. The original call-out remains
separate and retains its original documents, limit and financial history.

Quoted work requires PM classification, an externally prepared PDF, a manually
entered quotation reference and an explicit Send for Approval action. Drafts stay
private. The assigned PM or the agency administrator can decide; the actual actor
and time are saved. Approval alone allocates SV, without making an appointment.
SQ references and external invoice references are never generated. Revised PDFs,
immutable approvals and the existing duplicate/stale/concurrent controls remain.

For new quoted work, confirmed customer receipts must cover 50% of the effective
approved amount AND Super Admin must explicitly verify the funds. Refunds and
reconciliation holds remove eligibility. The existing explicit, audited Super
Admin scheduling arrangement remains the exception. Ordinary/future finance
permissions do not currently grant payment or deposit access.

## Attendance and privacy

Attendance unlocks after call-out approval, or quoted approval plus verified
funds/explicit authorised arrangement. It displays **Please confirm attendance
date** and **This job is ready for attendance arrangements.** The attendance
notification does not describe deposit allocation.

Both access-responsibility choices offer a preferred date or Request a Call.
The public windows are exactly 09:00–13:00 and 12:00–17:00. A request stays pending
until Operations confirms it; it is not an appointment. Alternative/rescheduled
or call-arranged dates require the backend-validated confirmation checkbox and
Tenant / PM / Other Authorised Contact category. Original requested date/window,
final agreed date/window, confirming user/time and decision history are retained.

Confirmation calls the existing private calendar service in the same transaction.
It checks service coverage, team, availability and overlaps; only Super Admin can
authorise the existing overlap exception with a reason. Public windows are saved
separately from actual internal start/end times. New-workflow customer calendars
project the agreed public window only; supplier/team identities and actual job
length are excluded. Direct old booking APIs cannot bypass confirmation for new
workflow jobs. Published cancellations create participant notifications.

Messages offer an agency/Operations audience, an explicitly tenant-shared audience,
and staff-only internal notes. Querysets, activity and file downloads enforce the
audience. Sharing does not grant access to commercial/private documents. Staff
must still review the contents of anything they intentionally share; the platform
cannot infer confidential names inside arbitrary prose/PDFs.

## Completion, agency invoices and private payments

Before a new final agency invoice, accept a saved completion report and after-work
photos. Before-work photos are required unless Super Admin explicitly records
unavailability and a reason; that actor/time is retained. Evidence uses the same
validated private file storage and authorised download paths. Work must be marked
Completed before the final agency PDF upload.

Invoices are external PDFs with manual references. Invoice purpose is immutable.
Keep deposit and final-balance documents consistent with the external accounting
records: total active agency invoices must not bill the authorised scope twice.
The platform does not automatically transfer a receipt between invoices, create a
credit note or decide external tax treatment. Use the existing audited void,
refund, correction and reconciliation process where externally issued documents
need correction; obtain accounting sign-off on the actual deposit/final documents.

Only Super Admin records agency receipts, verifies deposits or confirms supplier
payments. Closed is a real saved job status reached only after completion evidence
and full settlement of all active agency invoices, including a final invoice.
Supplier payments are independent. A later refund/void requiring reconciliation
reopens the job with an audit event; original closure/history is retained.

Private supplier invoice upload requires the relevant assigned subcontractor/job.
The invoice itself is the durable payable obligation in the existing finance
ledger; viewing it never creates a cash-payment entry. New supplier invoices are
due the next Monday strictly after upload, including a seven-day interval for a
Monday upload. Due classification comes from saved dates and net balances.
Payments provides Upcoming, Overdue, Paid and All views with supplier, agency/job,
due date, payment date, payment state, invoice state and amount filters. Actual
payment date/reference are required. No bank account, gateway or transfer is used.

## Notifications and local workers

Per-recipient, saved in-app notifications cover submission, issued quotations,
approval decisions, review, additional work, attendance eligibility/requests/
confirmation, selected comment audiences, completion, agency invoice upload and
closure. Read state is persistent. Unique event/recipient and action keys prevent
replay duplicates. Existing Operations inbox and email outbox remain separate
from recipient read state and email delivery success.

`send_operations_notifications --watch` also checks overdue private invoices,
recording deduplicated Super Admin alerts. For a one-off local check, use:

```text
python manage.py refresh_payment_alerts
```

Without a running worker/check, the finance screen still derives Overdue correctly,
but a new persisted overdue notification waits for the next check. Keep all actual
SMTP/SES delivery flags disabled. Local queue/previews are not proof of email
being delivered to a real mailbox.

## Migrations and historical compatibility

0028 adds workflow fields/decision, recipient notification, spending, deposit,
attendance and completion records; 0029 extends attachment purpose length; 0030
adds audience/category choices; 0031 adds the saved Closed status/constraint; 0032 adds positive-amount, pending-attendance, arrival-window and closure-timestamp database guards.
These are additive schema changes. They do not overwrite SQLite, delete media,
renumber existing jobs, populate fake approvals/payments, or infer completion
from old documents. Existing rows remain explicitly `workflow_version=0` with
legacy invoice purpose until reviewed. Their existing functionality/history is
retained. New reports use workflow version 1 and strict gates automatically.

A legacy request can be reviewed explicitly by its PM through Review and Route
Request to enter the strict workflow; this is a real new decision, not a migration
backfill. Existing approved legacy commercial documents, historical shared
appointments and legacy invoices require an Operations review/acceptance plan
before a controlled launch. Do not mass-update workflow flags or infer authorisation
from an old job status. Earlier numbering migration 0027 remains protected against
unsafe rollback on populated databases.

## Acceptance and remaining operational steps

Use separate Super Admin, PM, agency admin, tenant and other-agency browser profiles.
Test both Gauteng and Cape Town and each access-responsibility choice. Include:

1. PM login routing, Properties/Tenants buttons, 19 category icons, responsive
   navigation, stage counts and stage-to-job tabs.
2. Tenant safety flag versus PM urgency; PM reporting and another agency's denial.
3. Call-out approval, ceiling, declined increase and a separately quoted linked job.
4. PDF/manual references, PM/admin approval, concurrent/repeated decisions and SV.
5. Partial receipt, Super Admin verification, refund/hold and blocked attendance.
6. Preferred date and call request; alternative date without checkbox must fail;
   then confirm contact, team and actual private time. Verify only public windows
   reach the right PM/tenant calendars and inboxes.
7. Private versus shared comments and direct PDF/photo download attempts.
8. Missing after photos/report/before evidence; audited before-photo exception;
   final upload blocked until all evidence/work requirements are satisfied.
9. Final balance, real manual payment date, Closed history and refund/reopening.
10. Private supplier PDF, next-Monday obligation, partial payments, overdue worker
    notification, Paid/All filters and denial for the future finance account.

Actual Windows acceptance, real mailbox setup/approval and production security/
infrastructure acceptance remain manual. Existing scanner/quarantine, MFA,
private-storage, backup/restore and launch-readiness requirements still apply.
No production infrastructure or live service is activated by this work.
