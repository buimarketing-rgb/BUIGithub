"""Administrative command line.

    python -m app.cli create-user  --email a@b.com --name "Jane" --role super_admin
    python -m app.cli reset-password --email a@b.com
    python -m app.cli reindex
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password, validate_password_strength
from app.models import Role, User
from app.rag.indexer import reindex_all
from app.services.bootstrap import ensure_roles


def _password() -> str:
    pw = getpass.getpass("New password: ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    if err := validate_password_strength(pw):
        sys.exit(err)
    return pw


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--role", default="team_member", choices=["super_admin", "admin", "team_member"])
    r = sub.add_parser("reset-password")
    r.add_argument("--email", required=True)
    sub.add_parser("reindex")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        ensure_roles(db)
        if args.cmd == "create-user":
            if db.scalar(select(User).where(User.email == args.email.lower())):
                sys.exit("User already exists")
            role = db.scalar(select(Role).where(Role.name == args.role))
            db.add(User(email=args.email.lower(), full_name=args.name, role_id=role.id, password_hash=hash_password(_password())))
            db.commit()
            print(f"Created {args.email} ({args.role})")
        elif args.cmd == "reset-password":
            u = db.scalar(select(User).where(User.email == args.email.lower()))
            if not u:
                sys.exit("User not found")
            u.password_hash = hash_password(_password())
            u.is_active = True
            db.commit()
            print(f"Password reset for {args.email}")
        elif args.cmd == "reindex":
            print(reindex_all(db))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
