#!/usr/bin/env bash
# Nightly Postgres backup: compressed dump kept for 14 days locally, copied to GCS if configured.
set -euo pipefail

APP_DIR=/opt/careeros
BACKUP_DIR="$APP_DIR/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/careeros-$STAMP.sql.gz"

cd "$APP_DIR/current"
docker compose --env-file "$APP_DIR/.env.production" -f docker-compose.prod.yml exec -T db \
  pg_dump -U careeros -d careeros --format=plain --no-owner | gzip -9 >"$FILE"
chmod 600 "$FILE"
echo "backup written: $FILE ($(du -h "$FILE" | cut -f1))"

# Optional off-machine copy (set BACKUP_BUCKET=gs://... in .env.production).
BUCKET="$(grep -E '^BACKUP_BUCKET=' "$APP_DIR/.env.production" | cut -d= -f2- || true)"
if [ -n "${BUCKET:-}" ] && command -v gcloud >/dev/null 2>&1; then
  gcloud storage cp "$FILE" "$BUCKET/" --quiet && echo "copied to $BUCKET"
fi

find "$BACKUP_DIR" -name 'careeros-*.sql.gz' -mtime +14 -delete
