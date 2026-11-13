# Compact Sevlink dashboard, access contacts and unread inbox

Prepared for visual review; not published yet.

Sevlink summary cards and stage pots are compact horizontal cards, with smaller icons, shorter headings and tighter spacing. Wide desktop uses five columns; tablet and phone remain responsive. PM dashboard geometry is unchanged. Upcoming attendance is removed from Sevlink stage pages; calendar records and job Attendance tabs remain available.

When a PM-forwarded request selects Sevlink to arrange access, the authorised Sevlink job popup shows active tenant contacts linked to that exact property address, including clickable phone/email. No new account is created. PM-arranged access and unreviewed tenant reports do not expose this contact section. PM, tenant and foreign-agency users do not receive the Sevlink contact list. PM repair submission includes a reminder to maintain tenant details under Properties.

Operations notifications now open an unread-only feed. Mark read removes the row and decrements the badge immediately. Saving persists the existing per-user receipt; errors restore the row and count. Default API history remains available and no notification or job is deleted. Opening a job continues to mark its notification read. Unread pagination filters before applying the page cursor.

Validation: 52 maintenance/pipeline/contact/inbox/Step7 tests, one PostgreSQL-only skip. Actual browser proof verifies compact card height, all 13 pots, preserved upcoming API data with no attendance panel, both payment routes, linked sample contact display, unchanged customer navigation, mobile containment, immediate removal while POST is delayed, persistence after reopen and rollback after simulated HTTP failure. No live email or AWS changes. No new migration after 0037.
