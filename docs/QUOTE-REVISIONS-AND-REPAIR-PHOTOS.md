# Quote revision controls and repair-photo forwarding

Sent quotes now display the saved value, metadata and original PDF download without an unsolicited revision form or another initial-upload form. The normal revision form appears only after the PM/agency administrator records **Request revision**. The server also rejects a normal replacement before that request and prevents a second initial published quote while a current draft/sent/requested/approved quote exists. Legacy private draft APIs remain compatible with saved history.

**Upload revised quotation** saves the replacement PDF and sends it for PM approval in one transaction; retry keys do not duplicate revisions/notifications. The previous PDF/history remain. Revised uploads do not approve expenditure. Existing approved-amendment accounting remains intact: rejected amendments have a separate collapsed staff action, and the original approval stays effective until a replacement is approved.

## Multiple photo selection and limits

Tenant/PM report, shared-attachment, comment and forwarding uploads accept multiple selections. The picker retains earlier selections when another is added, including matching phone filenames, and provides Remove/Clear controls, size feedback and visible errors. Files must be at most **5 × 1024 × 1024 bytes each**, with **25 × 1024 × 1024 bytes total**. The streaming parser and per-job saved-byte checks enforce limits on the server, not just in JavaScript. A bounded maximum of fifty files per selection remains an abuse/resource guard; it does not replace the byte limits.

General shared/agency repair media share the 25 MB saved-byte budget, including existing files; staff internal-note media have a separate private budget. Existing files are not deleted or truncated to enforce the new limit. Photo decoding, EXIF/GPS removal, format/20 MP limits, PDF validation/scanning, private storage and download permissions remain. Staff completion-report photo limits remain the separate established workflow. Commercial PDF uploads remain one PDF up to 5 MB.

## PM forwarding

Tenant photos stay on the same saved maintenance request. The PM review form explains that existing request photos are included automatically, with no copying/re-upload. Its optional multi-photo selector lets the PM add photos when the tenant supplied none, or add supporting photos within the remaining budget.

PM forwarding supports multipart uploads, checks portfolio/role access before image preparation, fingerprints metadata/photo contents for retries, locks the job, validates the review and saves the new photos/classification/notification in one transaction. A failed size/storage/authorisation check does not forward the job or partially save photos. An unavailable private store returns a visible retryable error. Existing tenant file IDs remain unchanged and Sevlink can download them through its authenticated job view after forwarding. No live email is enabled or sent by this update.

## Verification and owner installation

Full regression: **288 tests, 270 passed and 18 PostgreSQL-only skipped**, including source scenarios, JavaScript syntax, Django checks and no migration drift. The final seven focused quote/upload/forwarding tests also passed, including requested-only revision, repeated uploads/notifications, photo limits, retained file IDs, PM/no-tenant-photo submissions and storage-failure rollback.

Actual authenticated browser acceptance passed with **18 screenshots**: sent quote without edit forms, PM-requested revision, one-step revised upload, cumulative same-filename phone selections, automatic tenant-media forwarding, PM-added photos and retained approved-amendment handling. Fixtures are persisted synthetic records in a temporary SQLite/private store, not the owner's Windows data. Screenshots/logs are in `visual-proof/quote-photos-2026-10-29/`.

Use `scripts/update-windows-quote-photos.ps1` through the established Raw/PowerShell workflow after stopping the local server. It backs up SQLite/source and verifies twenty-one source payloads, including the Django file-count setting. It ensures the previous schema through 0034; this feature adds no new migration. Restart the original local server, close the job, Ctrl+F5 and reopen it. Payloads are verified here; Windows execution must be confirmed by the owner. No existing records are removed during installation. No merge, AWS update or public deployment occurred.
