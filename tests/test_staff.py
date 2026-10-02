import pytest

from create_staff import create_or_promote_staff
from models import User


def test_create_and_promote_staff_account(db):
    message = create_or_promote_staff(
        db=db,
        name="Library Lead",
        email="lead@example.com",
        password="library123",
        role="librarian",
        update_existing=False
    )
    assert message == "Created librarian account for lead@example.com"

    user = db.query(User).filter(User.email == "lead@example.com").one()
    assert user.role == "librarian"
    assert user.hashed_password != "library123"

    with pytest.raises(ValueError):
        create_or_promote_staff(
            db=db,
            name="Library Lead",
            email="lead@example.com",
            password=None,
            role="admin",
            update_existing=False
        )

    promoted = create_or_promote_staff(
        db=db,
        name="Library Lead",
        email="lead@example.com",
        password=None,
        role="admin",
        update_existing=True
    )
    assert "admin" in promoted
    db.refresh(user)
    assert user.role == "admin"


def test_staff_script_rejects_student_role_and_short_password(db):
    with pytest.raises(ValueError):
        create_or_promote_staff(
            db=db,
            name="Student",
            email="student@example.com",
            password="student123",
            role="student",
            update_existing=False
        )

    with pytest.raises(ValueError):
        create_or_promote_staff(
            db=db,
            name="Library Lead",
            email="lead@example.com",
            password="short",
            role="admin",
            update_existing=False
        )
