# -*- coding: utf8 -*-
"""
PyBossa configuration for U-QUAIL.

This file is mounted read-only into the containers (web, worker, scheduler)
and loaded by PyBossa through the PYBOSSA_SETTINGS variable. This is the
configuration mechanism provided by PyBossa: the server code is not modified.

It contains NO secret: everything sensitive is read from environment
variables, which are themselves provided by the .env file (never committed).

Written from pybossa/default_settings.py and pybossa/settings_local.py.tmpl
of bloomberg/pybossa (the latter is not valid Python and contains settings
specific to the Bloomberg instance: it is not reused as is).
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
            "Missing environment variable: %s (to be set in .env)" % name)
    return value


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
DEBUG = False
HOST = "0.0.0.0"
PORT = 5000

# Behind Caddy: all generated URLs use https.
PREFERRED_URL_SCHEME = "https"
SPA_SERVER_NAME = "https://%s" % _env("DOMAIN", "localhost")
# Used in invitation emails (Bloomberg fork: util.generate_invitation_email_*)
SERVER_URL = SPA_SERVER_NAME
IS_QA = False
USER_MANUAL_LABEL = None
USER_MANUAL_URL = None
ADMIN_MANUAL_LABEL = None
ADMIN_MANUAL_URL = None

SECRET_KEY = _required("SECRET_KEY")
ITSDANGEROUSKEY = _required("ITSDANGEROUSKEY")
# 32-character key for IP address anonymization (CryptoPAn).
CRYPTOPAN_KEY = _required("CRYPTOPAN_KEY")

# Cookies: HTTPS only, inaccessible to JavaScript.
# Exception: on a workstation (DOMAIN=localhost), plain HTTP access on port 8080
# (tests, the tools' built-in browser) must be able to log in; the HTTPS requirement
# is then lifted. localhost is never a production domain.
_LOCAL_WORKSTATION = _env("DOMAIN", "localhost") in ("localhost", "127.0.0.1")
FORCE_HTTPS = not _LOCAL_WORKSTATION          # read by flask-talisman (pybossa/core.py)
SESSION_COOKIE_SECURE = not _LOCAL_WORKSTATION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
REMEMBER_COOKIE_SECURE = not _LOCAL_WORKSTATION
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_NAME = "uquail_remember_token"
# Session lifetime: 8 h sliding, then log in again. A server restart does not
# log anyone out (the session is a signed cookie, not server state): this is expected.
PERMANENT_SESSION_LIFETIME = 8 * 60 * 60
REMEMBER_COOKIE_DURATION = 7 * 24 * 60 * 60   # "remember me": 7 days

# ---------------------------------------------------------------------------
# Database and Redis
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s/%s" % (
    _env("POSTGRES_USER", "pybossa"),
    _required("POSTGRES_PASSWORD"),
    _env("POSTGRES_HOST", "db"),
    _env("POSTGRES_DB", "pybossa"),
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Plain Redis, without Sentinel: if REDIS_MASTER_DNS, REDIS_SLAVE_DNS and REDIS_PORT
# are defined, pybossa/sentinel/__init__.py and run_scheduler.py connect
# directly. This is what avoids the Sentinel cluster of the Bloomberg template.
REDIS_MASTER_DNS = _env("REDIS_HOST", "redis")
REDIS_SLAVE_DNS = _env("REDIS_HOST", "redis")
REDIS_PORT = int(_env("REDIS_PORT", "6379"))
REDIS_PWD = None
REDIS_DB = 0
REDIS_KEYPREFIX = "pybossa_cache"
# Redis socket timeout. For the web server: short (0.1 s by default, too tight in a container).
# For the RQ worker: long, because it waits for jobs with a blocking command (BLPOP ~ 7 min)
# and RQ does not raise a timeout that is already configured (rq/worker.py, _set_connection): with 1 s it
# would exit every two seconds with "Redis connection timeout".
_IS_RQ_WORKER = any("app_context_rqworker" in a for a in sys.argv[:1])
REDIS_SOCKET_TIMEOUT = 900 if _IS_RQ_WORKER else 1.0
REDIS_RETRY_ON_TIMEOUT = True
REDIS_SSL = False

# ---------------------------------------------------------------------------
# Instance identity
# ---------------------------------------------------------------------------
BRAND = _env("BRAND", "U-QUAIL")
TITLE = _env("TITLE", "U-QUAIL")
DESCRIPTION = _env("DESCRIPTION", "Expert annotation platform")
COPYRIGHT = _env("COPYRIGHT", "Université Grenoble Alpes")
# U-QUAIL logo (files added in static/img/, the theme is not modified):
# uquail-logo.svg for the black bar, uquail-logo-light.svg for light backgrounds, uquail-icon.svg alone.
LOGO = "uquail-logo.svg"
FAVICON = "img/favicon/favicon.ico"
CONTACT_EMAIL = _env("CONTACT_EMAIL", "")
CONTACT_TWITTER = ""
TERMSOFUSE = "/help/terms-of-use"
DATAUSE = "/help/privacy"
ADMINS = _env_list("ADMINS")
WEEKLY_ADMIN_REPORTS_EMAIL = ADMINS
# Public repository of this instance (AGPL notice in the footer and on the "About" page).
PROJECT_URL = _env("PROJECT_URL", "https://gricad-gitlab.univ-grenoble-alpes.fr/ia4health.daisy/pybossa/pybossa-uquail-theme")
# Privacy page (footer link): the internal page, not a third-party site.
PRIVACY_POLICY_PAGE = "/help/privacy"
# No per-project contact form.
CONTACT_ENABLE = []

# English interface by default (U-QUAIL texts written in English, translatable);
# each user can choose French in their settings.
DEFAULT_LOCALE = _env("DEFAULT_LOCALE", "en")
LOCALES = [("en", "English"), ("fr", "Français")]

# Environment identification banner (Bloomberg feature): disabled.
SERVER_TYPE = ""
DISPLAY_PLATFORM_IDENTIFIER = False
# Navigation bar background: black, like the AI4Health@DAISY banner (the logo is designed for it).
NAVBAR_COLOR = "#000000"

# ---------------------------------------------------------------------------
# Privacy and access
# ---------------------------------------------------------------------------
# Statistics, leaderboard and profile pages: restricted to administrators.
ENFORCE_PRIVACY = True
# No browsing without an account (Bloomberg setting).
DISABLE_ANONYMOUS_ACCESS = True
# No email confirmation as long as SMTP is not validated (see MAIL_*).
ACCOUNT_CONFIRMATION_DISABLED = _env_bool("ACCOUNT_CONFIRMATION_DISABLED", True)
ACCOUNT_LINK_EXPIRATION = 5 * 60 * 60
# Strong passwords and mandatory API key (no bypassing 2FA).
ENABLE_STRONG_PASSWORD = True
SECURE_APP_ACCESS = False
# Bloomberg L1-L4 access levels: disabled, not needed here.
ENABLE_ACCESS_CONTROL = False
# ... but the fork requires a "data classification" for each project
# (pybossa/repositories/project_repository.py). A single class, public:
# U-QUAIL items come from public knowledge graphs, with no patient data.
DATA_CLASSIFICATION = [("L4 - public", True)]
VALID_DATA_CLASSES = [c for c, enabled in DATA_CLASSIFICATION if enabled]
VALID_ACCESS_LEVELS = sorted({c.split("-")[0].strip() for c in VALID_DATA_CLASSES})
# Product/subproduct catalog of the project creation form (Bloomberg feature).
PRODUCTS_SUBPRODUCTS = {"U-QUAIL": ["Benchmark", "Sandbox"]}
# A project password is not mandatory (the API still asks for one at creation).
PROJECT_PASSWORD_REQUIRED = False
# Task data encryption (Bloomberg feature): disabled.
ENABLE_ENCRYPTION = False
# No third-party audience measurement tool, no GCS/Mailchimp/Flickr/Dropbox.

# ---------------------------------------------------------------------------
# Email
# Locally (MAIL_SERVER empty): Mailpit, the fake server of the "local" compose profile.
# ---------------------------------------------------------------------------
if _env("MAIL_SERVER"):
    MAIL_SERVER = _env("MAIL_SERVER")
    MAIL_PORT = int(_env("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
else:
    # Workstation: Mailpit, port 1025, no TLS, whatever MAIL_PORT / MAIL_USE_TLS say.
    MAIL_SERVER = "mailpit"
    MAIL_PORT = 1025
    MAIL_USE_TLS = False
MAIL_USERNAME = _env("MAIL_USERNAME")
MAIL_PASSWORD = _env("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = _env("MAIL_DEFAULT_SENDER", "U-QUAIL <no-reply@example.org>")
MAIL_FAIL_SILENTLY = False

# ---------------------------------------------------------------------------
# Uploaded files (avatars, etc.): local storage in the "uploads" volume.
# ---------------------------------------------------------------------------
UPLOAD_METHOD = "local"
UPLOAD_FOLDER = "/app/uploads"
ALLOWED_EXTENSIONS = ["js", "css", "png", "jpg", "jpeg", "gif", "zip"]
MAX_IMAGE_UPLOAD_SIZE_MB = 5
AVATAR_ABSOLUTE = True

# ---------------------------------------------------------------------------
# Projects, tasks, schedulers
# ---------------------------------------------------------------------------
AVAILABLE_SCHEDULERS = [
    ("default", "Default"),
    ("locked_scheduler", "Locked"),
    ("user_pref_scheduler", "User Preference Scheduler"),
    ("task_queue_scheduler", "Task Queues"),
]
PRESENTERS = ["basic"]
TEMPLATE_TASKS = {}
# No mandatory field imposed on tasks (Bloomberg setting neutralized).
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

# "Pro" features: open to all users (no notion of a pro account here).
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

# S3 storage: not used, neutral values expected by the Bloomberg code.
S3_CONN_KWARGS = {"port": None, "is_secure": True}
S3_SSL_NO_VERIFY = False
S3_HOST_SUFFIX = ""
S3_CUSTOM_HEADERS = []
S3_CUSTOM_HANDLER_HOSTS = []

# Outgoing webhooks: HTTPS only, never to private IPs.
WEBHOOK_ALLOWED_DOMAINS = []
WEBHOOK_HTTPS_ONLY = True
WEBHOOK_BLOCK_PRIVATE_IPS = True

# ---------------------------------------------------------------------------
# Interface: project creation wizard (taken from the upstream template)
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

# Task presenter editor components (names expected by the Bloomberg theme).
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

# Interactive API documentation (Swagger).
SWAGGER_HEADER_PATH = "pybossa/themes/default/templates/flasgger_custom_head.html"
SWAGGER_TEMPLATE = {
    "info": {
        "title": "%s - API" % BRAND,
        "description": "REST API of the PyBossa instance %s.\n"
                       "Documentation: https://docs.pybossa.com/" % BRAND,
    },
    "favicon": "/static/img/favicon/favicon.ico",
    "title": "%s - API" % BRAND,
}

# Logging to standard output (read by `docker compose logs`).
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
