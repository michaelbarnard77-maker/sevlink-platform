# Step 8.5 — private subcontractor management

This extends Step 8's existing directory, geography, coverage and assignment
models. It does not replace them or import the original browser-demo suppliers.
No real contacts, rates, bank accounts, coverage or availability are seeded.
All changes belong to `development/phase-1-foundations`; no merge or deployment.

## Working Django features

**Profiles and discovery.** Operations can register a company using the existing
Add subcontractor form, then open Profile & teams to maintain trading/company
name, contact person, telephone, WhatsApp, email, trades, specialisations and
internal notes. Active/inactive/archived status preserves historical records.
Archived and inactive suppliers cannot receive new assignments. Profile saves
use optimistic versions. Search supports name/contact/email/specialisation;
filters support trade, status and existing province/city/suburb coverage.
All nine provinces remain supported, including Gauteng and Cape Town together.
Existing service-area records and historical assignment IDs remain unchanged.

**Commercial agreements.** Commission percentages and negotiated ZAR rates
(hour/visit/fixed) with private agreement terms are append-only, timestamped and
attributed to the acting user. New terms preserve older agreements. Decimal
validation rejects negative rates, fractional cents and commissions outside
0–100%. Submission keys prevent duplicate retries. There is no automatic
commission calculation, payroll, payout, quotation calculation or generated PDF.

**Finance restriction.** Bank name, account holder/number, branch code and account
type use a separate model and endpoint, never the directory/profile/job payloads.
An active Operations Super Admin must additionally receive an **explicit**
`portal.manage_subcontractor_finance` user or group permission. Superuser's normal
implicit permission bypass intentionally does not grant this access. Ordinary
Operations accounts see a restricted notice, including in the API. Authorised
reads and changes are audited without copying bank values to audit payloads.
Bank updates require the current bank version; account values are fetched only
when the authorised user opens the restricted bank panel.

After development migrations, provision a designated finance Operations account:

```sh
python manage.py subcontractor_finance_access --email FINANCE_ACCOUNT_EMAIL
python manage.py subcontractor_finance_access --email FINANCE_ACCOUNT_EMAIL --revoke
```

Group grants are managed separately; removing a direct grant does not remove a
group grant. Existing Operations authorization remains Super Admin only; this
slice does not introduce a separate, less-privileged general Operations role.
No grant is automatic and no finance account or credentials are created.

**Compliance PDFs.** CIPC, public liability insurance, qualifications/certificates
and other compliance PDFs use the existing named private storage alias, bounded
5 MB upload validation and conservative PDF safety checks. Keys are server UUIDs
under `subcontractors/<supplier UUID>/<document UUID>.pdf`; no public URLs exist.
Downloads require Operations authorization, use attachment delivery, no-store,
sandbox and nosniff headers, and are audited. Wrong-parent URLs return 404.
Upload retries deduplicate; failed database/storage saves clean newly saved
files. PDFs/metadata cannot be silently edited or deleted through these APIs.
Upload a replacement of the same type, preserving the original PDF/history.

Expiry dates are optional for documents with no relevant expiry. Operations sees
expired and next-30-day alerts in Service areas, with profile links. Today and
30 days ahead are due soon; dates before today are expired. Superseded documents
remain accessible in history but do not generate current alerts. These are
**in-app reminders**, computed from saved records; no reminder email is sent.
An expiry date is not verification of document authenticity or compliance.
Missing documents and documents without dates are not claimed to be compliant.

**Teams and availability.** Suppliers can have multiple named teams, each active
or inactive, with its own working weekdays, 09:00–17:00 working window, unavailable
dates and job assignments. No working days are assumed: Operations confirms them.
Working times and appointments use Africa/Johannesburg. Team changes use versions.
Unavailable-date changes and appointment cancellations retain a supplier audit.

When a supplier has registered teams, a new assignment requires an active team
belonging to that supplier. Existing assignments keep a nullable team and appear
as Legacy / team unallocated; creating teams never invents historical allocations.
Suppliers without teams retain the existing allocation workflow, but cannot have
team appointments until explicitly allocated to a team. Reassigning to Team A or
Team B adds a new immutable allocation instead of editing the earlier record.

Appointment start/end times are saved backend records, not a calendar. They must
be timezone-aware, within one working day and the team's confirmed hours, and
avoid unavailable dates and overlapping active appointments for that team.
Different teams may work at the same time. Parent/team locks protect concurrent
bookings on PostgreSQL. Duplicate retries of the same active appointment return
the saved record. Cancel with a reason before rescheduling; original appointments
remain in history. Availability edits that conflict with future appointments are
rejected; reassignment with an active future appointment requires cancelling or
rescheduling it first. Job status is never changed by these operations.

