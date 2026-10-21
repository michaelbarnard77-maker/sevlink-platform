# Step 7.5 recovery and verification

Recovery baseline: `development/phase-1-foundations` ended at `d605e5d`; GitHub and draft PR #1 had the same head. Earlier commits `a5dd817` and `ff6e23b` were present, including the explicit concurrency-thread connection cleanup fix. Step 7.5 source/migrations/tests/UI/worker examples and acceptance guide were saved as uncommitted changes. None of those financial features needed rebuilding or resetting.

The previous temporary virtual environment and `/tmp` test logs were unavailable. Dependencies were restored from the unchanged `requirements.lock`; existing Chromium and Playwright were reused. A missing production-preparation document referenced by the saved acceptance guide was completed. No account data or production DB was used for tests.

## PostgreSQL cleanup investigation

The earlier two-session teardown error was caused by request threads retaining healthy persistent connections (`CONN_MAX_AGE=60`). `close_old_connections()` does not close every healthy connection. Commit `ff6e23b` had already corrected the original test with `connections.close_all()` inside the thread's `finally` block. Both subsequent payment and Step 7.5 concurrency helpers also contained that explicit closure.

Recovery preserves those fixes and adds assertions in all three concurrency helpers that every thread-local Django connection is released after closure. Threads are joined and exceptions propagate through the executor results. No `--keepdb`, forced DROP DATABASE, session termination, swallowed teardown exceptions or relaxed financial assertions were introduced. Normal PostgreSQL CI database teardown remains part of successful verification.

## Local result

Fresh full run: **129 discovered; 123 passed, six PostgreSQL-only concurrency tests skipped**. Chromium was enabled. Both original Node demo suites, JavaScript syntax, Django system checks, migration consistency and upgrade-preservation tests passed. The browser covers tenant reporting/files, PM review/comments, Operations invoice/payment/refund/void/correction holds, fresh approved-quote amendment decisions and hidden supplier/financial notes.

The previous run's known test-helper failure (parsing a foreign user's expected HTML 404 as JSON) was already corrected in saved source. It did not recur in recovery. No fresh local test failed. Remote PostgreSQL/CI results are recorded on draft PR #1 after the recovery commit is pushed; do not infer PostgreSQL success solely from SQLite skips.

## Scope and outstanding launch work

All recovered financial workflows stay on the development branch. PDFs are manually prepared/uploaded; no line-item calculator, document generator, bank refund or gateway was introduced. Live mail flags remain disabled. No merge, deployment, AWS/DNS provisioning or paid service activation occurred.

See [acceptance and financial limits](STEP-7-5-ACCEPTANCE.md) and [email/AWS preparation](PRODUCTION-PREPARATION.md). Owner manual acceptance/accountant review, real mailbox/SMTP/SES configuration and genuine delivery evidence, a verified provider feedback consumer, malware scanning, MFA/throttling, production backups/restore drills and infrastructure remain outstanding. Original browser demo finance/planning remains simulated; the authenticated Django workflow uses the database.
