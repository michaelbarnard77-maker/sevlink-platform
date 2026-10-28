# PM attention reasons and job-tab counts

Extends the existing authenticated portal and recipient notification records.
The original demo, database schema, operational decisions and email queues are
unchanged. No migration is needed. Live email remains disabled independently.

## Behaviour

- The PM's Needs Your Attention stage still counts unique authorised jobs. Each
  result now lists all its unresolved actions with relevant amounts and dates,
  using the same backend attention projection as the dashboard banner.
  Unread comments in the same conversation are grouped, and a user's own
  messages do not create a response-required action for that user.
- Quotation approval removes the quotation-decision action; any remaining
  deposit/invoice/attendance action is shown with its own explanation.
- Tabs show `(n)` only when there are outstanding items or permitted unread
  updates. They are not document totals or simulated browser notifications.

| Tab | Badge meaning |
| --- | --- |
| Overview | PM review and pending additional-work authorisations |
| Quotes | Pending quotation decisions; Operations also sees current draft/revision work |
| Invoices | Active agency invoices with a positive outstanding balance |
| Attendance | Required date request or pending Operations decision; otherwise unread attendance updates |
| Comments | Permitted unread messages from other users, excluding the reader's own messages |
| Before & After Report | Unread accepted completion-report notifications |
| Timeline | Permitted unread status/cancellation/completion updates |
| Private Costs | Outstanding private invoices; Operations only |

Opening a tab marks only that recipient's existing notifications read. It does
not approve a quote, settle an invoice, confirm attendance or change job status.
Consequently unpaid/partially paid invoice badges and pending approval badges
remain when their tabs are opened. Read failures retain the unread badge and
offer a retry. Notifications and business actions are not added together to
double-count the same item.

Tenant responses contain no quote, invoice or private-cost badge metadata.
Comment counts use only comments visible to that recipient; private supplier
invoices cannot contribute to external counts, even if a notification were
misdirected. API and download permissions remain in force. Tab names retain
stable accessible labels with an accessible description of their badge count.

## Refresh and scope limits

Counts are refreshed when a job opens or a saved action reloads it; this change
does not add WebSockets or live polling within an already open job. The existing
dashboard refreshes after closing a customer job dialog. A report badge follows
the existing accepted-completion notification, not every individual photo upload.
Mailbox authentication and the revised live-email recipient policy are separate
unfinished work; this change does not activate or reconfigure email delivery.

## Verification

New backend tests exercise quotation approval, partial/full payment, document
privacy, cross-agency access, user-specific persistent read state, disabled tenant
conversations, completion reports and attendance action deduplication. Browser
tests exercise visible counts, clearing comment read state, retaining invoice
badges on viewing, clearing quote badges on approval and stage action reasons.
The existing privacy schema allowlist explicitly includes the new safe field.

An existing Monday payment browser fixture was date-dependent: on Mondays a newly
uploaded supplier invoice is due the following Monday, outside the default
today's-Monday cutoff. It now verifies the saved following-Monday date and uses
the existing Upcoming view for payment recording. No production payment rules
or isolation assertions were weakened.

## Windows test-copy update

1. Stop the local server with Ctrl+C and back up the complete working folder,
   including the SQLite database, local environment settings and private uploads.
2. Obtain this development branch's latest ZIP. Copy updated source into the
   existing project folder, preserving `.env`, `.venv`, databases and upload
   directories. Do not replace the whole working folder with an empty download.
3. The runtime files changed for this update are:
   - `portal/production/portal/maintenance.py`
   - `portal/production/portal/customer_portal.py`
   - `portal/production/portal/workflow.py`
   - `portal/production/static/workflow-ui.js`
   - `portal/production/static/workflow.css`
4. From the existing activated Python environment in `portal/production`, run
   `python manage.py check`, then restart with the existing local server command.
   This change adds no migrations or requirements.
5. Press Ctrl+F5 in the browser. Preserve exact filenames, avoiding `.js.js`.

Manual acceptance: open a PM's attention card and check its action explanation;
view a pending quotation `(1)`, approve it and confirm the count clears; view an
unpaid invoice `(1)` and confirm it stays until authorised settlement; read a new
comment and reopen the job to confirm the unread count stays cleared for that
user only. Check the same scenarios with a tenant and a second agency.

The AWS installation is not updated by pushing this branch. Its changes,
protected HTTPS access and backups remain separate staging setup work. Do not
merge or deploy this update without the owner's review.

## Deposit-upload completion and explicit verification (28 October 2026)

The invoice form now reports required-field failures in its own visible alert,
changes its submit button to Uploading invoice while the request is running,
scrolls server/storage errors into view and confirms a successful save inside the
job dialog. The confirmation follows a successful API response and record reload;
it is not simulated success. Browser tests cover a missing PDF and a successful
deposit upload. Actual owner PDF/server errors still require the displayed error
to diagnose; no claim is made that the owner's upload was remotely observed.

Integration tests cover approved quote -> deposit invoice -> PM Needs Your
Attention -> recorded receipt -> blocked attendance -> explicit staff verification
-> unlocked attendance. PMs cannot record their own receipt or verify it. This
sequence now also covers newly uploaded deposit invoices on historical jobs.
Existing historical invoices/payments are not relabelled or migrated; old
non-deposit compatibility rules and authorised scheduling arrangements remain.
No schema change, email activation or AWS deployment is included.

The four-file Windows repair script includes the two frontend scripts plus
portal/customer_portal.py and portal/workflow.py. Stop local Django before applying
it, preserve its generated backup, then restart using the existing configured
command window. Source payload hashes are checked before and after writing;
write failures restore the backed-up files. No SQLite/private uploads/settings
are included in the updater.

## Consistent receipt/verification status and historical numbering

A Paid invoice represents a recorded bank receipt, while deposit verification is
a separate existing authorisation action. The previous Verified received label
made the two steps appear contradictory. Receipt totals now say Recorded received;
the deposit projection explicitly reports verification_recorded and exact blockers,
and Attendance offers a Review deposit action with the actual lock reasons.
The verification form appears above invoice cards instead of below their expanded
payment/refund history. Tenant responses still exclude this financial projection.

The owner's next screenshot confirmed that the existing verification gate had
unlocked attendance. No numbering or payment rules are changed by this status fix.
Super Admin now sees Awaiting PM attendance request when the gate is open and no
request exists; the PM sends the preferred date/window or call request and staff
then confirms attendance. Existing role checks remain unchanged.
