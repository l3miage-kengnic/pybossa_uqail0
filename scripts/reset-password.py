# -*- coding: utf8 -*-
"""
Resets an account's password, by its username or its e-mail.

Usage (containers running):

    docker compose run --rm -e ACCOUNT=mullersa web python /scripts/reset-password.py

The new password is asked for at the keyboard (never as an argument, never in the logs).
Uses the PyBossa model (same hashing as the interface); no hand-written SQL.
Use case: first administrator who has forgotten their password, instance without outgoing e-mail.
With working outgoing e-mail, prefer the "Forgot password" link on the sign-in page.
"""
import getpass
import os
import sys

from pybossa import core


def main():
    account = os.environ.get("ACCOUNT", "").strip().lower()
    if not account:
        sys.exit("Required variable: ACCOUNT=<username or e-mail>")
    app = core.create_app(run_as_server=False)
    with app.app_context():
        repo = core.user_repo
        user = repo.get_by(name=account) or repo.get_by(email_addr=account)
        if user is None:
            sys.exit("No account matches %r." % account)
        print("Account: %s <%s>%s" % (user.name, user.email_addr, " (admin)" if user.admin else ""))
        pwd = getpass.getpass("New password (12 characters minimum): ")
        if len(pwd) < 12:
            sys.exit("Too short.")
        if getpass.getpass("Confirm: ") != pwd:
            sys.exit("The two entries differ, aborting.")
        user.set_password(pwd)
        repo.update(user)
        print("Password updated for %s." % user.name)


if __name__ == "__main__":
    main()
