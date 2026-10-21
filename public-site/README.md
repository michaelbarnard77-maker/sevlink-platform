# Sevlink public website demo

A separate public-facing marketing demo for homeowners, landlords and property agencies. The existing maintenance workspace is unchanged and linked from the agency portal buttons.

Static assets live in `dist/`; no build dependencies. Brand/logo/contact details come from the user's Sevlink assets. The architectural image is reused from their earlier Sevlink site and explicitly labelled illustrative. No completed projects, testimonials, registrations, qualifications, response guarantees or client counts are invented.

The form prepares an enquiry preview, then offers explicit WhatsApp and email-draft links. It does not automatically send messages, upload attachments, store leads or create portal accounts. The visitor adds photographs in their chosen messaging app and sends the message themselves. Business details: Influx Solar Energy (Pty) Ltd t/a Sevlink, 081 028 5034, maintenance@sevlink.co.za, info@sevlink.co.za.

The custom domain is not connected. The Sites demo starts owner-private for review.

A verified live portal may later be linked separately by setting the HTTPS origin
in `dist/portal-config.js`. The blank default adds no live link and leaves the
explicit demo links intact. No deployment or live sign-in domain is assumed.
