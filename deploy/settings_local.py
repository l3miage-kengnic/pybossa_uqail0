# -*- coding: utf8 -*-
"""
Configuration PyBossa pour U-QUAIL.

Ce fichier est monté en lecture seule dans les conteneurs (web, worker, scheduler)
et chargé par PyBossa via la variable PYBOSSA_SETTINGS. C'est le mécanisme de
configuration prévu par PyBossa : le code du serveur n'est pas modifié.

Il ne contient AUCUN secret : tout ce qui est sensible est lu dans les variables
d'environnement, elles-mêmes fournies par le fichier .env (jamais commité).

Écrit à partir de pybossa/default_settings.py et de pybossa/settings_local.py.tmpl
de bloomberg/pybossa (ce dernier n'est pas du Python valide et contient des
réglages propres à l'instance Bloomberg : il n'est pas repris tel quel).
"""
import sys
from collections import OrderedDict
from os import environ


def _env(name, default=None):
    value = environ.get(name)
    return value if value not in (None, "") else default


def _env_bool(name, default=False):
    value = _env(name)
    return default if value is None else value.lower() in ("1", "true", "yes", "on")


def _env_list(name):
    value = _env(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _required(name):
    value = _env(name)
    if value is None:
        raise RuntimeError(
            "Variable d'environnement manquante : %s (à renseigner dans .env)" % name)
    return value


# ---------------------------------------------------------------------------
# Serveur
# ---------------------------------------------------------------------------
DEBUG = False
HOST = "0.0.0.0"
PORT = 5000

# Derrière Caddy : toutes les URL générées sont en https.
PREFERRED_URL_SCHEME = "https"
SPA_SERVER_NAME = "https://%s" % _env("DOMAIN", "localhost")
# Utilisé dans les courriels d'invitation (fork Bloomberg : util.generate_invitation_email_*)
SERVER_URL = SPA_SERVER_NAME
IS_QA = False
USER_MANUAL_LABEL = None
USER_MANUAL_URL = None
ADMIN_MANUAL_LABEL = None
ADMIN_MANUAL_URL = None

SECRET_KEY = _required("SECRET_KEY")
ITSDANGEROUSKEY = _required("ITSDANGEROUSKEY")
# Clé de 32 caractères pour l'anonymisation des adresses IP (CryptoPAn).
CRYPTOPAN_KEY = _required("CRYPTOPAN_KEY")

# Cookies : uniquement en HTTPS, inaccessibles au JavaScript.
# Exception : sur un poste de travail (DOMAIN=localhost), l'accès HTTP simple sur le port 8080
# (tests, navigateur intégré des outils) doit pouvoir ouvrir une session ; on lève alors
# l'obligation HTTPS. localhost n'est jamais un domaine de production.
_LOCAL_WORKSTATION = _env("DOMAIN", "localhost") in ("localhost", "127.0.0.1")
FORCE_HTTPS = not _LOCAL_WORKSTATION          # lu par flask-talisman (pybossa/core.py)
SESSION_COOKIE_SECURE = not _LOCAL_WORKSTATION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
REMEMBER_COOKIE_SECURE = not _LOCAL_WORKSTATION
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_NAME = "uquail_remember_token"
# Durée de session : 8 h glissantes, puis reconnexion. Un redémarrage du serveur ne
# déconnecte personne (la session est un cookie signé, pas un état serveur) : c'est normal.
PERMANENT_SESSION_LIFETIME = 8 * 60 * 60
REMEMBER_COOKIE_DURATION = 7 * 24 * 60 * 60   # "se souvenir de moi" : 7 jours

# ---------------------------------------------------------------------------
# Base de données et Redis
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s/%s" % (
    _env("POSTGRES_USER", "pybossa"),
    _required("POSTGRES_PASSWORD"),
    _env("POSTGRES_HOST", "db"),
    _env("POSTGRES_DB", "pybossa"),
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Redis simple, sans Sentinel : si REDIS_MASTER_DNS, REDIS_SLAVE_DNS et REDIS_PORT
# sont définis, pybossa/sentinel/__init__.py et run_scheduler.py se connectent en
# direct. C'est ce qui évite la grappe Sentinel du modèle Bloomberg.
REDIS_MASTER_DNS = _env("REDIS_HOST", "redis")
REDIS_SLAVE_DNS = _env("REDIS_HOST", "redis")
REDIS_PORT = int(_env("REDIS_PORT", "6379"))
REDIS_PWD = None
REDIS_DB = 0
REDIS_KEYPREFIX = "pybossa_cache"
# Délai socket Redis. Pour le serveur web : court (0,1 s par défaut, trop juste en conteneur).
# Pour le worker RQ : long, car il attend les travaux par une commande bloquante (BLPOP ~ 7 min)
# et RQ ne relève pas un délai déjà configuré (rq/worker.py, _set_connection) : avec 1 s il
# quitterait toutes les deux secondes avec "Redis connection timeout".
_IS_RQ_WORKER = any("app_context_rqworker" in a for a in sys.argv[:1])
REDIS_SOCKET_TIMEOUT = 900 if _IS_RQ_WORKER else 1.0
REDIS_RETRY_ON_TIMEOUT = True
REDIS_SSL = False

# ---------------------------------------------------------------------------
# Identité de l'instance
# ---------------------------------------------------------------------------
BRAND = _env("BRAND", "U-QUAIL")
TITLE = _env("TITLE", "U-QUAIL")
DESCRIPTION = _env("DESCRIPTION", "Plateforme d'annotation par des experts")
COPYRIGHT = _env("COPYRIGHT", "Université Grenoble Alpes")
# Logo U-QUAIL (fichiers ajoutés dans static/img/, le thème n'est pas modifié) :
# uquail-logo.svg pour la barre noire, uquail-logo-light.svg pour fond clair, uquail-icon.svg seul.
LOGO = "uquail-logo.svg"
FAVICON = "img/favicon/favicon.ico"
CONTACT_EMAIL = _env("CONTACT_EMAIL", "")
CONTACT_TWITTER = ""
TERMSOFUSE = "/help/terms-of-use"
DATAUSE = "/help/privacy"
ADMINS = _env_list("ADMINS")
WEEKLY_ADMIN_REPORTS_EMAIL = ADMINS
# Dépôt public de cette instance (mention AGPL dans le pied de page et la page "À propos").
PROJECT_URL = _env("PROJECT_URL", "https://gricad-gitlab.univ-grenoble-alpes.fr/ia4health.daisy/pybossa/pybossa-uquail-theme")
# Page de confidentialité (lien du pied de page) : la page interne, pas un site tiers.
PRIVACY_POLICY_PAGE = "/help/privacy"
# Pas de formulaire de contact par projet.
CONTACT_ENABLE = []

# Interface en anglais par défaut (textes U-QUAIL écrits en anglais, traduisibles) ;
# chaque utilisateur peut choisir le français dans ses réglages.
DEFAULT_LOCALE = _env("DEFAULT_LOCALE", "en")
LOCALES = [("en", "English"), ("fr", "Français")]

# Bandeau d'identification de l'environnement (fonction Bloomberg) : désactivé.
SERVER_TYPE = ""
DISPLAY_PLATFORM_IDENTIFIER = False
# Fond de la barre de navigation : noir, comme la bannière AI4Health@DAISY (le logo est prévu pour).
NAVBAR_COLOR = "#000000"

# ---------------------------------------------------------------------------
# Confidentialité et accès
# ---------------------------------------------------------------------------
# Pages de statistiques, classements, profils : réservées aux administrateurs.
ENFORCE_PRIVACY = True
# Aucune consultation sans compte (réglage Bloomberg).
DISABLE_ANONYMOUS_ACCESS = True
# Pas de confirmation d'e-mail tant que le SMTP n'est pas validé (voir MAIL_*).
ACCOUNT_CONFIRMATION_DISABLED = _env_bool("ACCOUNT_CONFIRMATION_DISABLED", True)
ACCOUNT_LINK_EXPIRATION = 5 * 60 * 60
# Mots de passe forts et clé d'API obligatoire (pas de contournement du 2FA).
ENABLE_STRONG_PASSWORD = True
SECURE_APP_ACCESS = False
# Niveaux d'accès L1-L4 de Bloomberg : désactivés, inutiles ici.
ENABLE_ACCESS_CONTROL = False
# ... mais le fork exige une "classification des données" pour chaque projet
# (pybossa/repositories/project_repository.py). Une seule classe, publique :
# les items U-QUAIL viennent de graphes de connaissances publics, sans donnée patient.
DATA_CLASSIFICATION = [("L4 - public", True)]
VALID_DATA_CLASSES = [c for c, enabled in DATA_CLASSIFICATION if enabled]
VALID_ACCESS_LEVELS = sorted({c.split("-")[0].strip() for c in VALID_DATA_CLASSES})
# Catalogue produit/sous-produit du formulaire de création de projet (fonction Bloomberg).
PRODUCTS_SUBPRODUCTS = {"U-QUAIL": ["Benchmark", "Sandbox"]}
# Un mot de passe de projet n'est pas obligatoire (l'API le réclame quand même à la création).
PROJECT_PASSWORD_REQUIRED = False
# Chiffrement des données de tâche (fonction Bloomberg) : désactivé.
ENABLE_ENCRYPTION = False
# Pas d'outil de mesure d'audience tiers, pas de GCS/Mailchimp/Flickr/Dropbox.

# ---------------------------------------------------------------------------
# Courriel
# En local (MAIL_SERVER vide) : Mailpit, le faux serveur du profil compose "local".
# ---------------------------------------------------------------------------
if _env("MAIL_SERVER"):
    MAIL_SERVER = _env("MAIL_SERVER")
    MAIL_PORT = int(_env("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
else:
    # Poste de travail : Mailpit, port 1025, sans TLS, quoi que disent MAIL_PORT / MAIL_USE_TLS.
    MAIL_SERVER = "mailpit"
    MAIL_PORT = 1025
    MAIL_USE_TLS = False
MAIL_USERNAME = _env("MAIL_USERNAME")
MAIL_PASSWORD = _env("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = _env("MAIL_DEFAULT_SENDER", "U-QUAIL <no-reply@example.org>")
MAIL_FAIL_SILENTLY = False

# ---------------------------------------------------------------------------
# Fichiers envoyés (avatars, etc.) : stockage local dans le volume "uploads".
# ---------------------------------------------------------------------------
UPLOAD_METHOD = "local"
UPLOAD_FOLDER = "/app/uploads"
ALLOWED_EXTENSIONS = ["js", "css", "png", "jpg", "jpeg", "gif", "zip"]
MAX_IMAGE_UPLOAD_SIZE_MB = 5
AVATAR_ABSOLUTE = True

# ---------------------------------------------------------------------------
# Projets, tâches, ordonnanceurs
# ---------------------------------------------------------------------------
AVAILABLE_SCHEDULERS = [
    ("default", "Default"),
    ("locked_scheduler", "Locked"),
    ("user_pref_scheduler", "User Preference Scheduler"),
    ("task_queue_scheduler", "Task Queues"),
]
PRESENTERS = ["basic"]
TEMPLATE_TASKS = {}
# Aucun champ obligatoire imposé dans les tâches (réglage Bloomberg neutralisé).
TASK_REQUIRED_FIELDS = {}
TASK_RESERVED_COLS = []
TASK_DEFAULT_EXPIRATION = 60
TASK_MAX_EXPIRATION = 365
UNPUBLISH_PROJECTS = False
SESSION_REPLICATION_ROLE_DISABLED = True
PASSWD_COOKIE_TIMEOUT = 60 * 30
ANNOUNCEMENT_LEVELS = {
    "admin": {"display": "Admin", "level": 0},
    "owner": {"display": "Project Creator", "level": 10},
    "subadmin": {"display": "Subadmin", "level": 20},
    "user": {"display": "User", "level": 30},
}
ANNOUNCEMENT_LEVEL_OPTIONS = [
    {"text": v["display"], "value": v["level"]} for v in ANNOUNCEMENT_LEVELS.values()
]

# Fonctions "pro" : ouvertes à tous les utilisateurs (pas de notion de compte pro ici).
PRO_FEATURES = {
    "auditlog": False,
    "webhooks": False,
    "updated_exports": False,
    "notify_blog_updates": False,
    "project_weekly_report": False,
    "autoimporter": False,
    "better_stats": False,
}

# Exports
EXPORT_MAX_EMAIL_SIZE = 6 * 1024 * 1024
EXPORT_MAX_UPLOAD_SIZE = 1024 * 1024 * 1024

# Stockage S3 : non utilisé, valeurs neutres attendues par le code Bloomberg.
S3_CONN_KWARGS = {"port": None, "is_secure": True}
S3_SSL_NO_VERIFY = False
S3_HOST_SUFFIX = ""
S3_CUSTOM_HEADERS = []
S3_CUSTOM_HANDLER_HOSTS = []

# Webhooks sortants : HTTPS seulement, jamais vers des IP privées.
WEBHOOK_ALLOWED_DOMAINS = []
WEBHOOK_HTTPS_ONLY = True
WEBHOOK_BLOCK_PRIVATE_IPS = True

# ---------------------------------------------------------------------------
# Interface : assistant de création de projet (repris du modèle amont)
# ---------------------------------------------------------------------------
WIZARD_STEPS = OrderedDict([
    ("new_project", {
        "title": "Project Creation", "icon": "fa fa-pencil",
        "href": {"url_for": "project.new", "args": [""]},
        "done_checks": {"always": False},
        "enable_checks": {"always": True},
        "visible_checks": {"and": ["not_project_exist"], "or": []},
    }),
    ("project_details", {
        "title": "Project Details", "icon": "fa fa-pencil",
        "href": {"url_for": "project.update", "args": ["short_name"]},
        "done_checks": {"always": True},
        "enable_checks": {"always": True},
        "visible_checks": {"and": ["project_exist"], "or": []},
    }),
    ("task_imports", {
        "title": "Import Tasks", "icon": "fa fa-file",
        "href": {"url_for": "project.import_task", "args": ["short_name"]},
        "done_checks": {"and": ["tasks_amount"], "or": []},
        "enable_checks": {"and": ["project_exist"], "or": []},
        "visible_checks": {"always": True},
    }),
    ("task_presenter", {
        "title": "Task Presenter", "icon": "fa fa-pencil",
        "href": {"url_for": "project.task_presenter_editor", "args": ["short_name"]},
        "done_checks": {"and": ["task_presenter", "task_guidelines"], "or": []},
        "enable_checks": {"and": ["tasks_amount"],
                          "or": ["task_presenter", "task_guidelines", "project_publish"]},
        "visible_checks": {"always": True},
    }),
    ("task_settings", {
        "title": "Settings", "icon": "fa fa-cogs",
        "href": {"url_for": "project.summary", "args": ["short_name"]},
        "done_checks": {"and": ["task_presenter", "tasks_amount"], "or": ["project_publish"]},
        "enable_checks": {"and": ["task_presenter", "tasks_amount"], "or": ["project_publish"]},
        "visible_checks": {"always": True},
    }),
    ("publish", {
        "title": "Publish", "icon": "fa fa-check",
        "href": {"url_for": "project.publish", "args": ["short_name"]},
        "done_checks": {"always": False},
        "enable_checks": {"and": ["task_presenter", "tasks_amount"], "or": ["project_publish"]},
        "visible_checks": {"and": ["not_project_publish"], "or": ["not_project_exist"]},
    }),
    ("published", {
        "title": "Published", "icon": "fa fa-check",
        "href": {"url_for": "project.publish", "args": ["short_name"]},
        "done_checks": {"always": True},
        "enable_checks": {"always": True},
        "visible_checks": {"and": ["project_publish"], "or": []},
    }),
])

# Composants de l'éditeur de task presenter (noms attendus par le thème Bloomberg).
USAGE_DASHBOARD_COMPONENTS = {
    "Task Presenter": "task-presenter",
    "All Buttons": "button-row",
    "Submit Button": "submit-button",
    "Submit and Leave Button": "submit-last-button",
    "Cancel Button": "cancel-button",
    "Task Timer": "task-timer",
    "Conditional Display": "conditional-display",
    "Text Input": "text-input",
    "Checkbox Input": "checkbox-input",
    "Radio Group Input": "radio-group-input",
    "Dropdown Input": "dropdown-input",
    "Multiselect Input": "multi-select-input",
    "Table": "table-element",
    "Input Text Area": "input-text-area",
}

# Documentation interactive de l'API (Swagger).
SWAGGER_HEADER_PATH = "pybossa/themes/default/templates/flasgger_custom_head.html"
SWAGGER_TEMPLATE = {
    "info": {
        "title": "%s - API" % BRAND,
        "description": "API REST de l'instance PyBossa %s.\n"
                       "Documentation : https://docs.pybossa.com/" % BRAND,
    },
    "favicon": "/static/img/favicon/favicon.ico",
    "title": "%s - API" % BRAND,
}

# Journalisation sur la sortie standard (lue par `docker compose logs`).
LOG_DICT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(name)s:%(levelname)s:[%(asctime)s] %(message)s"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": _env("LOG_LEVEL", "INFO"),
            "formatter": "default",
        },
    },
    "loggers": {
        "pybossa": {"level": _env("LOG_LEVEL", "INFO"), "handlers": ["stdout"]},
    },
}
