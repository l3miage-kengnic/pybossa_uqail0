#!/usr/bin/env bash
# Restauration d'une sauvegarde produite par scripts/backup.sh.
#
# Usage (depuis le dossier du dépôt, conteneurs db et redis démarrés) :
#   ./scripts/restore.sh backups/2026-10-21_030000          # demande confirmation
#   ./scripts/restore.sh backups/2026-10-21_030000 --yes    # sans confirmation (scripts)
#
# Ce que fait le script :
#   1. arrête web, worker et scheduler (la base ne doit plus être écrite) ;
#   2. remplace ENTIÈREMENT la base par celle de la sauvegarde ;
#   3. remplace le contenu du volume "uploads" ;
#   4. relance les services.
# Les fichiers .age sont déchiffrés à la volée (clé privée : BACKUP_AGE_IDENTITY, défaut ~/.config/age/key.txt).
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows) : ne pas convertir les chemins Linux passés aux conteneurs

cd "$(dirname "$0")/.."
# Lecture de .env sans l'exécuter (des valeurs avec espaces y sont permises, pas en shell).
envget() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true; }
for k in POSTGRES_USER POSTGRES_DB BACKUP_AGE_IDENTITY; do
  v="$(envget "$k")"; [ -n "$v" ] && [ -z "${!k:-}" ] && eval "$k=\"\$v\""
done
: "${POSTGRES_USER:=pybossa}" "${POSTGRES_DB:=pybossa}" "${BACKUP_AGE_IDENTITY:=$HOME/.config/age/key.txt}"

src="${1:-}"; confirm="${2:-}"
[ -d "$src" ] || { echo "usage : $0 <dossier de sauvegarde> [--yes]" >&2; exit 1; }
[ -f "$src/MANIFEST" ] && { echo "--- MANIFEST ---"; cat "$src/MANIFEST"; echo "----------------"; }

decrypt() {  # $1 = nom de fichier (db.dump | uploads.tgz) ; écrit sur stdout
  if [ -f "$src/$1.age" ]; then
    command -v age >/dev/null || { echo "age introuvable" >&2; exit 1; }
    age -d -i "$BACKUP_AGE_IDENTITY" "$src/$1.age"
  elif [ -f "$src/$1" ]; then
    cat "$src/$1"
  else
    echo "fichier manquant : $src/$1" >&2; exit 1
  fi
}

if [ "$confirm" != "--yes" ]; then
  echo "ATTENTION : la base '$POSTGRES_DB' et les uploads actuels vont être REMPLACÉS par $src."
  read -r -p "Continuer ? (taper 'oui') " answer
  [ "$answer" = "oui" ] || { echo "abandon"; exit 1; }
fi

echo "[1/4] arrêt des services applicatifs"
docker compose stop web worker scheduler >/dev/null

echo "[2/4] restauration de la base"
# --clean --if-exists : supprime les objets existants avant de les recréer ; --no-owner : indépendant du rôle d'origine.
decrypt db.dump | docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists --no-owner --no-privileges --exit-on-error

echo "[3/4] restauration des uploads"
decrypt uploads.tgz | docker compose run --rm -T --no-deps --entrypoint sh web -c \
    'rm -rf /app/uploads/* && tar xzf - -C /app && echo "  uploads : $(find /app/uploads -type f | wc -l) fichier(s)"'

echo "[4/4] redémarrage"
docker compose up -d web worker scheduler >/dev/null
echo "restauration terminée ; vérifier avec ./scripts/smoke-test.sh"
