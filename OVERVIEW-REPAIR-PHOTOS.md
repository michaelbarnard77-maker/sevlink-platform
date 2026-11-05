Repair photos before the assessment decision
===========================================

Sevlink's new-request assessment card now displays a Repair photos thumbnail gallery in Overview, above Attendance needed and Prepare desktop quote. It uses authorised general-purpose JPEG/PNG/WebP attachments already returned by the job API, including tenant and PM photos retained when the request is forwarded. Completion photos, invoices, PDFs and report documents are not inserted into this gallery.

Clicking a thumbnail opens a native, accessible photo dialog inside the existing job workspace. Previous/Next buttons browse the photos; Download original uses the protected attachment endpoint. Escape or Close returns focus to the thumbnail while keeping the job open. Failed image previews show a fallback message. Requests without photos show an explicit empty state and retain both assessment choices. Existing attachment permissions, storage, upload limits and workflows are unchanged; no public media URL or new backend endpoint is added.

Validation: 54 attachment/workflow regression cases completed successfully, with three concurrency checks skipped on SQLite. Authenticated Chromium acceptance checks forwarded tenant/PM photos, image-only selection, thumbnail ordering above the buttons, successful private image decoding/download, larger browsing, Escape/focus restoration, mobile layout, the no-photo state and desktop-quote selection. Preview screenshots use synthetic test images in an isolated temporary database.

The cumulative local installer is update-windows-overview-repair-photos.ps1, with 40 payloads verified against source SHA256. It retains existing backup and rollback protection and migrations through 0036. The owner approved the screenshot preview for publication through the existing Desktop updater.
