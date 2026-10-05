#!/usr/bin/env python
"""Create demo accounts (admin, doctor, nurse) and one demo patient with a login.

Every password is randomly generated and printed ONCE — nothing is hard-coded. Accounts are
created with must_change_password off so you can try each role immediately; real staff
accounts created through the admin page always require a change on first login.

Usage: python scripts/seed_demo_users.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.security import audit  # noqa: E402
from app.security.passwords import generate_temporary_password  # noqa: E402
from app.services import accounts_service  # noqa: E402

DEMO_STAFF = [
    ("demo.admin", "admin", "Demo College Administrator"),
    ("demo.doctor", "doctor", "Dr. Demo Doctor"),
    ("demo.nurse", "nurse", "Demo Nurse"),
]


def main() -> None:
    rows = []
    for username, role, name in DEMO_STAFF:
        password = generate_temporary_password()
        try:
            uid = accounts_service.create_user(username, password, role, name, created_by=None)
        except accounts_service.AccountError as e:
            print(f"skip {username}: {e}")
            continue
        audit.record("user_create", username="(seed)", target=f"user:{uid}", detail=f"demo {role}")
        rows.append((role, username, password))

    existing = accounts_service.find_patient_by_mrn("DEMO-0001")
    if existing:
        print("skip demo patient: MRN DEMO-0001 already exists")
    else:
        result = accounts_service.register_patient("DEMO-0001", "Demo Patient", "1990-05-17", "F",
                                                   created_by=None, create_login=True)
        login = result["login"]
        # Demo convenience: clear the forced change so the patient view can be tried directly.
        from app.db import connect
        with connect() as conn:
            conn.execute("UPDATE users SET must_change_password = 0 WHERE username = ?", (login["username"],))
        audit.record("patient_register", username="(seed)", target=f"patient:{result['patient']['id']}")
        rows.append(("patient", login["username"], login["temporary_password"]))

    if rows:
        print("\nDemo accounts (shown once — store them somewhere safe):\n")
        print(f"{'ROLE':<10}{'USERNAME':<18}PASSWORD")
        for role, username, password in rows:
            print(f"{role:<10}{username:<18}{password}")


if __name__ == "__main__":
    main()
