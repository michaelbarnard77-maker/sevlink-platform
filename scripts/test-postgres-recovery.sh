#!/usr/bin/env bash
# Ephemeral CI rehearsal only. Uses the PostgreSQL service's matching client tools.
set -euo pipefail
: "${SEVLINK_CI_POSTGRES_CONTAINER:?CI service container required}"
: "${GITHUB_ACTIONS:?This rehearsal runs only in GitHub Actions}"
sevlink_restore_db="sevlink_restore_${GITHUB_RUN_ID:?}_${GITHUB_RUN_ATTEMPT:?}"
sevlink_dump_dir="$(mktemp -d)"
cleanup() {
  local result=$?
  if ! docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" dropdb -U sevlink_ci --if-exists "$sevlink_restore_db"; then result=1; fi
  rm -rf -- "$sevlink_dump_dir"
  exit "$result"
}
trap cleanup EXIT
# Django's test database must have disappeared through normal teardown.
remaining="$(docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" psql -U sevlink_ci -d sevlink_ci -Atc "SELECT count(*) FROM pg_database WHERE datname='test_sevlink_ci'")"
[[ "$remaining" == 0 ]]
docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" pg_dump -U sevlink_ci -d sevlink_ci --format=custom --no-owner > "$sevlink_dump_dir/database.dump"
docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" createdb -U sevlink_ci "$sevlink_restore_db"
docker exec -i "$SEVLINK_CI_POSTGRES_CONTAINER" pg_restore -U sevlink_ci --dbname="$sevlink_restore_db" --exit-on-error --single-transaction --no-owner < "$sevlink_dump_dir/database.dump"
original="$(docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" psql -U sevlink_ci -d sevlink_ci -Atc 'SELECT count(*) FROM django_migrations')"
restored="$(docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" psql -U sevlink_ci -d "$sevlink_restore_db" -Atc 'SELECT count(*) FROM django_migrations')"
[[ "$original" == "$restored" && "$restored" -gt 0 ]]
# A restored database must support a real committed write and rollback.
docker exec "$SEVLINK_CI_POSTGRES_CONTAINER" psql -v ON_ERROR_STOP=1 -U sevlink_ci -d "$sevlink_restore_db" -c "BEGIN; INSERT INTO portal_agency (id,name,phone,area,created_at) VALUES ('11111111-1111-1111-1111-111111111111','Synthetic restore probe','test','test',CURRENT_TIMESTAMP); ROLLBACK;" > /dev/null
printf 'PASS: normal Django test database cleanup and ephemeral PostgreSQL dump/restore/write rehearsal.\n'
