# Raccourcis d'exploitation de l'instance PyBossa U-QUAIL (tutoriel GRICAD §9-11).
# Sur Windows sans make : les commandes équivalentes sont dans README-deploy.md.
#
#   make build     construit l'image (serveur épinglé à PYBOSSA_REF, thème de ce dépôt)
#   make init      crée le schéma de la base — UNE SEULE FOIS dans la vie de l'instance
#   make admin     crée le premier compte administrateur (interactif)
#   make up        démarre tout (production : sans Mailpit)
#   make up-local  démarre tout + Mailpit (poste de travail)
#   make down      arrête tout (les données restent dans les volumes)
#   make ps        état des conteneurs
#   make logs      journaux en continu (Ctrl+C pour sortir)
#   make shell     shell dans un conteneur web jetable
#   make smoke     cinq contrôles de bon fonctionnement
#   make backup    sauvegarde base + uploads (voir scripts/backup.sh)
#   make restore DIR=backups/<horodatage>
#   make upgrade REF=<sha>   change de version du serveur, reconstruit, migre le schéma
#   make verify-upstream     prouve que le serveur installé est identique à l'amont

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
	@read -p "Nom d'utilisateur (minuscules, sans espace) : " n; read -p "Nom complet : " f; read -p "E-mail : " e; \
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
	@test -n "$(DIR)" || { echo "usage : make restore DIR=backups/<horodatage>"; exit 1; }
	./scripts/restore.sh "$(DIR)"

upgrade:
	@test -n "$(REF)" || { echo "usage : make upgrade REF=<sha du commit bloomberg/pybossa>"; exit 1; }
	@echo "Mise à jour vers $(REF) : à faire HORS campagne, après une sauvegarde."
	./scripts/backup.sh
	sed -i.bak 's/^PYBOSSA_REF=.*/PYBOSSA_REF=$(REF)/' $(ENV_FILE) && rm -f $(ENV_FILE).bak
	$(COMPOSE) build
	$(COMPOSE) run --rm web alembic upgrade head
	$(COMPOSE) up -d
	./scripts/smoke-test.sh || true

verify-upstream:
	@$(COMPOSE) run --rm -T --no-deps --entrypoint sh web -c '\
	  ref=$$(cat /app/PYBOSSA_REF); head=$$(git -C /app rev-parse HEAD); \
	  echo "commit installé : $$head"; echo "commit attendu  : $$ref"; \
	  [ "$$ref" = "$$head" ] || { echo "ECHEC : commit différent"; exit 1; }; \
	  changes=$$(git -C /app status --porcelain --untracked-files=no -- . ":!pybossa/themes/default"); \
	  if [ -n "$$changes" ]; then echo "ECHEC : fichiers du serveur modifiés :"; echo "$$changes"; exit 1; fi; \
	  echo "OK : le serveur installé est identique à bloomberg/pybossa@$$ref (hors thème)."'
