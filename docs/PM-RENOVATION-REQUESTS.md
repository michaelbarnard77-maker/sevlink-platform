# PM refurbishment and renovation requests

The customer navigation now says **Request a repair**. Renovations & Refurbishments is removed from the repair category picker and has its own **Refurbishments & Renovations** navigation item for property managers and agency administrators.

The form selects an authorised property and project title. Without a callback request, project details are required; photographs are optional. Selecting **Request a call from Sevlink** requires a contact name and telephone number and makes project details optional. Callback details are saved prominently in the job description, visible to Sevlink with the existing job. New requests use the existing direct-to-Sevlink submission, audit, notification and private attachment workflow. This does not activate live email.

The API rejects tenant renovation submissions, including crafted requests. Property scoping, UUID idempotency keys, private image storage and existing upload limits remain enforced. This change requires no database migration.

Validation: 22 maintenance tests; 55 attachment/workflow tests (3 existing database-specific skips); isolated browser submissions with photo and callback; Sevlink visibility; tenant navigation/category exclusion and API denial; 390px layout. Preview screenshots are generated with SEVLINK_RENOVATIONS_PROOF=1 using scripts/capture-portal-visual-proof.py.

Included in the approved modern portal Windows update.
