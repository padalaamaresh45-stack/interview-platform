"""One-time bootstrap: create the first Admin account.

Run once at deploy time, outside the normal request/response cycle:

    python -m app.seed.create_admin
"""
import getpass
import os
import sys

from app.auth.hashing import hash_password
from app.database import SessionLocal
from app.models.user import User, UserRole


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL") or input("Admin email: ").strip()
    full_name = os.environ.get("ADMIN_FULL_NAME") or input("Admin full name: ").strip()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            print(f"A user with email {email!r} already exists.", file=sys.stderr)
            sys.exit(1)

        admin = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created admin user {email!r}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
