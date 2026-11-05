# Agency team visibility and compact portals

Prepared for review; not yet published. This cumulative local update keeps email gates off and does not deploy AWS.

Agency administrators can see all records in their own agency. Agents/property managers can see only assigned properties and the jobs, quotes, invoices and tenant links attached to them. Agents can add properties, automatically assigned to themselves. Admins can assign or reassign a property using Properties → Edit Property → Property manager. Reassignment immediately changes property-scoped access. Payment reporting remains separate from Sevlink's verification of received funds.

The existing admin invitation and account-management routes are now discoverable in Agency profile → Agency team. This section lists the agency's agents, active status, assigned-property counts and pending agent invitations. Only admins receive the team projection and controls. No roles or existing accounts are changed by the update.

The approved compact Sevlink pot treatment now also applies to PM/admin pots and tenant summary cards. Private-client cards, headers and spacing use the same compact rhythm; form controls remain readable and functional. Existing navigation and workflow permissions are preserved. Portal asset URLs are versioned to refresh cached CSS and JavaScript.

Validation: 76 targeted account, portfolio, quote and invoice tests pass (two database-specific skips). Added tests cover admin-only team projection, cross-agency exclusion, agent isolation, tenant-link denial for others' properties, automatic assignment and admin reassignment. Chromium checks cover PM/tenant desktop/mobile layout, compact pot/card dimensions, admin team controls and property assignment selector, alongside the existing Quotes/Jobs journey. The private-client browser journey also passes with its compact styling.
