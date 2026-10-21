# Step 8: private subcontractor management — regional requirements

Sevlink supports Gauteng and Cape Town, Western Cape from the first release.
There is no Gauteng-only eligibility rule. All nine South African provinces are
seeded; cities and suburbs are database records, not a regional allowlist in code.
Operations manages both launch regions in one authenticated `/maintenance/`
workspace under **Service areas**. The existing shell, branding and styles are
reused; the original browser demo remains unchanged and simulated.

## Implemented regional foundation

- Province → city → suburb hierarchy with protected references and case-insensitive
  unique city names per province and suburb names per city. Initial cities include
  Cape Town, Johannesburg, Pretoria, Meyerton, Vanderbijlpark, Heidelberg and Nigel.
  Operations can add cities and suburbs in the dashboard. Add further provinces as
  Province records if needed; eligibility code has no province names or codes.
- Existing property address strings and agency area strings are preserved. New
  city/suburb links are nullable. No address parsing, geocoding or silent Gauteng
  defaults: Operations maps each property explicitly. Suburbs must belong to the
  selected city. Existing property reporting and financial workflows remain usable
  before a property is mapped; only new regional assignments require a city.
- A private subcontractor may cover multiple provinces, cities and/or suburbs,
  including Gauteng and Cape Town simultaneously. Province coverage includes its
  cities/suburbs; city coverage includes its suburbs. Suburb-only coverage never
  implies city-wide coverage. A property with no known suburb matches only
  province-wide or city-wide coverage. Inactive subcontractors cannot be assigned.
- The Service areas dashboard filters subcontractors, properties and jobs by
  province, city or suburb. Lists paginate 50 records of each type per page.
  Subcontractor filters show any overlap with the selected location; actual job
  candidates require coverage of the specific mapped property.
- Private assignment dialogs list eligible active subcontractors. The server
  rechecks coverage at submission. Completed/cancelled jobs reject assignments.
  Job version checks, a job row lock and a unique submission key protect against
  stale/concurrent writes and duplicate retries. Reassignment preserves all prior
  assignment records, with user, time and a snapshot of city/suburb references.
  The latest record is the latest allocation; it is not scheduling or acceptance.
- Assignments add an internal-only permanent job activity. All new directory,
  location-management, candidate and assignment endpoints require active Sevlink
  Super Admin access, consistent with existing Operations authorization. Plain
  `is_staff`, agency administrators, PMs and tenants cannot use them. External
  request/detail APIs do not include subcontractors or assignment events.

## Operations verification

1. Sign in with a Super Admin account and open **Service areas**.
2. Select Gauteng, then Western Cape → Cape Town. Confirm that properties/jobs
   change and that clearing filters shows both regions together.
3. Add any required suburbs. Map a Gauteng property and a Cape Town property,
   checking that the existing address text is unchanged.
4. Add a subcontractor covering Johannesburg and Cape Town. Confirm it appears
   for both properties; a Gauteng-only contractor must not appear for Cape Town.
5. Add a Sea Point-only contractor: it must match Sea Point, not Gardens or a
   Cape Town property without a mapped suburb. Deactivate it and check exclusion.
6. Open **Private assignment** on a job and record an assignment. Refresh and
   confirm history persists. In two tabs submit the same old job version: only
   one new assignment should succeed. Retry the identical submission key: no new
   assignment or activity should be created.
7. Sign in separately as PM, tenant and another agency's administrator. Confirm
   there is no Service areas navigation and private APIs return 403. Inspect job
   JSON: no subcontractor identity or private assignment history should appear.
8. Add a city/suburb in another province and repeat the same coverage workflow.

## API and migrations

Operations-only endpoints, using existing session authentication and CSRF:

- `GET/POST /api/maintenance/operations/regions/` (catalogue and filtered dashboard;
  GET parameters `province`, `city`, `suburb`, `page`; POST creates city/suburb).
- `POST /api/maintenance/operations/subcontractors/` creates/updates coverage.
- `POST /api/maintenance/operations/properties/<id>/location/` maps a property.
- `GET/POST /api/maintenance/operations/requests/<id>/assignments/` lists candidates
  and private history / records an assignment with `version`, `subcontractor` and
  UUID `submission_key`.

Run `python manage.py migrate` before serving the development branch. Migration
0014 adds nullable property location fields and new private directory/assignment
models; 0015 seeds geographic reference records without modifying historical
business records. Seed reversal intentionally preserves reference rows until
schema reversal; do not reverse the new schema after recording assignments
without a backup. Upgrade-preservation tests restore the new migration head.

## Scope and remaining Step 8 work

This completes regional coverage/filtering/private allocation, not the entire
subcontractor product. Trade qualification, contacts/onboarding, availability,
travel distances, appointment booking, contractor acceptance, contractor login,
compliance documents and supplier accounting integration are not implemented by
this slice. Location coverage is eligibility, not proof of availability or trade
suitability. No original demo subcontractors are imported automatically. Legacy
properties require manual mapping and the initial suburb catalogue is empty.
A later property remap/coverage edit does not rewrite prior allocations or their
location snapshots; Operations must review/reassign affected open jobs manually.
Current regional catalogue selectors load all cities/suburbs; search/pagination
of the catalogue itself may be needed as reference data grows. No outbound email,
AWS service, deployment or merge is introduced.

Automated coverage includes multi-area matching, exact suburb boundaries,
invalid hierarchy rejection, inactive/out-of-area/closed-job assignment denial,
CSRF, role and cross-agency isolation, immutable assignment history, idempotency,
stale writes, PostgreSQL concurrent writes, additive migration preservation and
Chromium filtering/registration/assignment/PM-isolation checks. Full suite
results and CI links are recorded in draft PR #1.
