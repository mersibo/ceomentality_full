#!/bin/sh
set -eu

mkdir -p /backups
while true; do
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/${PGDATABASE}-${timestamp}.sql.gz"
  pg_dump --no-owner --no-privileges | gzip > "$target"
  find /backups -type f -name "${PGDATABASE}-*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -delete
  sleep "$BACKUP_INTERVAL_SECONDS"
done
