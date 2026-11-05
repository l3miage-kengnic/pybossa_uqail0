#!/usr/bin/env bash
# Restore a backup produced by scripts/backup.sh.
#
# Usage (from the repository folder, db and redis containers running):
#   ./scripts/restore.sh backups/2026-10-21_030000          # asks for confirmation
#   ./scripts/restore.sh backups/2026-10-21_030000 --yes    # without confirmation (scripts)
#
# What the script does:
#   1. stops web, worker and scheduler (the database must no longer be written to);
#   2. ENTIRELY replaces the database with the one from the backup;
#   3. replaces the contents of the "uploads" volume;
#   4. restarts the services.
# .age files are decrypted on the fly (private key: BACKUP_AGE_IDENTITY, default ~/.config/age/key.txt).
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows): do not convert Linux paths passed to containers

cd "$(dirname "$0")/.."
# Read .env without executing it (values with spaces are allowed there, not in shell).
envget() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true; }
for k in POSTGRES_USER POSTGRES_DB BACKUP_AGE_IDENTITY; do
  v="$(envget "$k")"; [ -n "$v" ] && [ -z "${!k:-}" ] && eval "$k=\"\$v\""
done
: "${POSTGRES_USER:=pybossa}" "${POSTGRES_DB:=pybossa}" "${BACKUP_AGE_IDENTITY:=$HOME/.config/age/key.txt}"

src="${1:-}"; confirm="${2:-}"
[ -d "$src" ] || { echo "usage: $0 <backup folder> [--yes]" >&2; exit 1; }
[ -f "$src/MANIFEST" ] && { echo "--- MANIFEST ---"; cat "$src/MANIFEST"; echo "----------------"; }

decrypt() {  # $1 = file name (db.dump | uploads.tgz); writes to stdout
  if [ -f "$src/$1.age" ]; then
    command -v age >/dev/null || { echo "age not found" >&2; exit 1; }
    age -d -i "$BACKUP_AGE_IDENTITY" "$src/$1.age"
  elif [ -f "$src/$1" ]; then
    cat "$src/$1"
  else
    echo "missing file: $src/$1" >&2; exit 1
  fi
}

if [ "$confirm" != "--yes" ]; then
  echo "WARNING: the '$POSTGRES_DB' database and the current uploads will be REPLACED by $src."
  read -r -p "Continue? (type 'yes') " answer
  [ "$answer" = "yes" ] || { echo "aborted"; exit 1; }
fi

echo "[1/4] stopping application services"
docker compose stop web worker scheduler >/dev/null

echo "[2/4] restoring the database"
# --clean --if-exists: drops existing objects before recreating them; --no-owner: independent of the original role.
decrypt db.dump | docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists --no-owner --no-privileges --exit-on-error

echo "[3/4] restoring uploads"
decrypt uploads.tgz | docker compose run --rm -T --no-deps --entrypoint sh web -c \
    'rm -rf /app/uploads/* && tar xzf - -C /app && echo "  uploads: $(find /app/uploads -type f | wc -l) file(s)"'

echo "[4/4] restarting"
docker compose up -d web worker scheduler >/dev/null
echo "restore complete; check with ./scripts/smoke-test.sh"
