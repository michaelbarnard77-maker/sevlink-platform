# Property manager dashboard, accounts and customer calendar

Development branch only; no merge, deployment, live email or paid service.
The original static demo remains separate. All new authenticated screens use
Django records, existing sessions/CSRF and scoped agency/property permissions.

## Navigation and attention

PM/agency users: Overview, Repair Jobs, Properties, Tenants, Quotations,
Accounts & Payments, Maintenance Calendar, Updates & Notifications, Agency Profile,
Report Website Issue. Tenants: Overview, My Repairs, Report a Repair, My Property,
Maintenance Calendar, Updates & Notifications, Report Website Issue. Responsive
navigation reuses existing branding; no demo role switch or browser-local records.
Properties/account-management links reuse the existing Django forms and account
lifecycle rather than creating another property backend.

Needs Your Attention is derived across the authorised portfolio, not just the
first repair-list page. It prioritises explicitly recorded urgent/safety concerns,
overdue invoices, sent/revised quotation decisions, deposits/scheduling, shared
appointments and explicit customer-information requests. One key identifies each
underlying action. Review/decision/payment/resolution removes the corresponding
alert. Changes refresh on navigation, modal close, explicit refresh and a one-minute
refresh while a relevant page is visible and no modal is open. It is not push/live
WebSocket delivery.

Urgency is a saved field, not keyword guessing. PMs/Operations can update it.
Operations can create a safe customer-facing action request for the PM or reporting
tenant, with an optional due date. Only its intended audience or Super Admin can
resolve it. Duplicate unresolved requests coalesce. Each action retains its author,
creation time and resolution user/time; changes are audited. Shared comments and
existing quotation decisions still use their existing notification/activity flow.

A quotation already marked Revision Requested is awaiting Sevlink's replacement,
not another PM decision. A newly sent revision/amendment creates the next decision
item. Historical approvals/PDFs and externally printed references are untouched.

## Customer accounts and the 50% rule

Only customer-visible Sevlink invoices are projected; supplier-linked and internal
invoices are excluded by server queries. Filters include unpaid, deposit received,
partially paid, paid, overdue and void/credit-document records. Totals reflect the
selected filter. Each record links to its job and original protected invoice PDF.
Only authorised Sevlink users can record payments using the existing ledger.
An agency claim, browser action or uploaded receipt does not credit a payment.

Scheduling deposit basis is the sum of effective approved quotation amounts,
excluding approvals replaced by an approved amendment. If there is no approved
quotation, use active customer invoice totals. Required cash is 50%, rounded UP
to a cent. Received cash is confirmed payments minus recorded refunds on active
customer invoices. Internal supplier invoices never contribute. Reconciliation
holds block ordinary readiness. Original financial records are not rewritten.

The deposit filter uses the JOB deposit basis, not half of a smaller deposit-only
invoice. Therefore a fully paid deposit-only invoice may appear in both the paid
and deposit filters: it is paid as a document while covering 50% of the job. Invoice
outstanding balances remain document balances; unissued future invoices are not
invented. Credit-note uploads do not silently create cash receipts or rewrite
accounting balances; existing void/correction/reconciliation controls remain.

New appointments/reschedules and publishing Scheduled status require confirmed
50% cash or a reasoned Super Admin-authorised agreed scheduling arrangement.
An arrangement is a job-level permission to schedule under agreed payment terms,
not money received; it is stored append-only and its reason stays private.
Existing appointments remain intact; no automatic cancellations, bank transfers,
receipt matching or invoice/PDF generation occur. Operations must review changed
scope/refunds/payment arrangements and separately cancel obsolete appointments.

## Customer appointment privacy

Existing appointment rows remain PRIVATE after migration. Staff explicitly check
**Share confirmed appointment dates and times** on booking/rescheduling, or Super
Admin explicitly publishes an existing appointment via the protected backend.
Sharing reveals only that job's property, issue, reference, public status and
appointment dates/times/state. It reveals no supplier/team identity, other jobs,
working days, unavailable dates, internal notes, reasons, costs or override details.

PMs see their assigned portfolio; agency administrators their own agency. A tenant
needs both an active property tenancy and ownership of that maintenance request.
Co-tenants do not gain access to somebody else's repair appointment. Customer
calendars navigate Monday–Sunday in South African time. Cancelled/rescheduled
records remain in history. A replacement suppresses duplicate old cancellation
alerts. Mark reviewed/read is persistent per user and never changes the job status.
Shared appointment changes also appear in Updates & Notifications (latest 200).
The private team/Operations calendar and Monday supplier ledger remain staff-only.

## Website reports

Report Website Issue creates a private persistent report with reporter, agency,
subject, description, status and timestamp. Reporters see their own reports;
Super Admin has a private Website Issues listing. Reports never create/change a
maintenance job. No live delivery or automatic support response is claimed.

## Numbering and migration

0027 supersedes 0025's request-time SV allocation. Requests receive REQ-0001;
only authorised quotation approval issues an official global SV-0001. Manual PDF
quotation/invoice references are required; no new SQ/SI identifiers are generated.
Existing UUIDs, PDFs, decisions and financial history remain. Premature SV numbers
become reserved historical aliases rather than official numbers. See
[the numbering correction](NUMBERING-CORRECTION.md) for migration and duplicate
reference handling. Stop writers and back up before upgrading.

## Verification and local update

Tests cover portfolio/agency isolation, decision removal, payment and refund
balances, approved-amount versus deposit-invoice handling, priority, action roles,
private supplier exclusion, explicit appointment publication, cancellation review,
co-tenant denial, website reports, PostgreSQL numbering concurrency and browser
navigation/mobile/PDF/approval flows. PostgreSQL CI also runs browser workflows
and normal test-database cleanup/recovery checks. No new live infrastructure has
been verified. Owner manual acceptance remains necessary.

See [safe Windows update steps](WINDOWS-PM-DASHBOARD-UPDATE.md). Production MFA,
scanning, real email configuration, backups/retention and owner/accounting approval
remain governed by the existing controlled-launch readiness plan.
