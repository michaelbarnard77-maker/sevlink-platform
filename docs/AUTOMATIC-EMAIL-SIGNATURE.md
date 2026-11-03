# Branded automatic emails

Account invitations, password resets, operations notifications and completion packages now share the approved company footer: a light blue banner, navy and muted teal lettering, a centred faded logo, all three contact emails, 081 028 5034, website and tagline. Personal names and Director titles are reserved for personal correspondence.

HTML is accompanied by readable plain text. The full signature banner is an inline MIME image within the HTML related part, requiring no public image host; completion PDFs remain separate attachments. Rendering the banner as one image prevents independent dark-mode recolouring of its text over the watermark. Clickable Maintenance, Finance, Info and Call links remain below the banner. Image alt text includes all contact details. Gmail and Outlook rendering should be checked with the explicit single-message test before enabling automated delivery.

Queued content, recipients, invitation URLs, expiry, delivery gates, audit and document access checks are unchanged. Neither this update nor its test command starts workers or processes the backlog.

After Update-Sevlink, run in the activated local environment:

```
python -X utf8 manage.py test_branded_email --to michaelbusiness890@gmail.com
```

The command prompts for Bulk SMTP credentials locally, connects using STARTTLS to mail.bulkmail-za.com:5878, sends exactly one test from maintenance@sevlink.co.za and does not persist credentials. The sender must be authorised with the SMTP provider. No AWS configuration is changed.

Verified with 37 account/notification/completion/branding tests (one existing database-specific skip), including safe HTML escaping, clickable links, embedded watermark MIME structure and preserved two-PDF completion packages. Actual browser preview captured with synthetic text. No real email sent by these checks.
