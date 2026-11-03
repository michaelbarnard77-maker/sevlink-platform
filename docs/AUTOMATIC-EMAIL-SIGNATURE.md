# Branded automatic emails

Account invitations, password resets, operations notifications and completion packages now share the approved company footer: navy, muted teal, clickable maintenance email and website, tagline and a centred faded logo watermark. Personal names and Director titles are reserved for personal correspondence.

HTML is accompanied by readable plain text. The watermark is packaged as an inline MIME image within the HTML related part, requiring no public image host; completion PDFs remain separate attachments. Clients that suppress background images retain a navy background and readable contact text. Gmail and Outlook rendering should be checked with the explicit single-message test before enabling automated delivery.

Queued content, recipients, invitation URLs, expiry, delivery gates, audit and document access checks are unchanged. Neither this update nor its test command starts workers or processes the backlog.

After Update-Sevlink, run in the activated local environment:

```
python -X utf8 manage.py test_branded_email --to michaelbusiness890@gmail.com
```

The command prompts for Bulk SMTP credentials locally, connects using STARTTLS to mail.bulkmail-za.com:5878, sends exactly one test from maintenance@sevlink.co.za and does not persist credentials. The sender must be authorised with the SMTP provider. No AWS configuration is changed.

Verified with 37 account/notification/completion/branding tests (one existing database-specific skip), including safe HTML escaping, clickable links, embedded watermark MIME structure and preserved two-PDF completion packages. Actual browser preview captured with synthetic text. No real email sent by these checks.
