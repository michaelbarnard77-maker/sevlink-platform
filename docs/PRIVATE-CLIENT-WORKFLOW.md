# Private clients — approved local release

Implemented and previewed with synthetic records; approved for the Windows local updater. AWS deployment is excluded. Live-mail gates remain unchanged and off. This release also contains compact pots, removal of staff Upcoming attendance panels, conditional access contacts and instant unread-notification removal.

## Staff workflow

Select **New private-client request** from Quotes or Jobs and record name, email, phone, property address and work description. Existing pipeline tables and job dialogs display a **Private Client** badge. Internal client containers do not appear as agencies.

For quoted work, upload and send the original PDF. The queued email contains a seven-day direct review link. Opening the link or PDF makes no decision. Accept/Decline applies only to the exact sent revision, once. Superseded and revoked links stop working. Decline comments are optional.

Acceptance moves work into Jobs → New Requests and queues a 48-hour activation link. Staff chooses **Send 50% deposit invoice** or **Start without deposit**. The preferred-date email follows scheduling authorisation, including verification of the required deposit. Clicking Paid reports payment; staff must verify received money.

Private call-outs require a recorded client authorisation and ceiling. They enter Jobs with scheduling authorised immediately and queue activation with a preferred-date request, bypassing quotation approval and the deposit gate.

## Portal and retention

Activation sets a password and opens a separate private-client portal. Clients see only their own jobs, quotes, shared invoices, attendance, shared messages and authorised files. They can report payment, request a preferred date and send comments. Internal costs, other clients, agency portfolios and staff payment controls are excluded.

An inactive audit identity is created with the enquiry; it provides no portal access before acceptance/call-out activation. When all approved/call-out work closes or is cancelled, access is deactivated, sessions invalidated and activation links revoked. Records and documents remain with Sevlink. Returning clients reuse their identity and records, receiving fresh activation when eligible. Access stays active while another eligible job remains open.

The existing membership model supports one role per email. Emails already registered as an agency manager or tenant are rejected rather than silently merged; staff must resolve that identity separately.

## Links and email

Random tokens are stored only as SHA-256 digests in the grant table; the raw token appears in the queued email. Mutations require CSRF protection. `Referrer-Policy: same-origin` preserves same-origin form submissions while excluding token-bearing referrers to other sites. Pages are not cached or indexed. PDFs retain private attachment protections.

Revoked, expired, consumed, closed-job and stale-revision link messages are blocked before SMTP delivery. Closing work retires its pending portal-update mail without flushing unrelated messages. Final authorised completion-document delivery remains possible after deactivation.

External clients require SITE_URL to point to the reachable HTTPS portal. Local 127.0.0.1 links only work on the server computer. This release does not deploy AWS or enable a delivery worker.

## Local updater

`scripts/update-windows-private-clients.ps1` is the cumulative installer, including migration 0038. It verifies payload hashes, rejects newer databases, backs up SQLite and source, applies migrations and checks, and restores source/database on failure. Uploaded files and records are preserved. The desktop update manifest pins the approved installer commit and SHA-256 hash.

## Validation

173 targeted regression tests pass, with nine PostgreSQL-specific skips under SQLite. Chromium checks cover staff creation/badges, anonymous PDF review/acceptance, activation, own quotes/invoices, payment reporting without recording money, staff verification, attendance gates, comments, mobile containment, immediate call-out attendance and cross-client isolation. The split-pipeline browser check covers compact pots, existing dialogs, conditional contacts and instant notification removal with failed-save rollback. All previews use synthetic records.
