# Private GitHub repository

Target: https://github.com/michaelbarnard77-maker/sevlink-platform

GitHub reports private visibility and push access for this session. The initial remote main branch contained only a two-line README identifying the Sevlink Property Maintenance Management Platform. The project import retains that commit as its parent and expands the README with the existing project documentation. No force push is required.

All exported application files, images, deployment files, documentation and both `.openai/hosting.json` configurations are retained. The hosting project IDs are identifiers, not authentication credentials; retaining them does not deploy or publish either site.

The source review found no live passwords, API keys, private keys or customer data in the intended tracked files. The Django test password is an isolated test fixture, `.env.example` contains placeholders, and example people/addresses/contact records are demo fixtures. Existing public Sevlink business contact details and display names are intentionally preserved. Databases, actual `.env` files, uploads, backups, dependencies and generated caches remain excluded. PNG assets contain no embedded metadata. This is a source review, not a guarantee about every possible secret format.

## Local verification

Use Python 3.12 and Node 24. Create and activate a virtual environment, install `portal/production/requirements.lock`, then run `bash scripts/check.sh`. GitHub Actions runs these checks without production secrets and does not deploy.

## Subsequent changes

```bash
git clone https://github.com/michaelbarnard77-maker/sevlink-platform.git
cd sevlink-platform
# Edit and review changes, then:
git add .
git diff --cached
git commit -m "Describe the change"
git push origin main
```

Authenticate through GitHub CLI or an authorized credential manager; never embed access tokens in source or remote URLs. To avoid exposing a private email in commit metadata, configure the GitHub-provided noreply address in your local Git author settings.

Keep the repository private. After the first Actions run, protect `main` with pull requests and required `checks` status where supported. Grant minimum collaborator permissions and enable available secret scanning/push protection and dependency alerts. Keep production/customer records and credentials outside Git, even for private repositories. No open-source license was inferred or added.

The launch gaps in PROJECT-REVIEW.md still apply. Publishing source does not establish production readiness.
