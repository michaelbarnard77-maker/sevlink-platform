# Sevlink assessment of forwarded repairs

PM-forwarded and directly PM-reported repairs without quotes or a saved Operations assessment remain in New Requests. Sevlink can choose Attendance needed or Prepare desktop quote in Overview. The choice is an append-only WorkflowDecision with version, idempotency and Super Admin checks; the desktop choice moves the job to Quoting. Quotes and existing later-stage appointments, payments, approved work, manual overrides and history remain intact.

Attendance needed records the assessment route. Existing PM call-out/attendance authorisation remains necessary; this action never creates an appointment, approves expenditure or invents a payment. The user has been asked whether pre-quote assessments should instead be free bookable visits; that policy is pending.

Initial quote upload is hidden until desktop quoting is selected. Existing saved quotes remain visible. No new migration or owner-record rewrite is required. Existing forwarded requests without quotes are included automatically.

Validation: 11 quote/photo/routing tests passed; browser proof passed with 20 authenticated/source captures, including forwarded New Requests and desktop transition. Test fixtures and database are isolated synthetic data.
