#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for script in portal/dist/*.js public-site/dist/*.js portal/production/static/*.js portal/tests/*.cjs scripts/*.cjs; do
  node --check "$script"
done
(cd portal && node tests/full-repair-flow.cjs && node tests/operations-calendar.cjs)
export DEBUG=1
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export SMTP_DELIVERY_ENABLED=0
# Always use local SQLite for checks, independent of the caller's DB configuration.
unset DB_HOST
cd portal/production
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test portal
