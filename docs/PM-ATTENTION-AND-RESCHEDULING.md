# PM action-only attention and confirmed-attendance rescheduling

PM/admin Needs Your Attention is derived only from sent quotes awaiting a decision, eligible attendance requiring the PM's response when they arrange access, and active uploaded invoices requiring payment. Paid invoices, payment claims awaiting Sevlink verification, and reconciliation holds do not request another PM payment. An approved quote without an uploaded invoice creates no attention item.

New reports remain in New Requests. Booked appointments remain in Booked, upcoming attendance and the customer calendar. Informational bookings/cancellations, comments and other workflow activity no longer inflate PM attention; their normal activity/inbox/tab views remain. Tenant appointment alerts and role/portfolio boundaries are unchanged. Independent unpaid invoices or pending quotes may still require action on an otherwise booked job.

Confirmed active attendance shows Need to reschedule, New preferred date and Send reschedule request. The current appointment remains confirmed while the contact proposes a new date. Operations accepts the new request against the existing booking of the same purpose, records client agreement and the reason, then replaces the original appointment while retaining its history. Assessment appointments cannot be mistaken for repair appointments. Terminal jobs retain their history view.

A request-generation check prevents a slow earlier pot response from replacing the pot the user has just selected. Close and Back to jobs continue to preserve the selected pot.

Validation: 84 relevant tests (80 passed, 4 PostgreSQL-only skips), including the real PM dashboard/accounts/calendar browser case. Scoped authenticated/source proof passed with 33 captures, including action-only PM attention, the confirmed-contact reschedule form, and a complete request/confirmation replacing the old booking. All 26 installer payloads were checked against source. No new schema migration; the cumulative updater retains 0035 and backs up the existing source/database. No merge, deployment or live email.
