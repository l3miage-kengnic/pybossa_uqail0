# Operations shortcuts for the U-QUAIL PyBossa instance (GRICAD tutorial §9-11).
# On Windows without make: the equivalent commands are in README-deploy.md.
#
#   make build     builds the image (server pinned to PYBOSSA_REF, theme from this repository)
#   make init      creates the database schema — ONLY ONCE in the lifetime of the instance
#   make admin     creates the first administrator account (interactive)
#   make up        starts everything (production: without Mailpit)
#   make up-local  starts everything + Mailpit (workstation)
#   make down      stops everything (data stays in the volumes)
#   make ps        container status
#   make logs      follows the logs (Ctrl+C to exit)
#   make shell     shell in a throwaway web container
#   make smoke     five health checks
#   make backup    backs up database + uploads (see scripts/backup.sh)
#   make restore DIR=backups/<timestamp>
#   make upgrade REF=<sha>   changes the server version, rebuilds, migrates the schema
#   make verify-upstream     proves that the installed server is identical to upstream

SHELL := /bin/bash
COMPOSE := docker compose
ENV_FILE := .env

.PHONY: help build init admin up up-local down ps logs shell smoke backup restore upgrade verify-upstream

help:
	@sed -n '2,20p' Makefile | sed 's/^# \{0,1\}//'

build:
	$(COMPOSE) build

init:
	$(COMPOSE) run --rm web python cli.py db_create

admin:
	@read -p "Username (lowercase, no spaces): " n; read -p "Full name: " f; read -p "Email: " e; \
	$(COMPOSE) run --rm -e ADMIN_NAME="$$n" -e ADMIN_FULLNAME="$$f" -e ADMIN_EMAIL="$$e" web python /scripts/create-admin.py

up:
	$(COMPOSE) up -d

up-local:
	$(COMPOSE) --profile local up -d

down:
	$(COMPOSE) --profile local down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail 100

shell:
	$(COMPOSE) run --rm --entrypoint bash web

smoke:
	./scripts/smoke-test.sh

backup:
	./scripts/backup.sh

restore:
	@test -n "$(DIR)" || { echo "usage: make restore DIR=backups/<timestamp>"; exit 1; }
	./scripts/restore.sh "$(DIR)"

upgrade:
	@test -n "$(REF)" || { echo "usage: make upgrade REF=<bloomberg/pybossa commit sha>"; exit 1; }
	@echo "Upgrading to $(REF): do this OUTSIDE a campaign, after a backup."
	./scripts/backup.sh
	sed -i.bak 's/^PYBOSSA_REF=.*/PYBOSSA_REF=$(REF)/' $(ENV_FILE) && rm -f $(ENV_FILE).bak
	$(COMPOSE) build
	$(COMPOSE) run --rm web alembic upgrade head
	$(COMPOSE) up -d
	./scripts/smoke-test.sh || true

verify-upstream:
	@$(COMPOSE) run --rm -T --no-deps --entrypoint sh web -c '\
	  ref=$$(cat /app/PYBOSSA_REF); head=$$(git -C /app rev-parse HEAD); \
	  echo "installed commit: $$head"; echo "expected commit : $$ref"; \
	  [ "$$ref" = "$$head" ] || { echo "FAILED: different commit"; exit 1; }; \
	  changes=$$(git -C /app status --porcelain --untracked-files=no -- . ":!pybossa/themes/default"); \
	  if [ -n "$$changes" ]; then echo "FAILED: modified server files:"; echo "$$changes"; exit 1; fi; \
	  echo "OK: the installed server is identical to bloomberg/pybossa@$$ref (theme excluded)."'
