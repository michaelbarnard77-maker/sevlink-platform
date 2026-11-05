Test a newly joining agency locally
==================================

Sign out of the existing account, open http://127.0.0.1:8000/register/, enter a new agency name and email, and choose your own password. This creates an agency administrator account. The account must be verified before login.

Real email is disabled on the local test installation. To write one pending account message into the private preview directory, stop the server with Ctrl+C in the original activated CMD window and run:

    python -X utf8 manage.py send_mail_queue --preview
    explorer private-email-preview

Open the newest preview email locally and use the verification/invitation URL from its body. The worker previews one queued message per run; if an older message is selected, repeat to preview the next pending message. Do not share these account links. Restart the original server to open the link:

    python -X utf8 manage.py runserver 127.0.0.1:8000

After verification, sign in as the new agency administrator. Invite a property manager, open their local invitation preview and choose their password. Add the new property and link/invite its tenant, then use the tenant invitation to choose the tenant password. All accounts are separate, and users choose their own credentials. No SMTP configuration is needed for this local preview flow.

Test a tenant repair: report as tenant, review and Send to Sevlink as PM, then sign into the existing Sevlink account and open New Requests. PM-origin repairs can be sent directly to Sevlink using the existing workflow. Existing agency/property/job records are unaffected.
