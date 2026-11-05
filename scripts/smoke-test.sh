#!/usr/bin/env bash
# Quick check of a U-QUAIL PyBossa instance (GRICAD tutorial §10).
#
# Usage:
#   PYBOSSA_URL=https://uquail.univ-grenoble-alpes.fr API_KEY=<admin key> ./scripts/smoke-test.sh
#   PYBOSSA_URL=https://localhost API_KEY=<key> INSECURE=1 ./scripts/smoke-test.sh   # self-signed certificate
#
# Five checks: the page responds; the API refuses a request without a key; the API accepts the key;
# the two background processes are running; the TLS certificate is valid (unless INSECURE=1).
# If the SECOND check fails, stop the instance: it would be open to the public.
set -uo pipefail

cd "$(dirname "$0")/.."
: "${PYBOSSA_URL:=https://localhost}" "${API_KEY:=}" "${INSECURE:=0}"
curl_opts=(-s -o /dev/null --max-time 20)
[ "$INSECURE" = "1" ] && curl_opts+=(-k)

fail=0
check() {  # $1 label, $2 expected, $3 actual
  if [ "$2" = "$3" ]; then printf "  OK      %-48s %s\n" "$1" "$3"
  else printf "  FAIL    %-48s got %s, expected %s\n" "$1" "$3" "$2"; fail=1; fi
}

echo "Instance: $PYBOSSA_URL"
code=$(curl "${curl_opts[@]}" -L -w '%{http_code}' "$PYBOSSA_URL/")
check "1. home page" 200 "$code"

code=$(curl "${curl_opts[@]}" -w '%{http_code}' "$PYBOSSA_URL/api/project")
check "2. API without key refused (401)" 401 "$code"
if [ "$code" != "401" ]; then echo "  !! The API responds without a key: STOP THE INSTANCE (docker compose down)"; fi

if [ -n "$API_KEY" ]; then
  code=$(curl "${curl_opts[@]}" -w '%{http_code}' "$PYBOSSA_URL/api/project?api_key=$API_KEY")
  check "3. API with key accepted (200)" 200 "$code"
else
  echo "  SKIP    3. API with key (API_KEY not provided)"
fi

for svc in worker scheduler; do
  state=$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$svc" '$1==s{print $2}')
  check "4. service $svc running" running "${state:-absent}"
done

if [ "$INSECURE" = "1" ]; then
  echo "  SKIP    5. TLS certificate (INSECURE=1)"
else
  if curl -s -o /dev/null --max-time 20 "$PYBOSSA_URL/"; then check "5. valid TLS certificate" ok ok
  else check "5. valid TLS certificate" ok "invalid or unreachable"; fi
fi

if [ "$fail" = "0" ]; then echo "Result: everything is in order."; else echo "Result: at least one check failed."; fi
exit "$fail"
