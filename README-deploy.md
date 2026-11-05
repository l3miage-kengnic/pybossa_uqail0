# U-QUAIL — deploying PyBossa in containers

This repository contains the PyBossa **theme** of the U-QUAIL instance (a customised fork of the
Bloomberg theme) and the **Docker packaging** that assembles a complete instance. The PyBossa server
itself is not in this repository: it is cloned when the image is built, at a precise commit, and
**is never modified**.

> **main, not master.** The server is `bloomberg/pybossa`, branch `main` (Python 3). The `master`
> branch is Python 2.7 and no longer installs. The commit in use is pinned in `.env`
> (`PYBOSSA_REF`): we never track the moving branch.

> **Durability: nothing is cloned from GitHub.** The three Bloomberg repositories the build depends
> on are copied, **without any modification**, into the GRICAD subgroup
> [`ia4health.daisy/pybossa`](https://gricad-gitlab.univ-grenoble-alpes.fr/ia4health.daisy/pybossa):
>
> | GRICAD copy (public) | Bloomberg upstream | Used by |
> |---|---|---|
> | `pybossa` | `bloomberg/pybossa` | the `Dockerfile`, through `PYBOSSA_REPO` in `.env` |
> | `pybossa-js` | `bloomberg/pybossa.js` | submodule `static/js/pybossa` (`.gitmodules`) |
> | `pybossa-player` | `bloomberg/pybossa-player.js` | submodule `static/js/pybossa-player` (`.gitmodules`) |
> | `synchro` (private) | — | monthly CI job that keeps the three copies up to date |
>
> `synchro` pushes **without ever forcing**: if Bloomberg rewrites its history, deletes or closes a
> repository, the job fails (GitLab e-mail) and the copy keeps everything. The copies' branches are
> protected (wildcard `*`, force push forbidden). These are not development forks: the code is the
> upstream code, at the same commit, and `make verify-upstream` proves it (SHA comparison).
> The `SYNC_TOKEN` of `synchro` expires after one year: renew it when it does.

## 1. Architecture

The containers, described in `compose.yaml`:

| Service | Image | Role |
|---|---|---|
| `db` | postgres:16 | database (volume `pgdata`) |
| `redis` | redis:7 | cache and background job queue (volume `redisdata`) |
| `web` | local image `pybossa:dev` | the Flask application, served by gunicorn on internal port 5000 |
| `worker` | same image | runs background jobs: exports, e-mails, statistics |
| `scheduler` | same image | schedules periodic jobs |
| `proxy` | caddy:2 | automatic HTTPS (Let's Encrypt), ports 80 and 443 |
| `mailpit` | `local` profile only | fake mail server, readable at http://localhost:8025 |

Without `worker` and `scheduler`, the application seems to work but no export or e-mail ever completes.

The image (`Dockerfile`) is built in three stages: the theme's JavaScript bundles (Node 18, webpack),
the server's Python dependencies (Python 3.12), and a lightweight final image. This repository's theme
is copied into the image in place of the server's theme submodule.

Packaging files:

```
Dockerfile, .dockerignore, compose.yaml, .env.example, Makefile
deploy/settings_local.py   PyBossa configuration (reads secrets from .env, contains none)
deploy/Caddyfile           HTTPS proxy
deploy/alembic.ini         schema migrations (database address taken from the environment)
deploy/entrypoint.sh       waits for db and redis, then runs the command
scripts/create-admin.py    first administrator account
scripts/backup.sh, restore.sh, smoke-test.sh, cron.example
static/css/uquail.css, static/img/uquail-*.svg, templates/custom/   U-QUAIL look and feel
```

### Data lives in volumes, not in the image

The image holds the **code**; the data (database, uploaded files) lives in Docker **volumes**
(`uquail_pgdata`, `uquail_uploads`, …). `make build`, `make up` and `make down` never touch the
volumes: after a rebuild, `up` recreates the `web`, `worker` and `scheduler` containers from the new
image and plugs them back into the same volumes. This is what makes upgrades safe. Only
`docker compose down -v` deletes the volumes — **permanently**, so back up first.

## 2. Prerequisites

- Docker ≥ 24 with Compose v2 (`docker compose version`).
- A workstation can run everything (Docker Desktop, 4 GB of free RAM): this is the students'
  development environment.
- For the VM: the GRICAD tutorial covers the PERSEUS account, the SSH key, creating the
  machine (2 vCPU, 4 GB), the firewall (22 restricted, 80 and 443 open) and the DNS name. Port 80 is
  required to obtain the certificate.

## 3. First installation — step-by-step checklist

Run every command **in order**, from the repository folder. Steps A and G only concern the VM; the
rest applies to the VM and to a workstation alike.

### A. Docker and permissions (VM only, once)

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git make
sudo usermod -aG docker $USER
```

The second line grants the right to use Docker without `sudo`. **Log out and log back in** for it
to take effect. Check: `docker ps` answers without a permission error.

### B. Get the repository

```bash
git clone https://gricad-gitlab.univ-grenoble-alpes.fr/ia4health.daisy/pybossa/pybossa-uquail-theme.git uquail
cd uquail
git submodule update --init --recursive
```

The submodules (`pybossa.js`, `pybossa-player.js`) come from the GRICAD copies (see "Durability").
Check: `ls static/js/pybossa static/js/pybossa-player` does not show empty folders.

### C. Create and fill in `.env`

```bash
cp .env.example .env
```

Then open `.env` in an editor (`nano .env` on the VM). **The file is commented line by line**: every
variable carries a marker.

| Marker in `.env` | What to do | Variables |
|---|---|---|
| `[REQUIRED]` | mandatory, the instance refuses to start without it | `POSTGRES_PASSWORD`, `SECRET_KEY`, `ITSDANGEROUSKEY`, `CRYPTOPAN_KEY` |
| `[VM]` | the default suits a workstation; adapt it on the VM | `DOMAIN`, `CONTACT_EMAIL`, `ADMINS`, e-mail (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`), `BACKUP_AGE_RECIPIENT`, `BACKUP_REMOTE` |
| `[DECISION]` | do not touch, except for a deliberate upgrade | `PYBOSSA_REF` |
| no marker | the default is fine | `PYBOSSA_REPO`, `POSTGRES_USER`, `POSTGRES_DB`, `PROJECT_URL`, identity (`BRAND`, `TITLE`, `DESCRIPTION`, `COPYRIGHT`), `DEFAULT_LOCALE`, `BACKUP_DIR`, `BACKUP_KEEP_DAYS`, `TZ`, `WEB_WORKERS` |
| `#` at line start (section 9) | optional: remove the `#` to enable | `ACCOUNT_CONFIRMATION_DISABLED`, `LOG_LEVEL`, `BACKUP_AGE_IDENTITY` |

Generate each secret **separately** (four different values):

```bash
openssl rand -hex 32        # POSTGRES_PASSWORD, SECRET_KEY, ITSDANGEROUSKEY
openssl rand -hex 16        # CRYPTOPAN_KEY (exactly 32 characters)
```

On Windows without `openssl`: `python -c "import secrets; print(secrets.token_hex(32))"` (`16` for `CRYPTOPAN_KEY`).

`POSTGRES_PASSWORD` is fixed when the database is created (step E): do not change it afterwards.
A `.env` created before November 2026 lacks the `PYBOSSA_REPO` line: copy it over from `.env.example`,
otherwise the server is cloned from GitHub.

### D. Build the image (10 to 15 minutes the first time)

```bash
make build
```

### E. Start and create the database

```bash
make up           # VM (production)
make up-local     # workstation: adds Mailpit, a fake mail server
make init         # creates the database schema — ONCE in the lifetime of the instance
```

Run only one of the first two lines. **Never** run `make init` again on an instance that holds data.

### F. Create the super administrator account

```bash
make admin
```

The script asks for a user name, full name, e-mail address, then the password (12 characters minimum,
never displayed). The account created is a **super administrator**: it can create projects and other
people's accounts. **Whoever types the command chooses the password**: if a student installs on
someone else's behalf, they create the account with that person's name and address, and the person
then sets their own password through "Forgot password". The script prints the account's **API key**:
note it down (it is used by the smoke test and the orchestrator).

### G. Check (VM)

```bash
make verify-upstream
PYBOSSA_URL=https://<DOMAIN> API_KEY=<API key> make smoke
```

Expected results: `make verify-upstream` ends with an "OK" line stating that the installed server is
identical to `bloomberg/pybossa@<commit>`, then the five smoke-test checks pass. On a workstation
(self-signed certificate): add `INSECURE=1`.

### H. First login

Open `https://<DOMAIN>/`. On a workstation, Caddy issues a self-signed certificate: accept the
browser warning. **You log in with your e-mail address, not your user name.** Forgotten password:
the "Forgot password" link (on a workstation the e-mail arrives in Mailpit, http://localhost:8025) or
`docker compose run --rm -e ACCOUNT=<name> web python /scripts/reset-password.py`. The Bloomberg fork
**has no open sign-up**: further accounts are created from the administration menu ("Register"), and
the person receives their password by e-mail.

Still to do once on the VM: the daily backup (section 4).

### Without `make` (Windows, PowerShell)

`make` does not exist on Windows; the equivalent commands, in the same order:

```bash
docker compose build
docker compose --profile local up -d
docker compose run --rm web python cli.py db_create
docker compose run --rm -e ADMIN_NAME=... -e ADMIN_FULLNAME="..." -e ADMIN_EMAIL=... web python /scripts/create-admin.py
```

Equivalent of `make verify-upstream` (a single line, copy it whole):

```bash
docker compose run --rm -T --no-deps --entrypoint sh web -c 'ref=$(cat /app/PYBOSSA_REF); head=$(git -C /app rev-parse HEAD); echo "installed: $head"; echo "expected:  $ref"; [ "$ref" = "$head" ] || { echo FAILED: different commit; exit 1; }; c=$(git -C /app status --porcelain --untracked-files=no -- . ":!pybossa/themes/default"); [ -z "$c" ] || { echo FAILED: server files modified; echo "$c"; exit 1; }; echo OK: server identical to upstream'
```

The smoke test is a bash script: run it from Git Bash, not PowerShell:
`PYBOSSA_URL=https://localhost API_KEY=<API key> INSECURE=1 ./scripts/smoke-test.sh`.

## 4. Operations

| Need | Command |
|---|---|
| container status | `make ps` |
| logs | `make logs` (or `docker compose logs -f web`) |
| check that everything works | `PYBOSSA_URL=https://<domain> API_KEY=<admin key> make smoke` |
| back up | `make backup` (database + uploads into `backups/`, encrypted if `BACKUP_AGE_RECIPIENT` is set) |
| restore | `make restore DIR=backups/<timestamp>` (replaces everything; asks for confirmation: type `yes`) |
| stop / restart | `make down` / `make up` (data stays in the volumes) |
| upgrade the server | first run the sync by hand (`synchro` project: *Build → Pipelines → Run pipeline*) so that the GRICAD copy contains the new commit; then `make upgrade REF=<sha>`: backs up, rebuilds, migrates the schema, restarts. **Outside campaigns.** |
| prove the server is untouched | `make verify-upstream` |

**Daily backup**: install `scripts/cron.example` in the VM's crontab, set `BACKUP_AGE_RECIPIENT`
(public `age` key; the private key stays off the VM) and `BACKUP_REMOTE` (off-machine copy).
**Test a restore before the first real campaign**: a lost campaign cannot be replayed.

**Smoke test**: if the check verifying that the API refuses requests without a key fails, stop the
instance (`make down`): it would be open to the public.


## 5. Bloomberg fork specifics worth knowing

- A project created through the API must provide: `password` (can be removed afterwards),
  `info.data_classification` (`"L4 - public"` for both fields), `info.kpi` (minutes per task, 0.1 to
  120), `info.product` / `info.subproduct` (from the `PRODUCTS_SUBPRODUCTS` catalogue in the configuration).
- To serve each annotator **their own** tasks in **their own** order: the `user_pref_scheduler`
  scheduler, and on each task `user_pref: {"assign_user": ["<e-mail>"]}` and `priority_0`. A task
  without an assignment is served to every project member: assign everything.
- Access to a project is restricted through `info.project_users` (list of user ids).
- At startup, lines such as `KeyError … Twitter signin disabled`, `Youtube importer not available`,
  etc. are normal: these are third-party plugins, disabled for lack of a key, on purpose.
- The RQ worker needs a long Redis socket timeout; `deploy/settings_local.py` sets it per process.
  A worker restarting every two seconds with "Redis connection timeout" is the symptom of a timeout
  that is too short.

## 6. Personal data and trackers

No resource is loaded from a third party (libraries in `static/vendor/`), no third-party cookie, no
audience measurement. Only three strictly necessary cookies are set; the information banner sets no
cookie. "Cookies" and "Privacy" pages: `templates/custom/`. The privacy policy is a draft to be
validated by the DPO before the first campaign.

## 7. Licence and guarantees

PyBossa is licensed under the GNU AGPL v3. The server is used **unmodified** (`make verify-upstream`
proves it: commit identical to upstream, no file changed). The theme is customised, which its licence
allows and what it is designed for; this repository is public (`PROJECT_URL`, linked in the footer),
which fulfils the obligation to make the source available.

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `worker` restarts in a loop right after installation | database schema missing | `make init` |
| blank page or 500 on first load | Flask-Assets compiles the CSS on the first request | reload; check `docker compose logs web` |
| "You must request a task first!" when submitting an answer | the task was not obtained through `newtask` (or was fetched directly by id) | go through the scheduler with `assign_user` |
| no certificate obtained on the VM | port 80 closed or DNS not yet propagated | open port 80, check `dig +short <domain>` |
| build failing on the VM (apt, pip, npm) | UGA outbound proxy | set `HTTP_PROXY`/`HTTPS_PROXY` for Docker and as `--build-arg` |
| `.env`: "command not found" in a script | value with spaces but no quotes | put the value in double quotes |
