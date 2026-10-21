#!/usr/bin/env bash
# Sauvegarde de l'instance PyBossa U-QUAIL : base PostgreSQL + fichiers envoyés (uploads).
#
# Usage (depuis le dossier du dépôt, conteneurs démarrés) :
#   ./scripts/backup.sh                  # dans ./backups/<horodatage>/
#   BACKUP_DIR=/mnt/sauvegardes ./scripts/backup.sh
#
# Variables lues dans .env (ou l'environnement) :
#   BACKUP_DIR            dossier de destination (défaut : ./backups)
#   BACKUP_KEEP_DAYS      rotation : supprime les sauvegardes plus vieilles que N jours (défaut : 30)
#   BACKUP_AGE_RECIPIENT  clé publique "age" : si définie, chaque fichier est chiffré (.age)
#   BACKUP_REMOTE         destination rsync (ex. user@hote:/chemin/) : si définie, copie hors machine
#
# Une campagne perdue ne se rejoue pas : planifier ce script chaque nuit (voir scripts/cron.example)
# et tester la restauration au moins une fois (scripts/restore.sh) avant la première campagne réelle.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash (Windows) : ne pas convertir les chemins Linux passés aux conteneurs

cd "$(dirname "$0")/.."
# Lecture de .env sans l'exécuter (des valeurs avec espaces y sont permises, pas en shell).
envget() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true; }
for k in POSTGRES_USER POSTGRES_DB PYBOSSA_REF BACKUP_DIR BACKUP_KEEP_DAYS BACKUP_AGE_RECIPIENT BACKUP_REMOTE; do
  v="$(envget "$k")"; [ -n "$v" ] && [ -z "${!k:-}" ] && eval "$k=\"\$v\""
done

: "${POSTGRES_USER:=pybossa}" "${POSTGRES_DB:=pybossa}"
: "${BACKUP_DIR:=./backups}" "${BACKUP_KEEP_DAYS:=30}" "${BACKUP_AGE_RECIPIENT:=}" "${BACKUP_REMOTE:=}"

stamp="$(date +%Y-%m-%d_%H%M%S)"
dest="$BACKUP_DIR/$stamp"
mkdir -p "$dest"
echo "[$(date -Is)] sauvegarde -> $dest"

# 1. Base de données (format "custom" de pg_dump : compressé, restaurable sélectivement).
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$dest/db.dump"
echo "  base : $(du -h "$dest/db.dump" | cut -f1)"

# 2. Fichiers envoyés (avatars, pièces jointes) : le volume "uploads" monté dans web.
docker compose exec -T web tar czf - -C /app uploads > "$dest/uploads.tgz"
echo "  uploads : $(du -h "$dest/uploads.tgz" | cut -f1)"

# 3. Version du serveur et empreinte de la configuration (pas de secret) pour savoir quoi restaurer.
{
  echo "date=$stamp"
  echo "pybossa_ref=${PYBOSSA_REF:-?}"
  echo "image=$(docker compose images web 2>/dev/null | awk 'NR>1{print $2":"$3" "$4}' | tail -1)"
  echo "settings_sha256=$(sha256sum deploy/settings_local.py | cut -d' ' -f1)"
} > "$dest/MANIFEST"

# 4. Chiffrement (optionnel mais recommandé pour toute copie hors machine).
if [ -n "$BACKUP_AGE_RECIPIENT" ]; then
  command -v age >/dev/null || { echo "age introuvable (apt install age)" >&2; exit 1; }
  for f in db.dump uploads.tgz; do
    age -r "$BACKUP_AGE_RECIPIENT" -o "$dest/$f.age" "$dest/$f" && rm -f "$dest/$f"
  done
  echo "  chiffré avec age"
else
  echo "  AVERTISSEMENT : sauvegarde non chiffrée (BACKUP_AGE_RECIPIENT non défini)"
fi

# 5. Copie hors machine (optionnelle).
if [ -n "$BACKUP_REMOTE" ]; then
  rsync -a --delete-after "$BACKUP_DIR/" "$BACKUP_REMOTE"
  echo "  copié vers $BACKUP_REMOTE"
fi

# 6. Rotation locale.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$BACKUP_KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true
echo "[$(date -Is)] terminé"
