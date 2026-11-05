#!/usr/bin/env bash
# Backup of the U-QUAIL PyBossa instance: PostgreSQL database + uploaded files (uploads).
#
# Usage (from the repository folder, containers running):
#   ./scripts/backup.sh                  # into ./backups/<timestamp>/
#   BACKUP_DIR=/mnt/backups ./scripts/backup.sh
#
# Variables read from .env (or the environment):
#   BACKUP_DIR            destination folder (default: ./backups)
#   BACKUP_KEEP_DAYS      rotation: deletes backups older than N days (default: 30)
#   BACKUP_AGE_RECIPIENT  "age" public key: if set, each file is encrypted (.age)
#   BACKUP_REMOTE         rsync destination (e.g. user@host:/path/): if set, off-machine copy
#
# A lost campaign cannot be rerun: schedule this script every night (see scripts/cron.example)
# and test the restore at least once (scripts/restore.sh) before the first real campaign.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows): do not convert Linux paths passed to containers

cd "$(dirname "$0")/.."
# Read .env without executing it (values with spaces are allowed there, not in shell).
envget() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true; }
for k in POSTGRES_USER POSTGRES_DB PYBOSSA_REF BACKUP_DIR BACKUP_KEEP_DAYS BACKUP_AGE_RECIPIENT BACKUP_REMOTE; do
  v="$(envget "$k")"; [ -n "$v" ] && [ -z "${!k:-}" ] && eval "$k=\"\$v\""
done

: "${POSTGRES_USER:=pybossa}" "${POSTGRES_DB:=pybossa}"
: "${BACKUP_DIR:=./backups}" "${BACKUP_KEEP_DAYS:=30}" "${BACKUP_AGE_RECIPIENT:=}" "${BACKUP_REMOTE:=}"

stamp="$(date +%Y-%m-%d_%H%M%S)"
dest="$BACKUP_DIR/$stamp"
mkdir -p "$dest"
echo "[$(date -Is)] backup -> $dest"

# 1. Database (pg_dump "custom" format: compressed, selectively restorable).
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$dest/db.dump"
echo "  database: $(du -h "$dest/db.dump" | cut -f1)"

# 2. Uploaded files (avatars, attachments): the "uploads" volume mounted in web.
docker compose exec -T web tar czf - -C /app uploads > "$dest/uploads.tgz"
echo "  uploads: $(du -h "$dest/uploads.tgz" | cut -f1)"

# 3. Server version and configuration fingerprint (no secrets) to know what to restore.
{
  echo "date=$stamp"
  echo "pybossa_ref=${PYBOSSA_REF:-?}"
  echo "image=$(docker compose images web 2>/dev/null | awk 'NR>1{print $2":"$3" "$4}' | tail -1)"
  echo "settings_sha256=$(sha256sum deploy/settings_local.py | cut -d' ' -f1)"
} > "$dest/MANIFEST"

# 4. Encryption (optional but recommended for any off-machine copy).
if [ -n "$BACKUP_AGE_RECIPIENT" ]; then
  command -v age >/dev/null || { echo "age not found (apt install age)" >&2; exit 1; }
  for f in db.dump uploads.tgz; do
    age -r "$BACKUP_AGE_RECIPIENT" -o "$dest/$f.age" "$dest/$f" && rm -f "$dest/$f"
  done
  echo "  encrypted with age"
else
  echo "  WARNING: unencrypted backup (BACKUP_AGE_RECIPIENT not set)"
fi

# 5. Off-machine copy (optional).
if [ -n "$BACKUP_REMOTE" ]; then
  rsync -a --delete-after "$BACKUP_DIR/" "$BACKUP_REMOTE"
  echo "  copied to $BACKUP_REMOTE"
fi

# 6. Local rotation.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$BACKUP_KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true
echo "[$(date -Is)] done"
