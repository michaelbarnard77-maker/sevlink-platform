Deposit invoicing and confirmation stages
=========================================

Sevlink's quoted-job pipeline now separates:
1. Deposit to invoice: an effective quote is approved but there is no outstanding active deposit/historical agency invoice available to pay.
2. Awaiting Deposit: the agency-visible active deposit invoice has been uploaded and remains unpaid.
3. Awaiting Confirmation: the payer has reported Paid, or the required deposit funds were recorded and still need explicit Sevlink verification.
4. Ready to Schedule: existing deposit_state eligibility confirms the required 50% amount and explicit verification, or an existing authorised scheduling arrangement applies.

Deposit to invoice and Awaiting Confirmation are Sevlink-only dashboard pots. PM/agency dashboards retain eight pots; Awaiting Deposit only counts invoiced deposits still requiring payment and excludes claims awaiting confirmation. The pending Paid claim continues to notify Sevlink without recording money or unlocking scheduling. Only the existing authorised verification operation records bank-confirmed payment/allocation. Historical records, refunds, reconciliation holds, free assessments, call-out authorisations and audited manual overrides retain their existing rules. An insufficient paid deposit invoice returns to Deposit to invoice for the remaining requirement rather than falsely unlocking scheduling.

Invoice upload, the PM's Paid action and staff verification refresh the surrounding dashboard without closing the job. Job next-step text explains the current phase for staff/PMs while keeping financial details out of tenant guidance. No migration or new receipt-writing mechanism is introduced.

Validation: 82 existing/new operational, customer, document and payment-report regression cases completed successfully, with five SQLite concurrency cases skipped. A real-browser flow uploads the deposit invoice, reports Paid as PM, confirms PM pots/attention and scheduling stay locked, then verifies as Sevlink and checks the required 50% amount and Ready to Schedule. Four Operations screenshots cover each stage. Installer integrity is checked for all 40 cumulative source payloads.

New-agency testing uses the real Create agency account route, rather than automatically seeded users. The local DEBUG default enables registration. Signing up creates an agency administrator; invite a PM, add a property and invite its tenant to exercise tenant -> PM -> Sevlink routing. No shared test credentials or passwords are embedded in this update. Real email remains off; account verification/invitation links must be accessed via local email previews for testing.

The broader PM/accounts/calendar and tenant/PM/Operations browser workflows also passed after the stage change. No automatic test-account creation is included; the owner chose the real registration route. See LOCAL-NEW-AGENCY-TESTING.md for local verification and invitation previews.
