"""Create or promote a librarian or admin account from this computer.

Public registration always creates a student. This script is the local way
to add a staff account. It is not an API endpoint.

Interactive example (PowerShell):

    .\\.venv\\Scripts\\python.exe create_staff.py

Non-interactive environment variables:

    STAFF_NAME
    STAFF_EMAIL
    STAFF_PASSWORD
    STAFF_ROLE          librarian or admin
    STAFF_UPDATE_EXISTING   set to true to change an existing account
"""

import os
import sys

from dotenv import load_dotenv
from pydantic import EmailStr, TypeAdapter, ValidationError

from auth_utils import hash_password
from database import SessionLocal
from models import User

load_dotenv()

ALLOWED_ROLES = ("librarian", "admin")


def _validated_email(email: str) -> str:
    try:
        return str(TypeAdapter(EmailStr).validate_python(email.strip()))
    except ValidationError as error:
        raise ValueError("Email address is not valid") from error


def create_or_promote_staff(
    db,
    name: str,
    email: str,
    password: str | None,
    role: str,
    update_existing: bool
) -> str:
    """Create a staff user, or update an existing user when allowed.

    Returns a short status message. Does not print the password.
    """
    name = name.strip()
    role = role.strip().lower()

    if len(name) < 2 or len(name) > 100:
        raise ValueError("Name must be between 2 and 100 characters")

    if role not in ALLOWED_ROLES:
        raise ValueError("Role must be librarian or admin")

    validated_email = _validated_email(email)

    existing_user = db.query(User).filter(
        User.email == validated_email
    ).first()

    if existing_user is None:
        if not password or len(password) < 8 or len(password) > 128:
            raise ValueError("Password must be between 8 and 128 characters")

        staff_user = User(
            name=name,
            email=validated_email,
            hashed_password=hash_password(password),
            role=role
        )
        db.add(staff_user)
        db.commit()
        return f"Created {role} account for {validated_email}"

    if not update_existing:
        raise ValueError(
            "An account with this email already exists. "
            "Confirm promotion to update it."
        )

    existing_user.name = name
    existing_user.role = role

    if password:
        if len(password) < 8 or len(password) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        existing_user.hashed_password = hash_password(password)

    db.commit()
    return f"Updated {validated_email} to {role}"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y"}


def _read_interactive_values() -> tuple[str, str, str, str, bool]:
    import getpass

    name = input("Name: ").strip()
    email = input("Email: ").strip()
    password = getpass.getpass("Password (hidden): ")
    confirm_password = getpass.getpass("Confirm password (hidden): ")
    role = input("Role (librarian or admin): ").strip().lower()

    if password != confirm_password:
        raise ValueError("Passwords do not match")

    return name, email, password, role, False


def main() -> int:
    env_email = os.getenv("STAFF_EMAIL")
    using_environment = bool(env_email)

    try:
        if using_environment:
            name = os.getenv("STAFF_NAME", "")
            email = env_email or ""
            password = os.getenv("STAFF_PASSWORD")
            role = os.getenv("STAFF_ROLE", "")
            update_existing = _env_flag("STAFF_UPDATE_EXISTING")
        else:
            name, email, password, role, update_existing = (
                _read_interactive_values()
            )
    except ValueError as error:
        print(error)
        return 1

    try:
        email = _validated_email(email)
    except ValueError as error:
        print(error)
        return 1

    db = SessionLocal()

    try:
        if not using_environment:
            existing_user = db.query(User).filter(
                User.email == email
            ).first()
            if existing_user is not None:
                answer = input(
                    "This email already exists. Update the role? [y/N]: "
                ).strip().lower()
                update_existing = answer in {"y", "yes"}

        message = create_or_promote_staff(
            db=db,
            name=name,
            email=email,
            password=password,
            role=role,
            update_existing=update_existing
        )
    except ValueError as error:
        db.rollback()
        print(error)
        return 1
    except Exception:
        db.rollback()
        print("Could not save the staff account.")
        return 1
    finally:
        db.close()

    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
