# Private maintenance attachments

Implemented on `development/phase-1-foundations`. Local development storage only; no S3 resources, cloud credentials or paid services were created. Nothing is merged or deployed.

## Connected behavior

- A tenant can select up to five photos/PDFs on the authenticated maintenance report form. Multipart submission creates the report, status/audit records and attachments together; JSON-only report submission remains supported.
- The job detail lists shared attachments with authenticated download links. Tenants can add files to their own open requests. Assigned PMs, agency administrators and Sevlink Super Admins can also add shared files to requests they can access.
- Tenants see only their own reports on active linked properties. PMs see their assigned properties; agency administrators see their agency. Django superusers have global access. Other agencies, other PM portfolios, cotenants, anonymous/inactive users and plain staff accounts are denied.
- Uploads recheck job access after taking a parent-row lock. File count is checked under that lock to serialize concurrent uploads on PostgreSQL. Completed/cancelled requests remain downloadable but reject new files.
- Every attachment is shared with everyone authorized to read that request. Do not attach private Sevlink/subcontractor records: this slice has no staff-only attachment category and cannot redact sensitive information inside a file.

The original static portal demo and public site are unchanged. The demo's browser-local files are not uploaded or imported into Django. Authenticated uploads use the existing form/detail styles with no new visual design.

## Format and resource policy

| Limit | Policy |
| --- | --- |
| Types | JPEG, PNG, WebP and PDF only |
| Per file | Nonempty, maximum 5 MiB (displayed as 5 MB in the UI) |
| Per submission | Up to 5 files |
| Per maintenance request | Up to 10 files |
| Photo dimensions | At most 20 million pixels; static images only |
| PDF | Unencrypted, 1–100 pages; rejects forms, actions, JavaScript, launches, embedded files and rich media |

The server checks extensions, declared MIME types and actual parsed contents. A generic `application/octet-stream` declaration is accepted only when parsed contents and extension match an allowed type. HTML, SVG, GIF, HEIC, executables, Office documents, animation and malformed or mismatched files are not supported. PDFs with active links/actions, forms or signatures may be rejected by this deliberately conservative policy.

Photos are fully decoded and rebuilt from pixels. EXIF/GPS and other metadata, appended payloads and animation are not retained. EXIF orientation is applied before metadata removal. PDF structural checks do not constitute malware scanning or document sanitization; PDF contents/metadata are retained. PDFs and photos are served as downloads, not inline previews.

A streaming Django upload handler enforces per-file, file-count and aggregate file-byte limits before memory/temp-file storage can grow without bound. Django also caps form metadata at 64 KiB, file count at five, field count at twenty and in-memory file buffering at 1 MiB. Oversized requests may be rejected by middleware before a JSON error can be generated; the frontend handles non-JSON errors with a generic message. Reverse-proxy limits/timeouts and per-user/agency quotas remain part of staging hardening.

## Storage and migration

`0003_maintenanceattachment.py` adds a metadata table linked to the existing maintenance request. It records an opaque UUID, safe display filename, canonical MIME type, stored size, SHA-256, storage key, uploader and timestamp. Existing requests and status history are preserved; the migration regression test covers both the onboarding upgrade and requests already present at 0002.

Local storage defaults to `portal/production/private-attachments/`, overridable through `PRIVATE_ATTACHMENT_ROOT`. Do not configure this inside any public/static/media directory. Django checks reject overlap with known public directories. The directory is Git- and Docker-context-ignored. Stored filenames use only server-generated keys:

```
maintenance/<request-uuid>/<attachment-uuid>.<canonical-extension>
```

Browser filenames are sanitized display/download names, never storage paths. Path traversal, symlink escape and collision overwrite are rejected. New local storage roots/directories use mode 0700; files use 0600 on Unix. Keep OS/user permissions restricted on any pre-existing storage directory.

The local backend refuses public storage URLs. No `MEDIA_URL` route, static route, Caddy file server or public object URL exposes uploaded files. Metadata serialization does not expose storage keys, hashes, uploader identity or local paths.

File writes and database transactions cannot be one atomic resource. The application validates the entire batch before writing, wraps records/audits in a database transaction, removes successful file writes on application rollback and removes partial local writes on write failures. Cleanup failures log a generic reconciliation-needed message. A process/host crash or failed cleanup can still leave an unreferenced private object; crash reconciliation is not implemented yet.

