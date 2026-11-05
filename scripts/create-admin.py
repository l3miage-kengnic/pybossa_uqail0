# -*- coding: utf8 -*-
"""
Creates the instance's first administrator account.

Why this script: in the bloomberg/pybossa fork, the /account/register page is
reserved for logged-in administrators. There is therefore no way, through the interface,
to create the very first account. This script uses PyBossa's own user model and
repository (no hand-written SQL, no modification of the server).

Usage, from the repository folder, containers running and schema created (db_create):

    docker compose run --rm \
        -e ADMIN_NAME=sandrine -e ADMIN_FULLNAME="Sandrine Muller" \
        -e ADMIN_EMAIL=firstname.lastname@univ-grenoble-alpes.fr \
        web python /scripts/create-admin.py

The password is asked for at the keyboard (it appears neither in the shell history
nor in the logs). The script refuses to create a duplicate and never displays the
password; it displays the API key, to be kept for the orchestrator.
"""
import getpass
import os
import sys

# user_repo is only initialised when create_app is called: we import the module,
# not the variable, and read it afterwards.
from pybossa import core
from pybossa.model.user import User


def main():
    name = os.environ.get("ADMIN_NAME", "").strip().lower()
    fullname = os.environ.get("ADMIN_FULLNAME", "").strip()
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if not (name and fullname and email):
        sys.exit("Required variables: ADMIN_NAME, ADMIN_FULLNAME, ADMIN_EMAIL (see the script header).")

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password for account %s: " % name)
    if len(password) < 12:
        sys.exit("Password too short (12 characters minimum).")
    if not os.environ.get("ADMIN_PASSWORD"):
        if getpass.getpass("Confirm the password: ") != password:
            sys.exit("The two entries differ, aborting.")

    app = core.create_app(run_as_server=False)
    with app.app_context():
        user_repo = core.user_repo
        if user_repo.get_by(name=name) or user_repo.get_by(email_addr=email):
            sys.exit("An account with this name or e-mail already exists: nothing was done.")
        user = User(name=name, fullname=fullname, email_addr=email,
                    valid_email=True, consent=True, admin=True,
                    info={"metadata": {"admin": True}})
        user.set_password(password)
        user_repo.save(user)
        if not user.admin:
            sys.exit("Account created but WITHOUT admin rights: the e-mail is not in SUPERUSER_WHITELIST_EMAILS.")
        print("Administrator account created: %s <%s>" % (name, email))
        print("API key (keep it, do not commit it): %s" % user.api_key)


if __name__ == "__main__":
    main()
