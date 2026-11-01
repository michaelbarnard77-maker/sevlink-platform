Combined quotations and invoices by job
======================================

Both Quotations and Accounts & Payments now open the combined Job documents library. There is one expandable folder per actual job ID, labelled with the existing reference, property, repair title, status and document counts. Expanding it shows every shared quotation/revision and agency invoice together. Different jobs at the same property stay separate. Quotation and invoice actions open the correct job tab; PDF downloads retain their existing protected endpoints.

The current authorised quotation and accounts endpoints are used together; private supplier invoices and draft quotes are not exposed, and tenants remain excluded. Invoice filters select matching job folders and calculate outstanding/overdue totals from the selected invoice filter. Inside each matching folder, all the job's shared documents remain available and matching invoices are labelled. Quotation amounts are not summed across revisions. Open folders remain expanded when moving between the two document navigation entries or returning from a job.

Native details/summary controls support mouse and keyboard. Mobile folders and document records use a single column. Existing document decisions, payment recording, financial calculations and records remain unchanged. No database migration is added.

Validation: 47 customer-portal/browser regression tests completed successfully (one SQLite concurrency check skipped). Authenticated Chromium acceptance captured eight screenshots and checked grouping, multiple quote revisions, deposit/final invoices, correct invoice-tab opening, protected PDF downloads, filters, retained expansion state, mobile overflow and tenant access denial. The cumulative Windows installer has 36 source payloads verified against SHA256 hashes.

Install by stopping the local server, then double-clicking the existing Update-Sevlink.cmd Desktop launcher. The approved release uses update-windows-job-document-folders.ps1 with the existing source/SQLite backup and rollback protection. Restart the local server and refresh with Ctrl+F5. Live email and hosting deployment are not enabled.
