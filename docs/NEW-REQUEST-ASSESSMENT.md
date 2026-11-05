# Sevlink assessment of forwarded repairs

PM-forwarded and directly PM-reported repairs without quotes or a saved Operations assessment remain in New Requests. Sevlink can choose Attendance needed or Prepare desktop quote in Overview. The choice is an append-only WorkflowDecision with version, idempotency and Super Admin checks; the desktop choice moves the job to Quoting. Quotes and existing later-stage appointments, payments, approved work, manual overrides and history remain intact.

Attendance needed opens a free quotation assessment, as confirmed by the owner. It invites the designated access contact to send a preferred date; Operations can also arrange it directly, agree the date with the client and book the existing appointment/calendar workflow without a deposit. The visit purpose is recorded in immutable Operations decisions and returned with attendance history. No repair work, quotation, spending or payment is authorised. Once a quote exists, assessment visits no longer satisfy or unlock repair attendance.

Initial quote upload is hidden until desktop quoting is selected. Existing saved quotes remain visible. No new migration or owner-record rewrite is required. Existing forwarded requests without quotes are included automatically.

Validation: 11 quote/photo/routing tests passed; browser proof passed with 20 authenticated/source captures, including forwarded New Requests and desktop transition. Test fixtures and database are isolated synthetic data.
