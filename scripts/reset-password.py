# -*- coding: utf8 -*-
"""
Réinitialise le mot de passe d'un compte, par son nom d'utilisateur ou son e-mail.

Usage (conteneurs démarrés) :

    docker compose run --rm -e ACCOUNT=mullersa web python /scripts/reset-password.py

Le nouveau mot de passe est demandé au clavier (jamais en argument, jamais dans les journaux).
Utilise le modèle PyBossa (même hachage que l'interface) ; aucune écriture SQL à la main.
Cas d'usage : premier administrateur qui a oublié son mot de passe, instance sans courriel sortant.
Avec un courriel sortant fonctionnel, préférer le lien « Forgot password » de la page de connexion.
"""
import getpass
import os
import sys

from pybossa import core


def main():
    account = os.environ.get("ACCOUNT", "").strip().lower()
    if not account:
        sys.exit("Variable requise : ACCOUNT=<nom d'utilisateur ou e-mail>")
    app = core.create_app(run_as_server=False)
    with app.app_context():
        repo = core.user_repo
        user = repo.get_by(name=account) or repo.get_by(email_addr=account)
        if user is None:
            sys.exit("Aucun compte ne correspond à %r." % account)
        print("Compte : %s <%s>%s" % (user.name, user.email_addr, " (admin)" if user.admin else ""))
        pwd = getpass.getpass("Nouveau mot de passe (12 caractères minimum) : ")
        if len(pwd) < 12:
            sys.exit("Trop court.")
        if getpass.getpass("Confirmez : ") != pwd:
            sys.exit("Les deux saisies diffèrent, abandon.")
        user.set_password(pwd)
        repo.update(user)
        print("Mot de passe mis à jour pour %s." % user.name)


if __name__ == "__main__":
    main()
