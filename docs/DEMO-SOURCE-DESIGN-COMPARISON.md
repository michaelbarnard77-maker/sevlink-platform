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
