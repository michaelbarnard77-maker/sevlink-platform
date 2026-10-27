# Demo source comparison and authenticated design reuse

The hosted demo URL returned HTTP 401 (sign-in required). An attempted Chromium
navigation also encountered the execution environment's certificate trust error.
The hosted dashboard and job tabs were **not inspected**. The preserved repository
source is the primary visual reference for this update.

## Exact sources

- `portal/dist/index.html`: actual navy sidebar/logo, page shell, typography,
  colours, modal, base `.tabs`, buttons, cards and forms.
- `portal/dist/features.css`: `.ops-pods`, `.ops-pod`, job cards, `.photo-pair`,
  modal dimensions and supporting components.
- `portal/dist/mobile.css`: responsive sidebar, dialog, forms and navigation.
- `portal/dist/operations-calendar.css`: proportional Operations calendar.
- `portal/dist/professional-polish.css`: job address/title, next-step banner,
  document header/property/totals and report presentation.
- `portal/dist/operations.js`: dashboard/card markup and job routing presentation.
- `portal/dist/repair-register.js`: Repair Job Register table/filter layout.
- `portal/dist/app.js`: job header, comments, attendance, quotes, invoices and tabs.
- `portal/dist/features.js`: Before & After report and timeline components.
- `portal/dist/professional-polish.js`: final job next-step and document layout.
- `portal/dist/dialog-navigation.js`: modal back-navigation presentation.

Django's existing `maintenance.workspace` reads the actual demo HTML, retains its
CSS links and removes every demo script, sample identity and browser-state entry
point. Its authenticated adapters remain `static/maintenance.js` and
`static/workflow-ui.js`; no demo actions are used to save real records.

## Reuse and differences

Operations now uses the actual `.ops-pods` / `.ops-pod` structure and selected
state from the demo stylesheet, plus real scoped summary counts. PMs retain the
owner-approved eight cards rather than copying the demo's twelve Operations
stages. Operations retains the ten agreed backend stages; assessment/cancelled
stages from the older demo are not invented as new backend workflows.

The live modal uses the demo's original `.tabs` buttons, 760px desktop dialog,
address/title hierarchy, job summary, back button and `.professional-next-step`.
Comments, Attendance, Quotes, Invoices, Timeline and Before & After Report are
separate panels. Overview and staff-only Private Costs remain additional working
panels. Commercial information and internal schedules remain excluded by the
existing backend permissions; cosmetic similarity does not copy demo permissions.

Before & After Report reuses `.sevlink-document`, `.document-header`,
`.document-property` and `.photo-pair`. Photos come only from the authorised
attachment response and authenticated download endpoints. The sole new document
metadata field is its existing purpose, allowing before/after grouping. No storage
keys, uploader IDs or supplier documents are added. No quote/invoice PDFs are
created, and no payment, approval or completion rule is changed.

The Repair Job Register ports the actual source title, search/filter grid,
bucket buttons, table columns and paging layout. Property, agency (Super Admin),
status, category, priority, open/closed/cancelled buckets and sorting controls
query the existing authorised Django queryset. Search covers every result page,
including REQ/SV references. Facets and counts remain portfolio-scoped; changing a
filter cannot expand agency or tenant permissions. No source browser state is used.

## Screenshot evidence and limits

The screenshots approved in this chat were generated from the authenticated
Django portal, not the inaccessible hosted demo. No separate owner-provided
original-demo screenshot set was attached to this task. Therefore matching an
unseen hosted revision or claiming pixel-perfect owner-screenshot parity is not
possible. Existing approved PM navigation, eight cards and repair icons are kept.

Optional browser captures interact with the local source demo in a separate
browser context, using only its synthetic example records. They visit its register
and six job tabs at 1440px. Live Django captures at matching sizes allow comparison.
These example records are never inserted into the development SQLite database.

No database migration is required. Real customer SQLite, uploaded files, accounts,
quotations, payments and historical decisions are not modified by this work.

## Latest owner navigation reference (27 October 2026)

The owner supplied an agency-demo sidebar screenshot with compact rows and small
white symbols. This supersedes the earlier large turquoise-icon reference. All
authenticated roles now share 12px navigation labels, white semantic symbols,
38px desktop rows and the existing navy/blue selected palette. Mobile drawer
rows retain a 44px touch target. Authorised links and their routing are preserved;
the simulated profile picker and demo account label are not added to real sign-in.
Only workflow-ui.js and workflow.css change at runtime.

## Published reference verified and navigation corrected

The Sites connector resolved the owner-supplied maintenance-demo URL to version 42
(commit 58a0777f69869461272cec00028dc0d51e27f57b). Authenticated read-only
requests retrieved its HTML, CSS and scripts. The published index.html and
features.css SHA-256 hashes exactly match the preserved portal/dist copies.
No hosted source, access settings or deployment was changed.

The prior compact recreation is superseded: desktop buttons now use the original
plain symbol + nonbreaking space + label markup, original inherited colour and
font metrics, 10px/12px padding and 4px vertical margins. The added flex icon boxes
and minimum heights are removed. Agency navigation begins Overview, Repair jobs,
Properties, Tenants, Agency profile, Report a repair, Maintenance calendar, Updates
& reminders. Working Quotes/Accounts and role-specific authorised links remain.
Mobile restores the published dark drawer and white bottom-navigation colours.
The visual harness compares computed font, line height, padding, margins, radius
and button height against the actual matching source for all four role fixtures.

Windows update requires maintenance.js, calendar.css and workflow.css from this
change in the existing production/static directory; no migration or database reset.
The user's screenshot demonstrated the old workflow.css remained installed.
