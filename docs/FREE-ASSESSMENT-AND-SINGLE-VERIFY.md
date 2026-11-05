# Free quotation assessments and one invoice verification action

Owner-approved free assessments are recorded using immutable Operations decisions linked to saved attendance IDs. Choosing Attendance needed opens assessment attendance and invites the saved access contact to send availability. Operations may also arrange the assessment directly. Operations confirms the client agreement, team and actual booking times using the existing conflict-checked calendar. Only that authenticated confirmation service can pass the assessment exception to assignment and booking; ordinary direct scheduling and work-progress endpoints retain their deposit checks.

Assessment bookings leave the repair status Reviewed, carry a visible Free quotation assessment label, and do not create an approval, invoice, payment or official SV number. Historical assessment appointments are excluded from the repair Booked stage after desktop quoting/quote creation, and cannot be reused for repair attendance. Existing work bookings and call-out rules remain unchanged.

The duplicate Verify and allocate received deposit panel has been removed. The existing invoice Verify action records the bank-verified balance and creates the deposit allocation atomically when the approved quote threshold is covered and no reconciliation hold exists. Idempotent retry adds neither another payment nor another verification. Legacy partial-receipt/allocation APIs remain for existing workflows.

No new database migration is needed. The Windows updater backs up source and database, preserving saved jobs and documents. No merge, deployment or live email is enabled.

Attendance requests route to active linked tenants when Sevlink arranges access, or to the authorised PM/admin when they arrange access. The tenant API exposes permission to respond, without the organiser field. An in-app notification grants a linked tenant access to an invited PM-originated repair within their active property; foreign properties remain excluded. The PM sees shared activity and confirmed public appointment information in either route. Notifications do not enable live email.

Legacy deposits already fully recorded but awaiting allocation retain a single Verify button on the invoice card. It uses the existing allocation action without another receipt. The standalone allocation form remains removed.

Validation: full scripts/check.sh passed (295 tests, 277 passed and 18 PostgreSQL-only skips), including authenticated browser scenarios. The final focused booking regression passed (36 tests, 3 skips), including assessment-to-approved-quote-to-verified-deposit-to-separate-repair-appointment with both original appointments retained. Final scoped browser proof passed with 25 captures, including the legacy paid deposit allocation through the single invoice Verify button and no extra receipt. Installer payloads were decompressed, hashed and compared against all 25 source files. Source and screenshots use isolated synthetic records.
