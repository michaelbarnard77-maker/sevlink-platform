# Published Sevlink demo compared with authenticated Django

Verified 28 October 2026. The Sites connection identifies the owner's URL
`https://sevlink-maintenance-demo.ableisle4.chatgpt.site/` as published version 42,
source commit `58a0777f69869461272cec00028dc0d51e27f57b`.
Read-only authenticated HTTP retrieval compared all **30** served HTML, JavaScript,
CSS and logo files against `portal/dist/`: every file matches byte for byte.
[File-by-file SHA-256 evidence](DEMO-SOURCE-HASHES.json) records this comparison.
There are no missing or outdated served demo files in the repository. The hosted
source, audience and deployment were not changed.

The earlier sign-in/401 limitation was resolved through authorised Sites access.
The source rather than an inferred recreation is now verified against the hosted
publication. The owner's invoice screenshots agree with `agency-finance.js`,
`deposit-workflow.js`, `single-invoice.js` and `professional-polish.js` in that set.

## Implementation and reference map

| Area | Exact source reused | Connection to real records |
| --- | --- | --- |
| Navy sidebar, logo, typography, buttons, modal | `index.html`, `features.css`, `mobile.css`, `professional-polish.css` | Original HTML/CSS shell; permitted role links, real identity and sign-out replace demo account switching |
| Operations dashboard | `operations.js` `.stats`, `.ops-pods`, `.ops-pod`, `.job-card` structures | Existing scoped workflow summary/stage API; saved jobs and authorised actions |
| PM overview | `team.js` attention semantics and original panel/card styles | Existing approved eight-card dashboard and portfolio attention projection retained |
| Repair Job Register | `repair-register.js` filter grid, bucket buttons and property-first table | Existing permission-scoped server search, filtering, pagination and REQ/SV references |
| Job header and panels | `professional-polish.js`, original `.job-property-address`, `.job-repair-title`, `.professional-next-step`, `.notice` | Saved property, agency, PM, report and current workflow; original report is a disclosure |
| Six core job tabs | `app.js` and `features.js` original `.tabs`, panels and report classes | Comments, Attendance, Quotes, Invoices, Timeline, Before & After Report use existing APIs |
| Invoice cards | `agency-finance.js` `renderInvoices` toolbar, amount, received/outstanding rows and actions | Saved original PDF, document status, verified manual receipts, refunds and true balance |
| Deposit/balance information | `deposit-workflow.js`, `single-invoice.js` notice structure | Authoritative `deposit_state` returned only to permitted non-tenant users |
| Email preview | `professional-polish.js` document header/property/totals structure | Authorised saved invoice/job values; clearly preview-only; no sending or queue changes |
| Completion report | `features.js`, `professional-polish.js` `.sevlink-document`, `.document-property`, `.photo-pair` | Private authorised downloads and accepted saved completion evidence |

The Django workspace reads the real `portal/dist/index.html` with UTF-8 and retains
its original CSS links. It strips all demo scripts and sample identities, then
loads `maintenance.js` and `workflow-ui.js`. No demo `localStorage`, IndexedDB,
mutable sample data or simulated operational actions are used in the real portal.
Original demo files remain unchanged.

Invoice upload now has a prominent primary **Upload invoice** submit action on its
own row. A successful API save collapses the form and renders the saved compact
card, with status, original PDF, full recorded amount and balance. Payment/history
and accounting controls remain functional behind the card's actions. Their
handlers, endpoints, version checks and audit history are retained. Previewing an
email does not send it. Existing invoices are not renumbered, merged or replaced.

## Exact remaining differences and unsupported prototype actions

- The demo's profile/account picker, prototype banner and fake team portrait are
  not real sign-in or staff records. They are intentionally excluded.
- Operations uses the existing ten saved workflow stages. Extra prototype stages
  are not added as invented backend states. PM retains the previously approved
  eight cards rather than reverting to the demo's earlier dashboard counters.
- Overview and Super Admin-only Private Costs remain alongside the six core job
  tabs to preserve existing review/authorisation and private finance workflows.
  Tenants do not receive Quotes, Invoices, Private Costs or deposit metadata.
- The prototype supports pending POPs and invoice issue-date edits. Django has no
  matching POP-verification model or saved original issue-date field in this
  change. **Payments** displays the actual verified receipt ledger; it is not
  misleadingly called a functioning POP upload. **Uploaded** date is labelled
  truthfully instead of being presented as the original invoice's issue date.
- A saved-value email preview is available; sending remains separately disabled.
- Existing multi-invoice jobs stay intact. Full job invoices can have deposit and
  balance receipts against the same number; historical split invoices are not
  silently merged, reclassified or discarded. Their display says so.
- No automatic tenant access-confirmation workflow or invented appointment
  reminders are copied from the prototype. Existing shared-attendance rules stay.
- Backend role/privacy controls override prototype visibility. No styling change
  exposes supplier identities, rates, private documents, notes or finances.

These are explicit functional/data differences, not missing demo source. A claim
of pixel identity across different records and permissions would be inaccurate.
The original styles and available component markup are reused as closely as the
existing saved workflows allow.

## Evidence and review

[Authenticated screenshots and before/after review](DEMO-REVIEW.md) include Super
Admin, Agency Admin, PM, tenant, desktop/mobile navigation, the register, job tabs,
and existing REQ requests. The walkthrough uploads an actual synthetic PDF,
checks the PM's actual attention response, records half the original invoice,
verifies the deposit and confirms attendance eligibility unlocks without changing
the original invoice number or total.

These are actual authenticated Django screens using records saved through the
real endpoints in an isolated temporary SQLite test database. They are not mockups
or renders using browser-local demo state. Records, people and documents are
labelled synthetic; the owner's Windows database/uploads are never opened,
modified, reset or reseeded. Screenshots of the owner's own machine require their
local update and cannot be asserted from this environment.

No schema migration, new dependencies, live email, merge or deployment is included.
The Windows repair script is prepared for review, not run on the owner's computer.
