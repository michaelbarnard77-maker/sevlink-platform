# Phase 1 inspection

Branch: `development/phase-1-foundations`. Baseline: `63d784f`.

## Existing foundations

- Django custom User extends AbstractUser. Email is unique, including a case-insensitive database constraint. Login normalizes email and authenticates using the username populated from email at registration.
- Agency, Membership, Property and Tenancy provide the existing organizational structure. Membership allows one agency per account. Properties have an optional assigned PM; active tenancies link tenant users to properties.
- Invitation stores hashed 48-hour tokens, expiry, revocation and acceptance state. Registration creates an inactive administrator; verification activates it. PM and tenant invitations set passwords through Django forms.
- Django sessions, CSRF middleware, password validation and password resets are already implemented. Mail is queued in MailQueue; actual SMTP delivery is separately gated.
- Audit records account/property operations. RateBucket implements database-backed throttling.

## Current permission boundaries

- Administrators manage their agency's properties and invite PMs.
- PMs can manage only properties assigned to them. Property form manager choices are restricted to active PMs in the same agency; PM-created properties are assigned server-side.
- Tenants see properties through active tenancy, with cotenant information and private access notes excluded from their dashboard.
- Staff without agency membership receive a basic global summary. There is no explicit operational staff workflow or permissions model for repair processing yet.
- New workflows must authorize every read and mutation server-side. Never accept agency, reporter, role or state transitions from browser-controlled values without validation.
- Existing property permissions are implemented in view helpers, not automatically enforced on all ORM writes. New workflow services need explicit checks and transactions.
- `properties_for` currently treats every non-admin/non-PM role as a tenant; future permission helpers should fail closed for unrecognized roles rather than extending this fallback.
- IP throttles rely on REMOTE_ADDR; reverse-proxy handling needs staging validation. One-agency membership is an intentional first-stage limitation.

## Frontend integration

The existing static portal is not authenticated against Django. It stores records in IndexedDB and uses role selectors to simulate access. Scripts share globals and extend earlier functions, making load order significant. The only fetch identified is the local logo asset. The public enquiry form creates email/WhatsApp drafts.

Django has separate server-rendered onboarding/dashboard templates and stylesheet. There are no backend repair, quote, payment or appointment models/API routes. Existing static UI and demo records must not be silently migrated or treated as authenticated business data.

## Implemented first workflow

The user confirmed tenant maintenance submission, authorized PM status review, tenant status visibility, global Sevlink Super Admin visibility and strict data isolation. This scope is implemented on the development branch. See PHASE-1-WORKFLOW.md for endpoints, operation and verification.

Implementation boundaries:

1. Add one repair report model linked to property and reporting tenant, with bounded fields, timestamps and explicit review status; create a migration without modifying existing migrations.
2. Tenant submits only for an active tenancy. Agency administrators and assigned PMs can read/review reports for their permitted portfolio. Tenants see only their own reports. Only explicit Django superusers can view all reports across agencies, including pending review; ordinary staff do not qualify.
3. Provide an authenticated Django submission, list/detail and POST-only review path, reusing existing session/CSRF protection, styling and audit records. Keep the browser-local demo intact. The authenticated /maintenance/ adapter reuses the original portal shell/CSS without executing browser-demo scripts.
4. Test complete submission/review, invalid fields, anonymous/inactive/nonmember access, cross-agency and cross-PM attempts, cotenant isolation, forged ownership/status, CSRF, forbidden methods and invalid/repeated transitions.

Attachments, financial workflows and operational dispatch would need their own complete permission and state-transition design. Do not introduce them incidentally into the first slice.

## Constraints

No changes to main, production deployment, paid infrastructure, website design or demo behavior. Baseline checks: both supplied Node suites, JavaScript syntax, Django system checks, migration drift and all six existing Django tests.
