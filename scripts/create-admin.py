# -*- coding: utf8 -*-
"""
Crée le premier compte administrateur de l'instance.

Pourquoi ce script : dans le fork bloomberg/pybossa, la page /account/register est
réservée aux administrateurs connectés. Il n'existe donc aucun moyen, par l'interface,
de créer le tout premier compte. Ce script utilise le modèle et le dépôt d'utilisateurs
de PyBossa lui-même (aucune écriture SQL à la main, aucune modification du serveur).

Usage, depuis le dossier du dépôt, conteneurs démarrés et schéma créé (db_create) :

    docker compose run --rm \
        -e ADMIN_NAME=sandrine -e ADMIN_FULLNAME="Sandrine Muller" \
        -e ADMIN_EMAIL=prenom.nom@univ-grenoble-alpes.fr \
        web python /scripts/create-admin.py

Le mot de passe est demandé au clavier (il n'apparaît ni dans l'historique du shell,
ni dans les journaux). Le script refuse de créer un doublon et n'affiche jamais le
mot de passe ; il affiche la clé d'API, à conserver pour l'orchestrateur.
"""
import getpass
import os
import sys

# user_repo n'est initialisé qu'à l'appel de create_app : on importe le module,
# pas la variable, et on la lit après.
from pybossa import core
from pybossa.model.user import User


def main():
    name = os.environ.get("ADMIN_NAME", "").strip().lower()
    fullname = os.environ.get("ADMIN_FULLNAME", "").strip()
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if not (name and fullname and email):
        sys.exit("Variables requises : ADMIN_NAME, ADMIN_FULLNAME, ADMIN_EMAIL (voir l'en-tête du script).")

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Mot de passe du compte %s : " % name)
    if len(password) < 12:
        sys.exit("Mot de passe trop court (12 caractères minimum).")
    if not os.environ.get("ADMIN_PASSWORD"):
        if getpass.getpass("Confirmez le mot de passe : ") != password:
            sys.exit("Les deux saisies diffèrent, abandon.")

    app = core.create_app(run_as_server=False)
    with app.app_context():
        user_repo = core.user_repo
        if user_repo.get_by(name=name) or user_repo.get_by(email_addr=email):
            sys.exit("Un compte avec ce nom ou cet e-mail existe déjà : rien n'a été fait.")
        user = User(name=name, fullname=fullname, email_addr=email,
                    valid_email=True, consent=True, admin=True,
                    info={"metadata": {"admin": True}})
        user.set_password(password)
        user_repo.save(user)
        if not user.admin:
            sys.exit("Compte créé mais SANS droits admin : l'e-mail n'est pas dans SUPERUSER_WHITELIST_EMAILS.")
        print("Compte administrateur créé : %s <%s>" % (name, email))
        print("Clé d'API (à conserver, ne pas committer) : %s" % user.api_key)


if __name__ == "__main__":
    main()
