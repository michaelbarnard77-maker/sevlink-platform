# PostgreSQL CI investigation: 715a410

The complete PostgreSQL job log for Source checks run 39390415022 (job
118520305035) reports 52 tests: 29 passed, 22 errors and one skip. Migrations
0001–0003 and Django system checks succeeded. The first error is in
`AttachmentTests.test_authorized_tenant_pm_admin_and_superadmin_can_download`:
the next login fails with `psycopg.OperationalError: the connection is closed`.
The remaining errors cascade through the same test class. Database destruction
completes; there is no open-session teardown failure in this run.

The test consumed the streaming download, then explicitly closed the response
again. The test-client streaming wrapper already closes it. The extra close
emits `request_finished` again, causing Django connection cleanup to close the
connection inside TestCase's active transaction. SQLite concealed the problem.

Commit `9fb2c60` already corrected this before the present investigation: consume
streaming responses once through the client wrapper, without the extra close.
The existing repeated-download/repeated-login test exercises the regression on
PostgreSQL. This verification adds an explanatory comment, with no application
or permission changes. Do not reintroduce manual response closure in these tests.

The separate two-open-session teardown failure in a later commit was fixed by
`ff6e23b`: concurrency worker threads close all their own connections in finally
blocks. Those fixes and the transaction-preserving Operations worker fix in
`10a18dc` remain intact. No tests, security checks or normal database teardown
have been disabled; no forced database deletion is used.

Fresh local verification: 132 Django tests discovered, 126 passed, six
PostgreSQL-only tests skipped; Chromium enabled. Original demo Node tests,
JavaScript syntax checks, Django system checks and migration consistency passed.
PostgreSQL runs in GitHub Actions against PostgreSQL 17, including the concurrency
tests and normal test-database creation and destruction. See the latest Source
checks run on the development branch for the final CI results. Main, deployment,
paid services and live email are unchanged.
