# Customer reschedule requests

Prepared for review, not published. No migration, email activation or AWS deployment.

Once an active appointment is confirmed, the authorised access contact sees **Need to reschedule?** and **Send reschedule request**. This applies to private clients, tenants when Sevlink arranges access, and property managers/admins when the agency arranges access. Initial attendance requests retain their original wording. Cancelled and completed visits are not treated as active confirmed bookings.

Submitting a new date creates a pending AttendanceRequest and the durable **Reschedule date requested** event/Operations inbox notification. The existing booking remains confirmed. An identical idempotent submission does not create another request or notification. Staff see **Action required → Reschedule date requested**, with a button opening Attendance. Resolved requests disappear from this live action panel; the historical notification remains in the normal notification history. Closed/cancelled/completed jobs are excluded from the action panel.

Existing booking confirmation and replacement controls remain responsible for coordinating with client and subcontractor, selecting the booking to replace, and recording the reason. The current appointment is cancelled only within the successful replacement transaction; a failed replacement preserves it. Historical appointments remain in the record.

Tests cover the access contact restriction, single notification and replay behavior, preservation of the active booking, replacement confirmation and clearing the action panel. Chromium also checks private-client initial booking, the reschedule form, submission, preserved original appointment, the dashboard action and opening Attendance from it. Previews use isolated synthetic records only.
