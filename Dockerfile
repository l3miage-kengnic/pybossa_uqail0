# syntax=docker/dockerfile:1.7
#
# Image PyBossa pour U-QUAIL.
#
#   - Serveur : bloomberg/pybossa, branche main, cloné au commit exact PYBOSSA_REF.
#     Le code du serveur n'est jamais modifié ; il n'est pas non plus stocké dans ce dépôt.
#   - Thème   : ce dépôt (templates/, static/, translations/), copié tel quel dans
#     pybossa/themes/default, après génération des bundles JavaScript par webpack.
#
# Trois étapes :
#   1. theme-assets : Node 18, construit les bundles du thème (static/js/gen/) et
#      réécrit les templates qui les référencent (même procédé que la CI du thème).
#   2. builder      : Python 3.12, clone le serveur et compile les dépendances dans /venv.
#   3. image finale : Python 3.12 "slim", seulement les bibliothèques d'exécution.
#
# Construction :  docker build --build-arg PYBOSSA_REF=<sha> -t pybossa .
# (compose.yaml passe PYBOSSA_REF depuis .env automatiquement)

ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=18

########################################################################
# Étape 1 : bundles webpack du thème
########################################################################
FROM node:${NODE_VERSION}-bookworm AS theme-assets

# Tout le thème : webpack écrit dans static/js/gen/ et dans templates/
COPY . /theme
WORKDIR /theme/static/src

# Même recette que .github/workflows/nodejs.yml du thème :
#  - le paquet @dtwebservices/task-presenter-components n'est pas sur le registre npm,
#    il se télécharge depuis un bucket S3 public (version lue dans package.json) ;
#  - la chaîne babel 6 exige le fournisseur OpenSSL "legacy" sous Node 17+.
ENV NODE_OPTIONS=--openssl-legacy-provider
RUN TPV=$(node -p "require('./package.json').dependencies['@dtwebservices/task-presenter-components']") \
 && npm install --no-audit --no-fund \
      "https://s3.amazonaws.com/cf-s3uploads/pybv/${TPV}/task-presenter-components.tgz" \
 && npm run build \
 && rm -rf node_modules

########################################################################
# Étape 2 : serveur PyBossa + dépendances Python compilées
########################################################################
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG PYBOSSA_REPO=https://github.com/bloomberg/pybossa.git
ARG PYBOSSA_REF
RUN test -n "$PYBOSSA_REF" \
 || { echo "ERREUR : PYBOSSA_REF manquant (--build-arg PYBOSSA_REF=<sha du commit>)" >&2; exit 1; }

# Bibliothèques de développement nécessaires à la compilation des dépendances
# (liste de la CI Bloomberg + libmagic/libjpeg pour python-magic et Pillow).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential git pkg-config ca-certificates \
      libpq-dev \
      libxml2-dev libxslt1-dev libxmlsec1-dev libxmlsec1-openssl \
      libsasl2-dev libldap2-dev \
      libssl-dev libffi-dev libkrb5-dev \
      libjpeg-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# Clone peu profond du serveur, au commit exact et à rien d'autre.
# Le dossier .git est conservé : il permet de prouver plus tard que le code
# installé est identique à l'amont (cible `make verify-upstream`).
RUN git init -q /app \
 && cd /app \
 && git remote add origin "$PYBOSSA_REPO" \
 && git fetch -q --depth 1 origin "$PYBOSSA_REF" \
 && git checkout -q --detach FETCH_HEAD \
 && echo "$PYBOSSA_REF" > /app/PYBOSSA_REF

WORKDIR /app

# requirements.txt de l'amont contient "-e ." : installation en mode éditable,
# le paquet reste dans /app. gunicorn est le serveur WSGI ajouté par le packaging.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /venv \
 && /venv/bin/pip install --upgrade pip wheel setuptools \
 && /venv/bin/pip install -r requirements.txt gunicorn==23.0.0

########################################################################
# Étape 3 : image finale
########################################################################
FROM python:${PYTHON_VERSION}-slim-bookworm

# Bibliothèques partagées d'exécution (pendants "non -dev" de l'étape 2),
# postgresql-client pour pg_isready et les sauvegardes, git pour verify-upstream.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git postgresql-client \
      libpq5 libxml2 libxslt1.1 libxmlsec1-openssl \
      libldap-2.5-0 libsasl2-2 libkrb5-3 libgssapi-krb5-2 \
      libmagic1 libjpeg62-turbo \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 1000 --create-home --shell /usr/sbin/nologin pybossa \
 && git config --system --add safe.directory /app

COPY --from=builder /venv /venv
COPY --from=builder /app  /app

# Le thème : celui de ce dépôt, avec les bundles générés à l'étape 1.
# Le sous-module vide de l'amont est remplacé.
RUN rm -rf /app/pybossa/themes/default
COPY --from=theme-assets /theme/templates    /app/pybossa/themes/default/templates
COPY --from=theme-assets /theme/static       /app/pybossa/themes/default/static
COPY --from=theme-assets /theme/translations /app/pybossa/themes/default/translations
COPY --from=theme-assets /theme/info.json    /app/pybossa/themes/default/info.json

COPY deploy/alembic.ini   /app/alembic.ini
COPY deploy/entrypoint.sh /usr/local/bin/pybossa-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/pybossa-entrypoint \
 && chmod +x /usr/local/bin/pybossa-entrypoint \
 # lien attendu par PyBossa pour les traductions (cf. CI de l'amont)
 && ln -s themes/default/translations /app/pybossa/translations \
 # dossiers où l'application écrit : envois de fichiers, cache/CSS compilés par Flask-Assets
 && mkdir -p /app/uploads \
             /app/pybossa/themes/default/static/.webassets-cache \
             /app/pybossa/themes/default/static/css/gen \
             /app/pybossa/themes/default/static/js/gen \
 && chown -R pybossa:pybossa /app/uploads /app/pybossa/themes/default/static

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYBOSSA_SETTINGS=/config/settings_local.py

WORKDIR /app
USER pybossa
EXPOSE 5000

ENTRYPOINT ["pybossa-entrypoint"]
# Commande par défaut = serveur web. worker et scheduler la remplacent dans compose.yaml.
# --forwarded-allow-ips '*' : fait confiance aux en-têtes X-Forwarded-* du proxy Caddy
# (le port 5000 n'est jamais exposé hors du réseau compose).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", \
     "--timeout", "120", "--forwarded-allow-ips", "*", "--access-logfile", "-", \
     "pybossa.run:app"]
