# One selected local password-reset email

`python -X utf8 manage.py send_local_password_reset --to user@example.test`

This explicitly sends a password-reset link for exactly one active account with a usable password. It prompts privately for Bulk SMTP credentials, queues a standard Django reset token, and passes only that queue record ID to the existing leased delivery worker. Other queued records are never selected. No automatic delivery flags are persisted, no passwords or invitation/property links are changed, and no AWS configuration is touched.

The reset link deliberately uses http://127.0.0.1:8000 and opens only on the computer running the local portal. Start the local server before opening it. Do not use this command for remote tenants or production. SMTP acceptance is not proof of inbox delivery; check the recipient mailbox.

Missing, inactive, unusable-password or ambiguous accounts are refused before requesting credentials. Errors retain the existing sanitized queue/attempt behavior. Standard token expiry and invalidation after password change apply.

Validation: targeted delivery sends the selected account once and leaves older backlog untouched; reset token is valid for the selected user and uses the local origin; account password is unchanged during sending; missing accounts cause no queue row or credential prompt. Account/branding/reset suite: 12 tests, one PostgreSQL-only skip.
