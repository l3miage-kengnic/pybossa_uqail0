#!/usr/bin/env bash
# Vérification rapide d'une instance PyBossa U-QUAIL (tutoriel GRICAD §10).
#
# Usage :
#   PYBOSSA_URL=https://uquail.univ-grenoble-alpes.fr API_KEY=<clé admin> ./scripts/smoke-test.sh
#   PYBOSSA_URL=https://localhost API_KEY=<clé> INSECURE=1 ./scripts/smoke-test.sh   # certificat auto-signé
#
# Cinq contrôles : la page répond ; l'API refuse une requête sans clé ; l'API accepte la clé ;
# les deux processus d'arrière-plan tournent ; le certificat TLS est valide (sauf INSECURE=1).
# Si le DEUXIÈME contrôle échoue, arrêter l'instance : elle serait ouverte au public.
set -uo pipefail

cd "$(dirname "$0")/.."
: "${PYBOSSA_URL:=https://localhost}" "${API_KEY:=}" "${INSECURE:=0}"
curl_opts=(-s -o /dev/null --max-time 20)
[ "$INSECURE" = "1" ] && curl_opts+=(-k)

fail=0
check() {  # $1 libellé, $2 attendu, $3 obtenu
  if [ "$2" = "$3" ]; then printf "  OK      %-48s %s\n" "$1" "$3"
  else printf "  ECHEC   %-48s obtenu %s, attendu %s\n" "$1" "$3" "$2"; fail=1; fi
}

echo "Instance : $PYBOSSA_URL"
code=$(curl "${curl_opts[@]}" -L -w '%{http_code}' "$PYBOSSA_URL/")
check "1. page d'accueil" 200 "$code"

code=$(curl "${curl_opts[@]}" -w '%{http_code}' "$PYBOSSA_URL/api/project")
check "2. API sans clé refusée (401)" 401 "$code"
if [ "$code" != "401" ]; then echo "  !! L'API répond sans clé : ARRÊTER L'INSTANCE (docker compose down)"; fi

if [ -n "$API_KEY" ]; then
  code=$(curl "${curl_opts[@]}" -w '%{http_code}' "$PYBOSSA_URL/api/project?api_key=$API_KEY")
  check "3. API avec clé acceptée (200)" 200 "$code"
else
  echo "  SAUT    3. API avec clé (API_KEY non fourni)"
fi

for svc in worker scheduler; do
  state=$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$svc" '$1==s{print $2}')
  check "4. service $svc en cours d'exécution" running "${state:-absent}"
done

if [ "$INSECURE" = "1" ]; then
  echo "  SAUT    5. certificat TLS (INSECURE=1)"
else
  if curl -s -o /dev/null --max-time 20 "$PYBOSSA_URL/"; then check "5. certificat TLS valide" ok ok
  else check "5. certificat TLS valide" ok "invalide ou injoignable"; fi
fi

if [ "$fail" = "0" ]; then echo "Résultat : tout est en ordre."; else echo "Résultat : au moins un contrôle a échoué."; fi
exit "$fail"
