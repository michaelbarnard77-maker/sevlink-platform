# Approved modern Sevlink appearance

The approved appearance uses navy, muted teal, pale blue surfaces, a clean abstract header without a house, white cards and restrained blue/amber accents on attention items. Existing navigation order, forms, role permissions and workflow stages are retained, together with the separately approved Request a repair label and PM-only refurbishment navigation.

The sidebar uses the existing transparent brand asset with a white CSS treatment for legibility on navy, without a white plaque. Account screens and the public site share the softer teal. Job tabs retain their underline and circular count badges. Existing status colours and notification warning indicators retain their meaning.

The cumulative Windows installer is scripts/update-windows-modern-portal.ps1. It verifies all 40 embedded file hashes, backs up the existing SQLite database and source, preserves user uploads and accounts, applies existing migrations through 0036, and rolls back on failure. Live email is not activated.

Validation includes 77 maintenance/attachment/workflow tests (3 database-specific skips), an isolated browser test for PM renovation/photo/callback submission and tenant denial, and 45 screenshots covering landing/login, four portal roles, job tabs, accounts/documents, categories, calendar, and desktop/tablet/mobile layouts.
