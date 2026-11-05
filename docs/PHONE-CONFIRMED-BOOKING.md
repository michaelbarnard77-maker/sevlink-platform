# Phone-confirmed subcontractor bookings

Sevlink calls subcontractors and records the agreed booking; it does not hold their team availability. The attendance form explicitly records the phone-agreed date/time and sends phone_confirmed=true. There is no team selector and no stored availability, working-day, team absence or overlap gate for this specific manual confirmation path. Private calendar APIs without the authenticated attendance/phone context retain their existing checks.

The original calendar schema requires a team reference. A clearly named internal booking group, Bookings — team not specified, provides that reference without assigning one of the subcontractor's actual teams. Its working_days remain empty (unknown), rather than inventing availability. This group is private; tenant and PM public appointments do not disclose team identities. Original team data and appointment history are retained.

Confirmation still checks the staff role, job/quote/deposit or free-assessment eligibility, supplier active status, job version, client agreement when the date changes, future date, public arrival window and end time after start on the same day. The phone confirmation is recorded with the operator and timestamp in the existing immutable decision history. Retry keys preserve the original appointment.

Booking records the agreed appointment and its Booked status for repair attendance; a free assessment leaves the repair Reviewed. It does not advance work to on site or completion. Existing recorded-reason manual stage controls remain. Existing finance-triggered closure rules are unchanged.

The entire Teams and scheduling preparation section, Add team, team search/status filters, availability forms and direct team appointment forms are removed from the subcontractor profile. Company details, coverage, compliance documents, agreements, finance and assignment/activity history remain.

The Windows updater preserves saved jobs, accounts, documents and team history. It enables no real email, deployment or merge.

Validation: current Django suite passed (298 discovered tests: 275 passed, 23 skipped, comprising browser opt-in and PostgreSQL-only cases). The focused attendance/calendar/supplier-finance suite passed (44 tests, 3 skips), and 30 authenticated/source captures passed, including an actual phone-confirmed assessment booking and the subcontractor profile without team controls. Existing browser regression scenarios also ran successfully. All 25 updater payloads were decompressed, hashed and compared against checked-in source. All tests used isolated synthetic data.

Phone-confirmed attendance also bypasses saved service-area matching. The property city is optional on a new assignment (migration 0035); existing location snapshots remain unchanged, and an unmapped property is stored as unknown rather than guessed. Ordinary regional assignment/calendar calls keep their mapped-coverage rules. The attendance overlap-exception control is removed because it is irrelevant to this manual flow.