Proposed Compose packaging adds a web-only `private_uploads` named volume; Caddy does not mount it. Docker prepares the directory for the existing non-root application user. These are source configuration changes only: no containers were deployed or started. Database and file-volume backup/restore must be designed and tested together before production.

## Storage interface prepared for S3

All application storage access goes through Django's `storages['maintenance_private']` alias and the `save/open/delete` interface. Application views never call `.path()` or `.url()`. Files stream through the same authorized Django endpoint on every request.

A future S3 integration can supply a backend for this alias, using the same opaque keys and metadata. It must preserve keys on save and map missing objects to `FileNotFoundError` (or extend the adapter's error mapping). It must use a private bucket, block public access, configure least-privilege credentials/encryption/lifecycle and retain authenticated delivery. Existing local objects would require a deliberate, verified migration; changing the alias alone does not copy data. No S3 package, bucket, signed-URL endpoint, credentials or remote storage calls were added now.

## API

| Method | Path | Request/response |
| --- | --- | --- |
| POST | `/api/maintenance/requests/` | Existing JSON fields, or multipart `property`, `title`, `description`, `category` plus repeated `attachments` parts |
| POST | `/api/maintenance/requests/<job-uuid>/attachments/` | Multipart repeated `attachments`; returns current shared attachment metadata |
| GET | `/api/maintenance/requests/<job-uuid>/attachments/<attachment-uuid>/` | Authorized streaming download |

Job list/detail responses now include `attachments`: id, safe filename, MIME type, size, creation time and download endpoint. Download endpoints check the job first, then the attachment's relation to that same job. A file UUID from one request cannot be used with another request's URL. Unauthorized object access returns 404; unsupported/no account roles are denied by existing API checks.

Upload writes require the normal Django session and CSRF token. Downloads use `Content-Disposition: attachment`, `nosniff`, sandbox CSP, same-origin resource policy and `no-store`. No browser-local storage is used. Missing files return 404 and local storage outages return a generic 503 without leaking storage credentials or paths.

## Local use and verification

In your existing activated development environment:

```bash
pip install -r portal/production/requirements.lock
cd portal/production
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Keep the local settings from [Phase 1 verification](PHASE-1-VERIFICATION.md): DEBUG enabled, SQLite and SMTP disabled. At `/maintenance/`, use Report a repair and select optional files, or open an existing open request and use Add shared photos or documents. PM/Super Admin accounts use the Download links in job details.

Full automated local result: **52 Django/API/storage/migration/browser tests passed**, along with both original portal suites, JavaScript syntax, system checks and migration consistency. Browser tests run in temporary private storage and a temporary database. No test files or credentials are committed.

Coverage includes multipart report creation, standalone follow-up files, allowed formats, invalid/spoofed/active/animated/oversized files, image orientation/metadata, file limits, traversal/symlink/collision protection, private response fields, CSRF/method restrictions, authenticated downloads, cross-agency/PM/cotenant isolation, role revocation, closed jobs, storage/database failure cleanup, partial writes and generic storage errors. Chromium exercises tenant photo submission, PM download/additional upload, foreign-agency download denial, Super Admin download, persistent status and mobile layout.

GitHub Actions runs the same browser/source suite plus PostgreSQL 17 Django tests. Check the development branch/PR for the latest remote result; these tests do not establish load, deployment or malware safety.

## Still unfinished

- Antivirus scanning, quarantine and content disarm/reconstruction for documents. Add and verify these before enabling uploads for production users.
- File deletion/replacement, retention/legal-hold policy, crash/orphan reconciliation and audited cleanup jobs.
- Per-user/agency storage quotas, dedicated upload throttling, idempotent retries and concurrent-load/abuse testing.
- S3 provisioning/configuration, actual object migration and cloud integration tests (intentionally deferred).
- File/database backup and restore, capacity monitoring and Docker/Caddy/staging validation.
- Staff-only/internal attachments, inline previews, HEIC/Office formats and document redaction.
- Human end-to-end verification remains deferred as requested. No production readiness or merge approval is implied.
