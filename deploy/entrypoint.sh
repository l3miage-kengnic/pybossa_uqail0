#!/bin/sh
# Common entry point for the PyBossa containers (web, worker, scheduler, one-off commands).
# Single role: wait until PostgreSQL and Redis respond, then run the requested command.
# No application logic here: everything else belongs to PyBossa itself.
set -eu

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_USER:=pybossa}"
: "${REDIS_HOST:=redis}"
: "${REDIS_PORT:=6379}"
: "${WAIT_TIMEOUT:=90}"

wait_for() {
    # $1 = label, $2 = test command (evaluated by sh)
    i=0
    until eval "$2" >/dev/null 2>&1; do
        i=$((i + 1))
        if [ "$i" -ge "$WAIT_TIMEOUT" ]; then
            echo "entrypoint: $1 unreachable after ${WAIT_TIMEOUT} s, giving up." >&2
            exit 1
        fi
        [ "$i" -eq 1 ] && echo "entrypoint: waiting for $1..."
        sleep 1
    done
}

wait_for "PostgreSQL ($POSTGRES_HOST)" "pg_isready -q -h '$POSTGRES_HOST' -U '$POSTGRES_USER'"
wait_for "Redis ($REDIS_HOST:$REDIS_PORT)" \
    "python -c \"import redis; redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, socket_connect_timeout=1).ping()\""

exec "$@"
