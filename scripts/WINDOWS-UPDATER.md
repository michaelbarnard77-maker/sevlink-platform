Update Sevlink launcher
======================

Save Update-Sevlink.cmd to the Desktop once (use the exact .cmd extension, not .txt). Stop the website server with Ctrl+C, then double-click the launcher. No administrator rights, Git installation, token, or large pasted script is needed. Windows PowerShell 5.1 and an internet connection are required.

The launcher checks windows-update.json on the development/phase-1-foundations branch, downloads the named immutable installer from this repository over HTTPS, and validates its SHA256 before executing it. TLS validation remains enabled. The manifest accepts only commit-pinned update-windows-*.ps1 paths in this repository. PowerShell execution policy is set only for this launcher process; machine and user policy settings are unchanged. The installer checks that the local server is stopped, validates embedded payloads, and backs up source and SQLite before installation. Failures keep the window open with an error. No database, photo or account is transmitted to GitHub.

The same launcher can be used for future updates. To publish an approved update, first push its cumulative installer, then change windows-update.json to its immutable commit URL, version and SHA256. Never point it at a mutable branch URL. The manifest/hash checks detect incomplete or changed downloads; they are not an independent signing system and rely on repository control and HTTPS.

After green SUCCESS, restart the original CMD server with:
python -X utf8 manage.py runserver 127.0.0.1:8000
Then open http://127.0.0.1:8000/ and choose Portal.

Validation: the currently referenced public GitHub installer was downloaded and its full SHA256 matched the manifest. URL constraints, small launcher size and pause/error handling were checked. Windows execution cannot be exercised in the Linux workspace.