**Assignment compatibility.** Changes through the location/coverage/profile/team
management APIs flag affected current, open-job allocations for Operations
review (property location, coverage/active status or team deactivation). Original
allocation records, location snapshots and history remain intact. No silent
reassignment or deletion occurs. Reviews and their attributed resolutions are
append-only. A manual acknowledgement does not override coverage/active-status
checks for future appointments. New appointments reject pending reviews, stale
allocations and closed jobs. Direct database edits bypass business APIs and must
not be used as a substitute for these management workflows.

## Access and audit

Every new endpoint uses existing session authentication and CSRF protection,
requires active Sevlink Super Admin access, and sets no-cache responses. Plain
staff, agency admins, PMs, tenants, private client accounts and other agencies
cannot access profiles, teams, commercial agreements, documents or appointments.
External maintenance APIs continue to use allowlisted payloads, excluding supplier
identities, notes, rates, bank details and assignment events. SupplierActivity
records changes/access with user/time/action; bank values are not in its details.
The original portal demo remains browser-local and simulated. The Service areas
screen and its new forms use Django; original website/assets/layout are preserved.

## Development setup and manual acceptance

1. Back up the development database/files, then run `python manage.py migrate`.
   Migrations 0016–0017 add fields/models and seed only the 19 trade labels already
   used by maintenance reporting. Existing active flags, locations, assignments,
   historical quotes, invoices, payments and refunds are preserved. Migration
   regressions restore the latest schema. Do not reverse new schema after entering
   supplier data without a backup: reversing schema removes those new records.
2. Sign in as Super Admin, open Service areas, create a synthetic subcontractor
   with Gauteng and Cape Town coverage, and complete Profile & teams. Search by
   contact/email and filter by trade/status/location. Confirm archived suppliers
   stay in history and are excluded from new assignment candidates.
3. Upload synthetic PDFs of each document type. Try an unsafe/non-PDF and a file
   larger than 5 MB. Set expiry yesterday, today, +30 and +31 days; confirm alerts.
   Upload a replacement and verify the original remains downloadable.
4. Create Team A and Team B with confirmed weekdays. Assign different jobs to each
   team. Confirm legacy assignments remain unallocated until explicitly assigned.
   Enter overlapping times: same team must reject, different teams must succeed.
   Try unavailable/nonworking dates, before 09:00, after 17:00 and backwards times.
   Cancel/reschedule and verify old appointment history remains.
5. Change a property's location or supplier coverage after assignment. Confirm
   review flags appear without deleting/reassigning anything. Resolve with an
   explanation; check the activity/history and continued eligibility enforcement.
6. An Operations account without an explicit finance grant must get HTTP 403 from
   the bank endpoint. Grant finance access, save synthetic details, refresh and
   verify persistence and stale-version rejection. Revoke access and verify 403.
   Profile/directory/job JSON must never contain bank values, even for finance.
7. Sign in as PM, tenant, another agency and ordinary staff. Private API/document
   URLs must fail. Inspect external job JSON for absence of names, internal notes,
   agreements, supplier documents, team IDs and financial fields.
8. Complete owner acceptance testing using synthetic data before any launch.

## Remaining work / production gates

- The full 09:00–17:00 weekly calendar, drag/drop, travel routing, contractor login,
  appointment acceptance, dispatch and automated scheduling are intentionally
  not built. WhatsApp/phone/email are contact fields, not messaging integrations.
- No outbound email is activated. Existing job-event notifications remain intact;
  compliance expiry reminders currently live in Operations, without background
  email or external reminders. SMTP/SES configuration and explicit activation
  still require separate approval.
- No bank verification, payment gateway, supplier payouts, automatic commission
  accounting, generated quotations/invoices or automatic compliance approval.
- Malware scanning/quarantine, file retention, encrypted production database/file
  volumes, backup/restore verification, privileged MFA and detailed staff role
  separation remain production safeguards. Bank values are access-controlled in
  Django but not application-encrypted; configure storage/database encryption and
  restricted backup access before entering real financial details in production.
- Profile histories currently return the latest 100 assignments/activity entries,
  and each team the latest 100 appointments; full database history is retained.
  Dashboard alerts show the earliest 50 due documents and latest 100 pending
  reviews. Larger datasets need explicit history/catalogue pagination and search.
- No real supplier data or availability was entered; manual onboarding, suburb
  entries, property mapping and owner end-to-end acceptance remain necessary.

Automated tests cover profile/finance privacy, secure documents and expiry,
team compatibility, availability/overlap/cancellation, review flags, preservation
migrations, PostgreSQL concurrency and Chromium Operations controls. Final full
suite counts and CI links are recorded on draft PR #1; nothing is merged/deployed.

## Browser verification environment

`SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh` creates a temporary, file-backed
SQLite test database and removes its directory on exit. The setting
`SEVLINK_SQLITE_TEST_DATABASE` affects Django's test database only. This avoids
LiveServer's shared in-memory connection across concurrent notification,
dashboard and form requests. PostgreSQL CI remains unchanged. Browser tests wait
for the saved profile version and explicitly fail on unhandled server exceptions;
no HTTP/authentication errors are ignored or retried to make a test pass.
