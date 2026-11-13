# Separate Sevlink Quotes and Jobs pipelines

Sevlink has separate Quotes and Jobs navigation. PM and tenant navigation is unchanged. Dashboard pots remain above the selected pot's compact job table; clicking a row opens the existing dialog. Request type shows the PM's Quotation or Call-out selection.

Quotes contains PM-forwarded quote requests, quote preparation, free assessment scheduling/visits, quotation approval and declined quotations. An approved quotation leaves Quotes and enters Jobs. PM-authorised call-outs enter Jobs directly. Tenant reports awaiting PM classification enter neither Sevlink pipeline.

For a new work job, Sevlink Super Admin makes one audited, versioned, idempotent decision:

- **Send 50% deposit invoice**: Deposit to invoice → Awaiting Deposit → Awaiting Confirmation after PM reports Paid → Ready to Schedule after verified receipts cover the required half.
- **Start without deposit**: save an explicit scheduling arrangement and move to Ready to Schedule. No receipt or payment is invented. Final invoicing and payment remain due.

On quoted jobs the half is based on the effective approved quotation amount. On call-outs requiring a deposit it is based on the PM-authorised spending ceiling. Existing invoice ceilings, reconciliation holds, remaining balances, reporting and closure requirements remain enforced.

Migration 0037 adds jobs_payment_route. Existing invoiced, booked and arranged work keeps legacy terms; unstarted uninvoiced requests require the new decision. A first quote approval following an older assessment also enters new work intake where no invoice, existing work booking or payment arrangement exists. Existing quote/PDF revisions, payments, appointments, official numbers and private documents are retained.

The UI and workflow were approved after actual browser previews. The cumulative Windows installer is scripts/update-windows-split-pipelines.ps1 and includes migration 0037, source/SQLite backups and rollback. Never run an older updater against a database already at 0037.

Validation: 121 workflow/customer/scheduling/manual-document/payment/pipeline tests (8 database-specific skips). Isolated browser proof confirms separate navigation/counts, approved/call-out intake, both real saved choices, same row-to-dialog behavior, unchanged PM/tenant navigation and mobile containment. Browser sample records and screenshots use an isolated temporary database, not customer records. No emails sent and no AWS configuration changed.
