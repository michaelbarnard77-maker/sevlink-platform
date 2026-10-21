> Numbering correction: new quotations/invoices now require manually entered PDF
> references; no automatic SQ/SI record allocation. REQ identifies requests; SV is
> allocated only on approval. See [current rules](NUMBERING-CORRECTION.md).

# Step 7.5: financial and email readiness acceptance

All changes are development-only. Main is unmerged; nothing is deployed, provisioned or paid for. Owner manual acceptance testing and real mail delivery testing remain outstanding. Quotations, invoices and credit notes are always prepared externally and uploaded as PDFs. No PDF generation, quote-line/VAT calculator, payment gateway or automatic bank refund exists.

## Implemented behaviour

**Refunds:** Operations records a positive ZAR amount, actual date, reason and reference against a specific original payment/invoice. Typed `REFUND` plus a browser confirmation is required. Original payment rows never change; refunds/action history are append-only. A job/invoice/payment lock plus version checks prevent simultaneous over-refunds. Eligibility is the original payment less its prior refunds. Net paid = gross received − recorded refunds; active outstanding = invoice amount − net paid. Gross may exceed invoice face value after a refund and subsequent new payment, but net may never exceed face value or become negative. Full refunds display Refunded, partial refunds update net status/outstanding. Refund reasons/references/actors are Operations-only; agencies see only safe totals/dates. No refund-edit endpoint exists: erroneous accounting entries need a future explicit reversal workflow rather than overwriting history.

**Voids/corrections:** Operations supplies `VOID` confirmation, a reason/date, an external accounting adjustment reference and an acknowledgement that the external accounting/tax treatment has been reviewed. Original PDFs/header/void details cannot be rewritten or reopened. Voids block new payments and retain all original receipts/refunds. Any invoice with payment history gets a reconciliation hold; replacements inherit unresolved holds. Outstanding collectible on a void invoice is zero; `recorded_balance` separately preserves the arithmetic historical balance. A corrected external PDF/new external number/amount/due date/reason creates a linked replacement with its external invoice number and immutable UUID. Payment records are never transferred automatically.

**Reconciliation:** Original funds must be fully refunded before clearing the original hold, followed by an explicit `RECONCILE` entry with reason/reference. Then the replacement hold can be released. External allocation/transfer of old funds is not implemented; such cases remain held for manual accounting resolution rather than inventing a refund or moving funds silently. Refund entries must represent actual refunds, not fabricated balancing entries.

**Credit notes:** Operations can upload externally issued credit-note PDFs with printed reference, amount, issue date and reason. Access inherits invoice visibility. Recording paperwork does not change the payment/refund ledger, avoiding double adjustment. Sevlink does not issue/validate legal tax documents. An accountant must confirm whether an issued South African tax invoice requires an externally issued credit/debit note, the appropriate VAT/document details and record retention; application voiding is not itself cancellation of a statutory tax invoice. No claim of legal/tax certification is made.

**Approved amendments:** An uploaded amendment links to the current approved quote and has a public reason, new amount, manual PDF reference, revision and separate decision. The original PDF/snapshot/decision never changes. Original approval stays valid while an amendment is pending, rejected or revision requested. Only fresh approval makes the replacement effective, using a separate protected approval-replacement record. The UI labels the original historical approval; its model status stays Approved as an immutable historical fact. One amendment chain per approved version, stale/version checks, job locks and unique replacement records prevent duplicate effective approvals. All amendment decisions use existing Operations notification triggers.

**Numbering:** New internal quotation IDs are `SQ-YYYY-0001`; invoice IDs are `SI-YYYY-0001`, global across agencies, with separate annual counters. Revisions/amendments get new IDs and retain their revision chain. Counters and document saves share a transaction and row locks. Four-digit ranges stop safely at 9999; expansion needs an explicit numbering policy change. Historical records are not renumbered. Recognizable historical printed SQ/SI ranges are reserved on upgrade so known numbers are not reused. The external PDF reference/number is a separate manually entered field and is never rewritten to match an internal ID. Internal SI numbering therefore does not impose a new numbering scheme on the accountant's invoices.

**Email readiness:** Committed-event outbox, retries/leases, stable Message-ID, safe HTML/text messages and default `maintenance@sevlink.co.za` remain. New worker heartbeat/health command, audited dead-letter replay, trusted normalized delivery/bounce/complaint importer and audited suppression resolution are implemented. Negative feedback suppresses future mail to that recipient until investigated. There is no public unauthenticated feedback webhook. A verified provider adapter/SNS/SQS subscription is not installed; feedback import is a trusted operator interface, not proof of live SES connectivity. Mounted secret support and disabled worker reference files are provided. No real message has been delivered or live test attempted.

## Manual checklist (perform later with synthetic review accounts)

Use [existing local setup](PHASE-1-VERIFICATION.md), migrate and start `/maintenance/`. Keep both live mail flags at 0. Use separate tenant A, PM A, Operations and agency B browser profiles.

