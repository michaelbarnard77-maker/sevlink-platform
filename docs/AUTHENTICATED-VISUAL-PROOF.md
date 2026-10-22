# Authenticated portal visual review

The review uses the preserved original demo source in `portal/dist`, not an
invented mock-up. Primary references are its `index.html`, `features.css`,
`mobile.css`, `operations-calendar.css`, `professional-polish.css`, `operations.js`,
`repair-register.js`, `app.js`, `features.js`, `professional-polish.js` and
`dialog-navigation.js`. The live Django shell uses the original CSS and layout;
its adapters use authenticated backend APIs rather than demo JavaScript state.

## Reproduce the captures safely

With the project's existing Python environment, locked requirements, Node
Playwright and Chromium installed, run from the repository root:

```bash
python scripts/capture-portal-visual-proof.py
```

Optionally set `SEVLINK_VISUAL_PROOF_DIR` for the output folder and
`SEVLINK_CHROMIUM_PATH` for the browser executable. `NODE_PATH` must identify
Playwright if it is installed outside the repository.

This starts a temporary Django static live server with a separate temporary
SQLite test database and private storage. It does not use or reset the owner's
database, uploaded files or test accounts. Test identities are created without
published passwords. Session cookies are passed to the local browser process
on stdin and are not written into the gallery. Real email delivery is disabled.
All examples are synthetic, clearly labelled visual test data. The before/after
pictures are the same existing website illustration, not genuine repair evidence.

The script performs real backend request, quotation approval, deposit receipt
and verification, appointment, completion evidence and final invoice actions.
It then opens Operations, PM and tenant sessions. It checks eight PM and ten
Operations cards, no demo IndexedDB in live sessions, no private supplier or
internal-note sentinel in PM/tenant dialogs, and no tenant finance tabs.
These capture assertions supplement the full security/browser suite.

Open `index.html` in the output folder. Every screenshot has a full-size link
and differences listed beside it. `manifest.json` is the exact capture inventory.
The original source is also navigated and captured in a separate browser context
for side-by-side review. Main images use a 1440 × 1000 viewport; long pages and
continued tab captures are labelled separately.

## Per-screen comparison

These are source-style matches, **not a claim of exact pixel identity**. The
hosted signed-in demo and any separately held owner screenshots cannot be
certified from this local source comparison.

| Screen | Source styling reused | Deliberate differences retained |
| --- | --- | --- |
| Operations overview | Source control-room heading, summary cards, navy selected stage, job cards | Ten agreed real stages rather than twelve prototype stages; real counts, alerts and sign-in |
| Operations repair register | Source register shell, column layout, filters and buttons | Real stage filtering, REQ/SV records and 50-record backend pagination rather than prototype 25-record paging |
| Job header | Source address-first modal, priority/status badges, agency/PM card and next-step panel | REQ plus authorised SV reference; no prototype/private supplier details; extra Overview tab |
| Comments | Source tabs and conversation cards | Real audience selection and secure attachment controls; Operations-only notes excluded externally |
| Attendance | Source tabs and white information cards | Actual preferred dates and arrival windows; completed jobs show retained attendance history; live call-out form also captured |
| Quotes | Source tabs, quotation cards and download/action buttons | Uploaded manual PDF references, revisions and actual approval history; pending-decision example also captured |
| Invoices | Source tabs, document cards and buttons | Separate deposit/final records, saved balances and manual receipts; Operations has additional audited refund/void/correction controls, so its tab is longer than the prototype |
| Timeline | Source event dots, separators and actor/time typography | Permanent role-filtered audit events; generic workflow-decision labels remain in some rows |
| Before & After Report | Source-style branded report and paired photo columns | Accepted database report and authorised file downloads; explicit test-illustration disclaimer in these captures |
| PM overview | Source navy/turquoise palette, white cards, outline icons | Exactly eight ordered cards and attention banner required by the owner; unique-job counts from authorised portfolio |
| PM repair jobs | Source register styling | Portfolio-scoped status filters; no global agency/private data |
| PM job tabs | Same live modal and tab styling as Operations | No Private Costs tab or internal finance/actions; agency-visible quotations and invoices retained |
| Tenant job | Same header, conversation, attendance and report styling | No agency quote/invoice tabs, internal notes, private costs or supplier identity |
| Sidebars | Source logo, navy panel, outline icons and spacing | Role-specific agreed links; FINANCE staff-only; no simulated account switching; approved turquoise PM/tenant selection state |

## Fixes found during visual review

- Restored the source Operations heading size and selected navigation/stage state.
- Reused source job cards for stage drill-downs and removed the redundant
  all-jobs table from Operations overview; the full register remains in navigation.
- Added real Operations pipeline-stage filtering to the source-style register.
- Restored priority and agency/PM information in the source-style job header.
- Corrected completed-job Attendance text and removed inappropriate completed-job
  deposit-verification prompts.
- Removed empty finance tabs from tenant job details.
- Excluded completed/closed/cancelled jobs from upcoming attendance and visit counts.
- Updated browser-test selectors to navigate the actual register and distinguish
  stage headings from source job-card headings. No assertions were disabled.

No schema migration is needed for these review fixes. Original demo files are
unchanged. Merge and deployment remain blocked on the owner's screenshot review;
Windows merge/deployment instructions will be supplied after that approval.
