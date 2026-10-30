# Phone-confirmed service areas

Phone-confirmed attendance records the active subcontractor's agreement to attend the selected property. Stored province, city and suburb coverage are not prerequisites in this route. The exception is passed internally from the authenticated attendance service through assignment and appointment creation; ordinary regional assignment and calendar APIs retain their existing coverage rules. Inactive/archived suppliers, job permissions, work authorisation, version checks, client-agreed dates and correct booking times remain enforced.

Migration 0035 makes the saved assignment city optional. An unmapped property can therefore be booked without inventing a location. Existing location snapshots and saved coverage records remain intact. The old attendance overlap-exception form is also removed.

Validation: 55 attendance/region/calendar tests passed (51 passed, 4 PostgreSQL-only skips), including empty supplier coverage, an unmapped property city, inactive-supplier rejection and unchanged legacy coverage checks. Authenticated browser proof passed with 30 source/role captures after clearing all seeded supplier coverage before booking. Django checks and migration drift checks passed. All 26 installer payloads match the source. All test records are isolated synthetic data.

The Windows updater backs up the database/source, applies migration 0035, and preserves existing customer information and bookings. No merge, deployment or live email is enabled.
