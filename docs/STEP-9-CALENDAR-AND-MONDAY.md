# Step 9 — weekly scheduling and Monday Payments Due

All work is on `development/phase-1-foundations`. Nothing is merged, deployed,
connected to banking or activated for live email. Existing website/demo assets
are unchanged. The authenticated portal reuses the current shell, branding and
styles, with calendar-specific responsive styles.

## Staff access

Active Sevlink Super Admins have both capabilities. For delegated staff, use
Django's user/group permissions:

- `portal.operate_schedule`: private weekly calendar, job selection, assignments,
  appointments, private appointment history and manual public progress updates.
- `portal.manage_supplier_payments`: Monday invoice review, private supplier
  invoice PDFs and the existing manual payment recording endpoint.

A delegated account must be active, have `is_staff=True` and have **no agency
Membership**. A staff flag alone grants nothing. Agency administrators, PMs,
tenants and private clients cannot access these screens/APIs, even if accidentally
assigned one of these permissions. Only Super Admin may authorise overlaps.
Permissions are provisioned through the trusted existing Django auth process;
this change adds no public role-grant endpoint. Example in `python manage.py shell`:

```python
from django.contrib.auth.models import Permission
from portal.models import User
operator = User.objects.get(email='EXISTING_STAFF_ACCOUNT_EMAIL')
# Verify the intended account and absence of an agency Membership first.
operator.is_staff = True
operator.save(update_fields=['is_staff'])
operator.user_permissions.add(Permission.objects.get(
    content_type__app_label='portal', content_type__model='user',
    codename='operate_schedule'))
# For an independently authorised finance account use manage_supplier_payments.
```

The delegated roles do not grant full supplier profile/commission/document
administration or unrestricted agency workspaces. The finance capability does
not grant scheduling. Scheduling does not grant supplier finance. Existing Super
Admin controls continue to manage profiles, rates, coverage and team availability.
Use separate synthetic test accounts for acceptance; no new real users are seeded.

## Weekly calendar

Open **Weekly calendar** in `/maintenance/`. The Django-backed calendar displays
Monday–Sunday with one row per subcontractor team. Each day runs 09:00–17:00,
Africa/Johannesburg. Booking position and width derive from actual start/end
intervals over 480 minutes: 09:00–12:00 = 37.5%; 12:00–14:00 starts at 37.5% and
occupies 25%. Adjacent bookings reuse the same lane; authorised overlapping
exceptions stack on separate lanes and are outlined. Cards show times, job
reference, property and public status as space allows, with complete details on
opening. Mobile displays one selected day at a time with the same proportions.

Previous/next week navigation normalises to Monday. Filters support province
(including Gauteng), city (including Cape Town), trade, subcontractor and team.
Coverage filtering controls which team rows qualify; location filtering also
applies to booking properties. Conflict checks always consider **all** appointments
for the team, including bookings hidden by the current filter.

Use **Schedule a job**, or an empty day cell, to choose an existing open job,
subcontractor/team, date and start/end. Job search returns up to 100 results; use
search for older records. Team rows without bookings are real saved availability,
not invented demo schedules. No team is created or assigned automatically for a
historical unallocated record.

Opening a booking shows details, its maintenance job and appointment history.
**Reschedule / reassign** requires a reason. It reuses the existing assignment and
appointment transaction services, cancels the original appointment with its
reason, optionally creates a new allocation, and saves a linked replacement.
The complete change is one transaction: a failed replacement restores the old
appointment/allocation. **Cancel appointment** preserves the original times,
actor/history and cancellation reason. Submission UUIDs and payload fingerprints
protect retries and conflicting key reuse. Multiple different jobs may occupy
one team's day, but the existing one-active-appointment-per-allocation rule remains.

Working weekdays, configured hours, unavailable dates, active team/parent, mapped
service-area coverage, closed jobs and pending assignment reviews are enforced on
the server. An ordinary scheduler cannot force a conflict. A Super Admin can
supply an explicit reason for a same-team **overlap only**; this does not bypass
working days, unavailable dates, coverage or closed-job rules. AppointmentOverride
records the reason, responsible user, timestamp and conflicting appointment IDs;
records are append-only. The team row lock protects concurrent checks/writes on
PostgreSQL. Property/job/vendor locks keep assignments and reschedules consistent.

## Public job progress

Calendar job details expose a manual public progress control. Existing review and
in-progress transitions remain, with Operations-only Scheduled, On Site and
Attended states, followed by Completed or Cancelled. A newly reported job still
requires review before scheduling progress is published. Saving an appointment
does **not** silently publish Scheduled, and publishing Cancelled/Completed does
not silently rewrite appointment history: cancel appointment records separately
where needed. Closed jobs cannot acquire new appointments.

The existing MaintenanceRequest status/version, MaintenanceStatusEvent and
JobActivity/outbox are reused. Agency/tenant APIs show authorised public status
and timestamped history on refresh/relogin. They never receive private calendar
entries, times, supplier/team identity, override reasons, rates, commissions or
supplier invoice/payment records. Staff actor names are shown externally as
Sevlink Operations. Existing completion/cancellation Operations notification
triggers still queue locally; private appointment events are not external emails.

## Monday Payments Due