- [ ] Create/report a job with a photo; PM reviews; tenant signs in again and sees persistence. Agency B/cotenant/unassigned PM cannot read it or copied document URLs.
- [ ] Upload an external quotation; verify SQ format and distinct unchanged PDF reference. Send and approve as PM. Download/hash the approved original.
- [ ] Operations uploads an amendment. Original remains valid. Reject/request revision and verify original still valid plus Operations inbox/local preview. Upload/send a revised amendment, approve freshly and verify only the replacement is current; original PDF/hash and decision are unchanged. Retry old/duplicate decisions and two-browser simultaneous approvals.
- [ ] Upload agency invoice and private supplier invoice. Verify SI internal IDs, printed external numbers, due dates and private visibility. PM can only read the agency invoice; tenant/agency B cannot obtain any commercial document. Raw general attachment URLs must not expose them.
- [ ] Record two real synthetic payment entries. Refund part of one using the two confirmation steps. Check gross/refunded/net/outstanding and actor/time history. Refund its balance and confirm eligibility cannot consume another payment. Retry duplicate/stale/over-limit submissions.
- [ ] Void a paid invoice with a reviewed external accounting reference. Confirm no further payment entry is allowed. Original file/receipts remain, collectible is zero, and reconciliation warning is prominent.
- [ ] Upload corrected invoice PDF with new external number/amount/date/reason. Confirm linked original/history and inherited hold. Attempt payment: blocked. Record genuine remaining refunds, reconcile original, then replacement; only then record a new payment. No funds should have moved automatically.
- [ ] Upload a real externally prepared credit-note test PDF. Check access, printed reference, date and audit; ledger totals must not change just from this upload. Accountant reviews tax treatment before any real use.
- [ ] Put distinct private markers in supplier documents, cost fields, refund reasons/references, void/correction notes and private job notes. Inspect PM/agency/tenant JSON, activity and copied download URLs: none may reveal them. Public scope/comments/PDFs must contain only intentionally shared content.
- [ ] Inspect inbox read/unread persistence and local previews for all original required event types and amendment decisions. Email failures/retries must not roll back jobs, decisions or financial entries.
- [ ] Inspect mobile/desktop original layout and static demo. Django flows use server state; static demo finance/planner actions remain browser-local and emit no backend events.

## Commands and API additions

Existing auth, CSRF, UUID idempotency keys and version checks apply. All financial mutations are active Super Admin only; ordinary `is_staff` is insufficient. Paths start `/api/maintenance/requests/<job>/`:

- `POST invoices/<id>/refunds/`: JSON version, payment_id, amount, refunded_on, reason, reference, confirmation `REFUND`.
- `POST invoices/<id>/void/`: JSON version, reason, voided_on, accounting_reference, accounting_reviewed true, confirmation `VOID`.
- `POST invoices/<id>/correct/`: multipart version, new number, amount, due_date, reason, one externally prepared PDF in `attachments`.
- `POST invoices/<id>/reconcile/`: JSON version, reason, reference, confirmation `RECONCILE`.
- `POST invoices/<id>/credit-notes/`: multipart version, reference, amount, issued_on, reason and one external PDF.
- `GET invoices/<id>/credit-notes/<note>/pdf/`: scoped download with invoice visibility.
- `POST quotations/<id>/amend/`: multipart version, external reference, new amount, public reason, optional title/scope, one new PDF. Existing send/decision/revision APIs continue the amendment chain.

Run `bash scripts/check.sh`, or `SEVLINK_BROWSER_TESTS=1 bash scripts/check.sh` with existing Playwright setup. PostgreSQL-only concurrent tests deliberately skip on SQLite. CI runs PostgreSQL migrations/tests and SQLite/Chromium. The browser regression exercises refund confirmations, void/replacement holds, fresh amendment approval and private-note hiding as well as earlier report/photo/comments/payment flows.

## Migrations and limits

0011 adds append-only refund/action/credit-note/approval-replacement/email audit tables and invoice totals/lifecycle fields; replaces gross-only balance constraints with net constraints. Existing gross payments, PDF relationships and decisions remain unchanged; refunds default zero and invoices Active. 0012 adds feedback resolution audit. 0013 reserves recognized historical number ranges without renumbering or emitting historical notifications. These have upgrade-preservation tests. Back up DB and private files together and rehearse on a restored copy before eventual staging/production migration. Reversing migrations after new refunds/re-payments is unsafe because older gross-only constraints may no longer hold; use a forward fix or a coordinated reviewed restore, not ad hoc rollback.

Remaining safeguards and infrastructure: [production/email preparation](PRODUCTION-PREPARATION.md). Owner acceptance, accountant/tax review, privileged-user MFA, throttling, malware scanning, production secret/storage provisioning and recovery drills remain pre-launch work. No deployment approval is implied by passing tests.
