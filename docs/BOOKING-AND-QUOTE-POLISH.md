# Quote approval and booking refinements

PM approval accepts a blank or omitted comment; rejection and revision requests still require a reason. Both browser required-state and server validation change with the selected decision. Approval history records the actual empty comment without inventing a reason.

Closing a job using Close, Back to jobs or Escape preserves the dashboard/list beneath it and restores the page scroll position. Role-local selected pots are retained across workspace refresh renders, including the existing periodic refresh and job-stage updates. No permissions or persistent customer data are added to browser storage.

Attendance booking no longer asks the user to select a subcontractor team. If the caller omits team, the confirmation service locks the subcontractor and its active teams and chooses one that fits working days, hours, time off and existing appointments. Explicit historical team API calls remain compatible. The existing assignment, coverage, conflict and authorised-overlap checks still apply. Fully unavailable suppliers return a clear 409, with no partial booking. Existing retry keys retain the original booking.

The whole time field opens an inline time selector with quarter-hour options, selected-state highlighting, contained scrolling, keyboard opening and Escape dismissal. Form values continue to use the existing South African booking endpoint. The visible team dropdown is removed; the internal calendar continues to use real saved team resources.

Validation: 79 relevant tests (72 passed, 7 PostgreSQL-only skips); 16 focused tests passed; 28 authenticated/source screenshots passed, including both close controls for Operations and PM, approval with a blank comment, hidden team selection, and a whole-field time selector choosing 09:15. Installer payloads were decompressed and compared to all 25 current source files. No new migration, merge, deployment or live email.
