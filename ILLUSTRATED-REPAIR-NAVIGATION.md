Illustrated repair categories and navigation
==========================================

The repair-report category picker uses 19 original Sevlink line illustrations with navy outlines and blue accents. Illustrations are keyed by the existing category name rather than display order. Each tile keeps its visible category label and opens the existing repair form. The report fields, privacy, authorisation, file limits and tenant/PM routing remain unchanged.

Desktop and mobile sidebar items now use matching SVG icons with visible text labels. Decorative SVGs are hidden from assistive technology. The category grid adapts to two columns on phones, with visible keyboard focus and reduced-motion support. No external icon CDN or additional image downloads are needed.

Install with the existing Desktop Update-Sevlink.cmd launcher after stopping the website server. The cumulative installer is update-windows-illustrated-icons.ps1; its 36 payload hashes were verified against the source. It includes landing/portal and prior workflow updates, uses the existing source/database backup and rollback process, and keeps the database at migration 0036.

Validation: authenticated Chromium proof passed for Operations, PM and tenant navigation; all 19 distinct category illustrations; Plumbing/Electrical/Roofing form selection; phone layout without horizontal overflow; keyboard tile activation; and actual PM/tenant report submissions retaining Plumbing and their correct reviewed/awaiting-review statuses. Nine screenshots were captured in the isolated synthetic-data workspace. JavaScript syntax and whitespace checks passed.
