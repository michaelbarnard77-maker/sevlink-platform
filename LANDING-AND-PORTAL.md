Landing page to authenticated portal
===================================

The public root / serves the existing Sevlink landing design. All three Portal links open /login/ in the same tab. Successful sign-in redirects to /portal/, preserving the existing role-specific workspace routing and account checks. The landing page remains visible at / even when signed in. Existing named dashboard links now resolve to /portal/; maintenance APIs and /maintenance/ remain unchanged.

Local landing assets are bundled under static/landing, with the existing public-site design preserved separately. There is no dependency on the public demo host. Enquiries retain their existing review-before-send behaviour.

The cumulative Windows installer scripts/update-windows-landing-and-portal.ps1 includes the previous multiple-appointment update and all landing assets. Stop the local server before running it. It checks payload hashes, backs up the local database and source, migrates through 0036 and runs Django checks. Newly required asset directories are created automatically. No live email or hosting deployment is enabled.

After restarting the existing local server, open http://127.0.0.1:8000/, choose Portal and sign in. Validation covers public landing access, local asset discovery, the protected /portal/ entry, real password login, workspace routing, account onboarding, tenant privacy and agency isolation.