This is a private view of existing supplier-linked invoice PDFs and immutable
manual payment/refund records. It shows company, external invoice number, linked
job reference, ZAR amount, net paid, outstanding, due date, status and private PDF.
Overdue and reconciliation-hold records are highlighted. Totals are calculated
across the **whole filtered result**, before 50-row pagination.

Default filtering includes active outstanding supplier invoices due **on or before
the upcoming Monday**. If today is Monday, the cutoff is today. Other filters show
all outstanding or overdue invoices, optionally for one subcontractor. Overdue
means due before today; invoices due today are not yet overdue. Displayed totals
cover the selected filter. Net balance is amount minus payments plus recorded
refunds; void and fully paid invoices do not contribute. Holds remain visible as
obligations requiring manual attention but cannot accept new payment records.

Record a payment only after making it externally, using the existing manual
payment form: amount, date and nonempty external reference. Partial/full status,
net paid and balance update from actual saved ledger entries. Reopening or viewing
on Monday never creates a payment or changes payment status. Stale versions,
duplicates, excess amounts, future dates, voids and holds retain their existing
protections. Delegated finance can read the supplier PDF and record a supplier
payment, but cannot use these permissions to read agency invoices or bank data.

No bank accounts, gateway, bank API, automatic transfers, automatic paid-on-Monday
process, generated PDFs, automatic commissions or tax documents are introduced.
The [external banking requirement](SUPPLIER-PAYMENTS.md), including guarded legacy
bank removal, remains in force. Original unlinked historical invoices remain in
the job workspace; no supplier attribution is invented to put them in this view.

## Migrations and APIs

Run development migrations before serving the branch. Migration 0019 adds three
status choices and updates their database check, appointment submission/replacement
metadata, append-only overlap records, an internal event choice and the two staff
permissions. Existing statuses, appointments, invoices and bank-removal safeguards
are preserved. No business records are seeded or reclassified. Upgrade regression
tests restore 0019. Do not reverse schema after recording new statuses/overrides
without a reviewed backup/data migration: an older status check cannot accept the
new states, and reversal would remove new metadata.

All new endpoints use authenticated, active staff authorization, no-store caching
and existing Django CSRF on writes:

- `GET /api/maintenance/operations/calendar/` — week, filters, team/booking data.
- `POST .../calendar/save/` — schedule, atomic reschedule/reassignment or cancel.
- `GET .../calendar/jobs/<id>/` — private job summary and appointment history.
- `POST .../calendar/jobs/<id>/progress/` — manual public status with current version.
- `GET /api/maintenance/operations/monday-payments/` — filters, totals and invoices.

Existing supplier invoice PDF/manual-payment endpoints are extended only for the
explicit finance capability and supplier-linked private records. No separate
scheduling backend, financial ledger or assignment model is created.

## Manual acceptance

1. Use separate Super Admin, delegated scheduler, delegated finance, ordinary
   staff, PM, tenant and another-agency accounts. Test role grants/revocation.
2. Set real synthetic teams/coverage and confirmed working days in Service areas.
   Verify Gauteng and Cape Town filters independently and together.
3. Navigate weeks and check Monday–Sunday. Schedule Team A at 09:00–12:00 and
   12:00–14:00 on different jobs: widths must be 3/8 and 2/8 of a day. Check times,
   property/status labels, narrow cards and the mobile day picker.
4. Try an overlap, unavailable/nonworking date, inactive team and another team's
   simultaneous slot. Ordinary staff must be blocked from overlap overrides;
   Super Admin must provide a reason, with a permanent audit and stacked cards.
5. Reschedule/reassign with a reason; confirm history and cancelled original.
   Attempt an invalid replacement and verify the original remains active. Race
   two tabs with the same job/appointment version; only one should replace it.
6. Manually review and move a job through Scheduled → On Site → Attended →
   Completed, and cancel another job. Refresh the authorised PM/tenant portal:
   status/history must update without any supplier/schedule/finance data.
7. Upload private supplier invoice PDFs due yesterday, Monday and after Monday.
   Confirm cutoff, totals, overdue highlighting and supplier filtering. Record a
   partial external payment, then a full balance payment; history/balances must
   persist. Refresh on Monday: no automatic payment or status change may occur.
8. Verify scheduler-only users cannot read supplier payments; finance-only users
   cannot access the calendar; agency/tenant/private/ordinary-staff users cannot
   access either API or download supplier documents. Forge request fields too.
9. Finish owner acceptance with synthetic data before considering any merge.

## Remaining scope / safeguards

This is manual scheduling and payment tracking. Drag-and-drop, recurring/multi-visit
active allocations, travel/routing, contractor login/acceptance, external calendar
sync, automatic dispatch, SMS/WhatsApp and real-time push updates are not built.
Public views refresh through the existing API; they do not use WebSockets.
Calendar team data is not virtualised/paginated; larger deployments need performance
and load verification. Existing malware scanning/retention, MFA, backups/restore,
production encryption and infrastructure safeguards remain pre-launch work.
Live email remains disabled and no paid services are activated.

Automated checks cover calendar navigation/proportions, multi-job/team conflicts,
override permissions/audits, atomic rescheduling and cancellation, public status
privacy, Monday filtering/totals/partial payments, finance/PDF access boundaries,
PostgreSQL concurrent scheduling and normal database cleanup, plus the original
Django/demo/browser/financial/migration regressions. Results and CI links are on
draft PR #1; no merge or deployment is performed.
