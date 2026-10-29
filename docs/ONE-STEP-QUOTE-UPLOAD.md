# Upload quote and notify the PM in one action

The real Sevlink quote form now says **Upload quote**. Its authenticated staff-only `/quotations/upload/` endpoint saves the original PDF and metadata, captures the existing public quotation snapshot, records the sent-for-approval state and notifies the scoped property manager/agency administrators within one database transaction. There is no separate draft/save/send step for a new quote uploaded through this form.

The saved quote remains pending approval; uploading does not authorise work, verify deposits, unlock attendance or generate an official job number. Tenant quote visibility remains excluded. Existing private draft APIs and revision/amendment flows are retained for compatibility with saved history.

A retry with the same key returns the existing quote without duplicate notifications. Changed payloads conflict. PDF validation/scanning, reference reservation, closed-job/classification guards, original-document retention, role checks and transactional file cleanup remain the existing implementations. The form disables Upload while saving, reports upload errors and shows a visible saved-reference/PM-notification confirmation.

Notifications are the existing durable portal notifications. This change does not enable SMTP or send actual live email.

Validation: 38 quote/document/history/authenticated-browser tests ran; 36 passed and 2 PostgreSQL-only tests skipped. Screenshots show actual Django upload and PM screens with persisted synthetic test records in an isolated temporary database, not the owner's Windows database.

Local installer: `scripts/update-windows-upload-quote.ps1`. Stop the existing local CMD server first, copy Raw into PowerShell and wait for SUCCESS, restart the original CMD server and Ctrl+F5. The eleven source payloads include the prior GitHub styling/routing/row changes, are hash-verified and backed up, and do not replace the database or uploads. Windows execution must be confirmed by the owner. The full completion installer also includes this source update. No merge/deployment occurred.
