# Declined quotes and removal buttons

Sevlink Operations now has a Declined pot. A rejected quote enters it automatically when no effective approval or later workflow stage applies. Revision requests remain in Quoting. Approved work and rejected amendments retain their existing authorisation. The recorded-reason manual move also supports Declined without creating an approval or changing invoice balances.

Super Admin → Agencies now opens property sections by default, exposing Remove property and Remove tenant. Existing signed previews, REMOVE confirmation, permission checks and cleanup controls remain in place. Removing tenants retains jobs and removes the account and structured personal details, as previously agreed.

Validation: 14 quote/photo/admin tests passed; JavaScript syntax and whitespace checks passed. No owner data was changed. The Windows updater includes prior updates and backs up source and SQLite before applying the existing schema migrations. No merge or deployment authorised.

Tenant privacy: the property dashboard and job overview omit the access organiser. Tenant workflow API responses omit access_responsibility; PM and Operations retain it. Authenticated browser removal checks passed with 15 captures.
