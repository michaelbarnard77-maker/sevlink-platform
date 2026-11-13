# GitHub styling, submission routing and clickable jobs

GitHub fetch on 29 October 2026 found two newer main-branch commits, `4697e64` and `3dc0e4d`, both editing `portal/dist/features.css`. These were cherry-picked to the development branch, retaining the author's commit attribution. Their Operations-card spacing, colour bars, selected states and responsive layout now feed the actual Django portal through its existing original-source stylesheet path.

The second upstream edit truncated `.agent-need` mid-declaration and removed the invoice badge, attendance time-field and calendar issue styles from the end of the file. The update preserves the new Operations cards but restores that complete original tail. No database/workflow changes came from GitHub. No merge to main, deployment, AWS update or hosted-demo publication was performed.

## Submission routing

Tenant submissions stay Awaiting property manager review, unclassified and unauthorised. Their existing scoped in-app notification goes to the assigned PM/agency administrators. No Sevlink Operations inbox/email event is queued at tenant submission.

PM and agency-admin submissions go directly to Sevlink, already reviewed. The form defaults to Request a quotation, which does not approve expenditure or bypass quotation approval/deposit checks. A call-out instead requires an explicit spending limit and uses the same existing review validation, numbering and access rules. The selected route, server-authenticated role and request-key fingerprint are checked in one transaction. Tenant attempts to supply work authorisation fields are rejected. Retry keys do not duplicate jobs or notifications.

Sevlink receives its existing durable notification and staff update for the direct PM submission. Existing role-based portfolio access remains enforced. Live email remains disabled in local testing; this update does not enable SMTP or send actual email.

## Clickable jobs

The entire repair register/history row opens the existing authenticated job dialog for Super Admin, PM, agency admin and tenant. The separate Open job column/button is removed. Dashboard stage-job cards and upcoming job rows are clickable too. Keyboard Enter/Space activates the same handler, with visible focus and hover feedback. Existing access checks still run on the detail API.

## Owner's local installation

Use Raw copy/paste of `scripts/update-windows-routing-and-job-rows.ps1` into PowerShell after stopping the existing local server with Ctrl+C. It verifies and backs up ten source files, including `portal/dist/features.css`. It does not replace SQLite, migrate the database, change accounts or remove uploads. Restart the original local CMD runserver, then close the job and Ctrl+F5. Payload integrity is checked here; PowerShell execution on Windows must be confirmed by the owner.

Browser screenshots use real authenticated Django screens, real APIs and persisted synthetic test records in an isolated temporary database, not the owner's Windows database.

Authenticated browser proof: 90 screenshots and privacy checks passed for Super Admin, PM, agency admin and tenant, including row click/Enter activation, direct PM call-out submission, existing REQ records, the final-invoice closure flow and mobile navigation. See `visual-proof/routing-rows-github-2026-10-29/`.

Latest regression: 275 tests, 18 PostgreSQL-only skips. All non-browser tests and four browser tests passed. One browser assertion still selected the former child Open job button; corrected it to select the job card itself, then reran all five authenticated maintenance browser tests: all passed. JavaScript syntax, Django checks, source scenarios and migration-drift checks passed. Initial and final logs are retained together for review.
