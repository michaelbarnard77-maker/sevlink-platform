# Repair report and call-out amount display

The saved original repair description now opens by default in the job header. PM and Operations see a separate Relevant access notes panel sourced from saved workflow access_information; empty notes are labelled explicitly. Tenant access-organiser privacy remains unchanged.

The call-out limit is hidden and disabled for quotation requests, and visible and required for call-outs. This applies to PM direct reporting and review/forwarding. Existing server authorisation validation remains unchanged.

Validation: JavaScript syntax and whitespace checks passed. The authenticated browser run passed with 19 screenshots, including the visible PM report/access panel and quotation → call-out → quotation amount-field switching followed by successful forwarding. All records were isolated synthetic fixtures.
