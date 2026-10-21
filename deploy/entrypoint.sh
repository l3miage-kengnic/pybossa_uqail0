#!/bin/sh
# Point d'entrée commun aux conteneurs PyBossa (web, worker, scheduler, commandes ponctuelles).
# Rôle unique : attendre que PostgreSQL et Redis répondent, puis lancer la commande demandée.
# Aucune logique applicative ici : tout le reste appartient à PyBossa lui-même.
set -eu

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_USER:=pybossa}"
: "${REDIS_HOST:=redis}"
: "${REDIS_PORT:=6379}"
: "${WAIT_TIMEOUT:=90}"

wait_for() {
    # $1 = libellé, $2 = commande de test (évaluée par sh)
    i=0
    until eval "$2" >/dev/null 2>&1; do
        i=$((i + 1))
        if [ "$i" -ge "$WAIT_TIMEOUT" ]; then
            echo "entrypoint: $1 injoignable après ${WAIT_TIMEOUT} s, abandon." >&2
            exit 1
        fi
        [ "$i" -eq 1 ] && echo "entrypoint: attente de $1..."
        sleep 1
    done
}

wait_for "PostgreSQL ($POSTGRES_HOST)" "pg_isready -q -h '$POSTGRES_HOST' -U '$POSTGRES_USER'"
wait_for "Redis ($REDIS_HOST:$REDIS_PORT)" \
    "python -c \"import redis; redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, socket_connect_timeout=1).ping()\""

exec "$@"
