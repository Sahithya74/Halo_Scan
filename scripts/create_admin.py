#!/usr/bin/env python
"""Create an administrator account. Prompts for the password (never pass it as an argument,
where it would land in shell history).

Usage: python scripts/create_admin.py --username admin --name "College Admin"
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.security import audit  # noqa: E402
from app.services import accounts_service  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()

    password = getpass.getpass("New admin password: ")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    try:
        uid = accounts_service.create_user(args.username, password, "admin", args.name, created_by=None)
    except accounts_service.AccountError as e:
        sys.exit(f"Error: {e}")
    audit.record("user_create", username="(cli)", target=f"user:{uid}", detail="admin via create_admin.py")
    print(f"Created administrator '{args.username}' (id {uid}).")


if __name__ == "__main__":
    main()
