# U-QUAIL — déploiement de PyBossa en conteneurs

Ce dépôt contient le **thème** PyBossa de l'instance U-QUAIL (fork du thème Bloomberg, personnalisé)
et le **packaging Docker** qui assemble une instance complète. Le serveur PyBossa lui-même n'est pas
dans ce dépôt : il est cloné à la construction de l'image, à un commit précis, et **n'est jamais modifié**.

> **main, pas master.** Le serveur est `bloomberg/pybossa`, branche `main` (Python 3). La branche
> `master` est en Python 2.7 et ne s'installe plus. Le commit utilisé est épinglé dans `.env`
> (`PYBOSSA_REF`) : on ne suit jamais la branche mouvante.

## 1. Architecture

Six conteneurs, décrits dans `compose.yaml` :

| Service | Image | Rôle |
|---|---|---|
| `db` | postgres:16 | base de données (volume `pgdata`) |
| `redis` | redis:7 | cache et file des travaux d'arrière-plan (volume `redisdata`) |
| `web` | image locale `pybossa:dev` | l'application Flask, servie par gunicorn sur le port 5000 interne |
| `worker` | même image | exécute les travaux : exports, courriels, statistiques |
| `scheduler` | même image | programme les travaux périodiques |
| `proxy` | caddy:2 | HTTPS automatique (Let's Encrypt), ports 80 et 443 |
| `mailpit` | profil `local` seulement | faux serveur de courriel, lecture sur http://localhost:8025 |

Sans `worker` et `scheduler`, l'application semble fonctionner mais aucun export ni courriel n'aboutit.

L'image (`Dockerfile`) se construit en trois étapes : bundles JavaScript du thème (Node 18, webpack),
dépendances Python du serveur (Python 3.12), image finale légère. Le thème de ce dépôt est copié
dans l'image à la place du sous-module du serveur.

Fichiers du packaging :

```
Dockerfile, .dockerignore, compose.yaml, .env.example, Makefile
deploy/settings_local.py   configuration PyBossa (lit les secrets dans .env, aucun secret dedans)
deploy/Caddyfile           proxy HTTPS
deploy/alembic.ini         migrations de schéma (adresse de la base via l'environnement)
deploy/entrypoint.sh       attend db et redis, puis lance la commande
scripts/create-admin.py    premier compte administrateur
scripts/backup.sh, restore.sh, smoke-test.sh, cron.example
static/css/uquail.css, static/img/uquail-*.svg, templates/custom/   habillage U-QUAIL
```

## 2. Prérequis

- Docker ≥ 24 avec Compose v2 (`docker compose version`). Sur la VM : `sudo apt install docker.io docker-compose-v2 git make`.
- Un poste de travail peut tout faire tourner (Docker Desktop, 4 Go de RAM libres) : c'est l'environnement de développement des étudiants.
- Pour la VM : voir le tutoriel GRICAD (`doc/`, non versionné) pour la création de la machine, le pare-feu (22 restreint, 80 et 443 ouverts) et le nom DNS. Le port 80 est indispensable à l'obtention du certificat.

## 3. Première installation

```bash
git clone <ce dépôt> uquail && cd uquail
git submodule update --init --recursive     # pybossa.js et pybossa-player.js (thème)
cp .env.example .env
```

Renseigner `.env` : le domaine (`DOMAIN`, `localhost` sur un poste), les quatre secrets
(`POSTGRES_PASSWORD`, `SECRET_KEY`, `ITSDANGEROUSKEY` avec `openssl rand -hex 32`, `CRYPTOPAN_KEY`
avec `openssl rand -hex 16`), le courriel sortant, les adresses d'administration. Puis :

```bash
make build        # 10 à 15 minutes la première fois
make up-local     # poste de travail (make up sur la VM)
make init         # crée le schéma de la base : UNE SEULE FOIS
make admin        # premier compte administrateur (mot de passe demandé au clavier)
```

Ouvrir `https://<DOMAIN>/`. Sur un poste, Caddy émet un certificat auto-signé : accepter l'avertissement
du navigateur. **On se connecte avec son adresse e-mail, pas avec son nom d'utilisateur.** Mot de
passe oublié : lien « Forgot password » (sur un poste, le courriel arrive dans Mailpit,
http://localhost:8025) ou `docker compose run --rm -e ACCOUNT=<nom> web python /scripts/reset-password.py`. Le fork Bloomberg **n'a pas d'inscription libre** : les comptes suivants se créent
depuis le menu d'administration (« Register »), et la personne reçoit son mot de passe par courriel.

Sans `make` (Windows), les commandes équivalentes sont :

```bash
docker compose build
docker compose --profile local up -d
docker compose run --rm web python cli.py db_create
docker compose run --rm -e ADMIN_NAME=... -e ADMIN_FULLNAME="..." -e ADMIN_EMAIL=... web python /scripts/create-admin.py
```

## 4. Exploitation

| Besoin | Commande |
|---|---|
| état des conteneurs | `make ps` |
| journaux | `make logs` (ou `docker compose logs -f web`) |
| vérifier que tout va bien | `PYBOSSA_URL=https://<domaine> API_KEY=<clé admin> make smoke` |
| sauvegarder | `make backup` (base + uploads dans `backups/`, chiffré si `BACKUP_AGE_RECIPIENT` est défini) |
| restaurer | `make restore DIR=backups/<horodatage>` (remplace tout, demande confirmation) |
| arrêter / relancer | `make down` / `make up` (les données restent dans les volumes) |
| mettre à jour le serveur | `make upgrade REF=<sha>` : sauvegarde, reconstruit, migre le schéma, relance. **Hors campagne.** |
| prouver que le serveur est intact | `make verify-upstream` |

**Sauvegarde quotidienne** : installer `scripts/cron.example` dans la crontab de la VM, renseigner
`BACKUP_AGE_RECIPIENT` (clé publique `age`, la clé privée reste hors de la VM) et `BACKUP_REMOTE`
(copie hors machine). **Tester une restauration avant la première campagne réelle** : une campagne
perdue ne se rejoue pas.

**Smoke test** : si le contrôle « API sans clé refusée » échoue, arrêter l'instance (`make down`) :
elle serait ouverte au public.


## 6. Spécificités du fork Bloomberg à connaître

- Un projet créé par l'API doit fournir : `password` (retirable ensuite), `info.data_classification`
  (`"L4 - public"` pour les deux champs), `info.kpi` (minutes par tâche, 0,1 à 120),
  `info.product` / `info.subproduct` (catalogue `PRODUCTS_SUBPRODUCTS` de la configuration).
- Pour servir à chaque annotateur **ses** tâches dans **son** ordre : ordonnanceur
  `user_pref_scheduler`, et sur chaque tâche `user_pref: {"assign_user": ["<e-mail>"]}` et
  `priority_0`. Une tâche sans affectation est servie à tout membre du projet : tout assigner.
- L'accès à un projet se restreint par `info.project_users` (liste d'identifiants d'utilisateurs).
- Au démarrage, les lignes `KeyError … Twitter signin disabled`, `Youtube importer not available`,
  etc. sont normales : ce sont les greffons tiers, désactivés faute de clé, et c'est voulu.
- Le worker RQ exige un délai socket Redis long ; `deploy/settings_local.py` le règle selon le
  processus. Un worker qui redémarre toutes les deux secondes avec « Redis connection timeout » est
  le symptôme d'un réglage trop court.

## 7. Données personnelles et traceurs

Aucune ressource n'est chargée depuis un tiers (bibliothèques dans `static/vendor/`), aucun cookie
tiers, pas de mesure d'audience. Seuls trois cookies strictement nécessaires sont posés ; la bannière
d'information ne pose pas de cookie. Pages « Cookies » et « Confidentialité » : `templates/custom/`.
La politique de confidentialité est un projet à faire valider par le DPO avant la première campagne.

## 8. Licence et garanties

PyBossa est sous GNU AGPL v3. Le serveur est utilisé **sans modification** (`make verify-upstream`
le prouve : commit identique à l'amont, aucun fichier changé). Le thème, lui, est personnalisé, ce
que sa licence permet et ce pour quoi il est conçu ; ce dépôt est public (`PROJECT_URL`, lien en
pied de page), ce qui satisfait l'obligation de mise à disposition des sources.

## 9. Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| `worker` redémarre en boucle juste après l'installation | schéma de base absent | `make init` |
| page blanche ou 500 au premier chargement | Flask-Assets compile le CSS au premier appel | recharger ; vérifier `docker compose logs web` |
| « You must request a task first! » à l'envoi d'une réponse | la tâche n'a pas été obtenue par `newtask` (ou appel direct par identifiant) | passer par l'ordonnanceur avec `assign_user` |
| certificat non obtenu sur la VM | port 80 fermé ou DNS pas encore propagé | ouvrir le port 80, vérifier `dig +short <domaine>` |
| construction qui échoue sur la VM (apt, pip, npm) | proxy sortant de l'UGA | renseigner `HTTP_PROXY`/`HTTPS_PROXY` pour Docker et en `--build-arg` |
| `.env` : « command not found » dans un script | valeur avec espaces sans guillemets | mettre la valeur entre guillemets doubles |
