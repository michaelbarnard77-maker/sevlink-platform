Job tab presentation
====================

The job tab strip uses a white rail, turquoise active underline and a separate circular count badge containing digits without parentheses. Labels, role permissions, active-panel behaviour and attention/unread calculations are preserved. Accessible tab names stay unchanged; aria-description retains the count and its meaning. The yellow top-level Updates/Notifications controls are unchanged.

On phones, the strip scrolls horizontally inside the job dialog. Keyboard focus remains visible. The new styling is scoped to the job tab strip.

Validation: both PM/account/calendar and the full tenant/PM/Operations repair browser flows passed after updating their badge-text assertions. A separate four-role screenshot check passed for desktop/mobile layout, keyboard activation, accessible counts and preserved Quotes/Invoices controls. The cumulative job-tabs installer has 40 source payloads verified by SHA256.

The Operations Quoting label is renamed Quote to upload, retaining the existing quoting stage identifier and all saved job classifications. Upload still sends a quote for PM approval; only an approved quote with payment required enters Awaiting Deposit. Existing audited manual overrides remain available. A workflow regression check exercises the one-step PDF upload and PM approval sequence, and an authenticated screenshot verifies the renamed pot, job count and navigation. The tab style and exact pot name/sequence were approved by the owner.

Quote-stage validation: all 31 operational workflow cases completed successfully, with three SQLite concurrency checks skipped. The new sequence test verifies desktop triage → quote upload → PM approval → deposit using the real upload/decision endpoints. An Operations screenshot confirms the Quote to upload pot and its job count/navigation. No migration or stage identifier change is required.
