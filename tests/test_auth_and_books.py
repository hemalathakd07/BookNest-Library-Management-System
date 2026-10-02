from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt

from auth_utils import JWT_ALGORITHM, JWT_SECRET_KEY
from tests.support import add_staff_user, auth_header, login, register_user

BOOK = {
    "title": "Python Programming",
    "author": "John Smith",
    "isbn": "9781234567890",
    "category": "Programming",
    "total_copies": 5
}


def test_register_login_and_me(client):
    created = register_user(client, "Ananya", "ananya@example.com")
    assert created["role"] == "student"

    privileged = client.post(
        "/auth/register",
        json={
            "name": "Sneaky",
            "email": "sneaky@example.com",
            "password": "student123",
            "role": "admin"
        }
    )
    assert privileged.status_code == 201
    assert privileged.json()["role"] == "student"

    token = login(client, "ananya@example.com")
    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "ananya@example.com"


def test_invalid_login_and_missing_token(client):
    register_user(client, "Ananya", "ananya@example.com")

    invalid = client.post(
        "/auth/login",
        json={"email": "ananya@example.com", "password": "wrongpass"}
    )
    assert invalid.status_code == 401

    missing = client.get("/auth/me")
    assert missing.status_code == 401

    create_book = client.post("/books/", json=BOOK)
    assert create_book.status_code == 401


def test_student_cannot_manage_books_but_can_view_them(client, db):
    register_user(client, "Ananya", "ananya@example.com")
    student_token = login(client, "ananya@example.com")
    add_staff_user(db, "librarian", "librarian@example.com")
    librarian_token = login(client, "librarian@example.com", "staffpass1")

    denied = client.post(
        "/books/",
        json=BOOK,
        headers=auth_header(student_token)
    )
    assert denied.status_code == 403

    created = client.post(
        "/books/",
        json=BOOK,
        headers=auth_header(librarian_token)
    )
    assert created.status_code == 201
    body = created.json()
    assert body["available_copies"] == 5

    public_list = client.get("/books/")
    assert public_list.status_code == 200
    assert len(public_list.json()) == 1

    public_one = client.get(f"/books/{body['id']}")
    assert public_one.status_code == 200


def test_duplicate_isbn_search_update_and_delete(client, db):
    add_staff_user(db, "librarian", "librarian@example.com")
    add_staff_user(db, "admin", "admin@example.com", name="Library Admin")
    librarian = auth_header(login(client, "librarian@example.com", "staffpass1"))
    admin = auth_header(login(client, "admin@example.com", "staffpass1"))

    first = client.post("/books/", json=BOOK, headers=librarian)
    assert first.status_code == 201
    book_id = first.json()["id"]

    duplicate = client.post("/books/", json=BOOK, headers=librarian)
    assert duplicate.status_code == 409

    missing = client.get("/books/999")
    assert missing.status_code == 404

    by_title = client.get("/books/", params={"title": "python"})
    assert by_title.status_code == 200
    assert len(by_title.json()) == 1

    by_author = client.get("/books/", params={"author": "smith"})
    assert len(by_author.json()) == 1

    by_category = client.get("/books/", params={"category": "program"})
    assert len(by_category.json()) == 1

    by_isbn = client.get("/books/", params={"isbn": BOOK["isbn"]})
    assert len(by_isbn.json()) == 1

    available = client.get("/books/", params={"available_only": True})
    assert len(available.json()) == 1

    updated = client.patch(
        f"/books/{book_id}",
        json={"title": "Advanced Python", "total_copies": 8},
        headers=librarian
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Advanced Python"
    assert updated.json()["total_copies"] == 8
    assert updated.json()["available_copies"] == 8

    librarian_delete = client.delete(f"/books/{book_id}", headers=librarian)
    assert librarian_delete.status_code == 403

    deleted = client.delete(f"/books/{book_id}", headers=admin)
    assert deleted.status_code == 204

    gone = client.get(f"/books/{book_id}")
    assert gone.status_code == 404


def test_total_copies_cannot_drop_below_borrowed_count(client, db):
    from models import Book

    add_staff_user(db, "librarian", "librarian@example.com")
    token = auth_header(login(client, "librarian@example.com", "staffpass1"))
    created = client.post("/books/", json=BOOK, headers=token)
    book_id = created.json()["id"]

    db.rollback()
    book = db.query(Book).filter(Book.id == book_id).one()
    book.available_copies = 3
    db.commit()

    rejected = client.patch(
        f"/books/{book_id}",
        json={"total_copies": 1},
        headers=token
    )
    assert rejected.status_code == 409

    accepted = client.patch(
        f"/books/{book_id}",
        json={"total_copies": 4},
        headers=token
    )
    assert accepted.status_code == 200
    assert accepted.json()["available_copies"] == 2
    assert Decimal(str(accepted.json()["total_copies"])) == Decimal("4")


def test_duplicate_registration_returns_409(client):
    register_user(client, "Ananya", "ananya@example.com")
    duplicate = client.post(
        "/auth/register",
        json={
            "name": "Ananya",
            "email": "ananya@example.com",
            "password": "student123"
        }
    )
    assert duplicate.status_code == 409


def test_student_cannot_update_or_delete_and_invalid_tokens_return_401(client, db):
    register_user(client, "Ananya", "ananya@example.com")
    student = auth_header(login(client, "ananya@example.com"))
    add_staff_user(db, "librarian", "librarian@example.com")
    librarian = auth_header(login(client, "librarian@example.com", "staffpass1"))

    created = client.post("/books/", json=BOOK, headers=librarian)
    assert created.status_code == 201
    book_id = created.json()["id"]

    student_update = client.patch(
        f"/books/{book_id}",
        json={"title": "Student Edit", "total_copies": 1},
        headers=student
    )
    assert student_update.status_code == 403

    unchanged = client.get(f"/books/{book_id}")
    assert unchanged.status_code == 200
    assert unchanged.json()["title"] == BOOK["title"]
    assert unchanged.json()["total_copies"] == BOOK["total_copies"]
    assert unchanged.json()["available_copies"] == BOOK["total_copies"]

    student_delete = client.delete(f"/books/{book_id}", headers=student)
    assert student_delete.status_code == 403

    missing_token = client.patch(
        f"/books/{book_id}",
        json={"title": "No Token"}
    )
    assert missing_token.status_code == 401

    invalid_token = client.patch(
        f"/books/{book_id}",
        json={"title": "Bad Token"},
        headers={"Authorization": "Bearer not-a-token"}
    )
    assert invalid_token.status_code == 401
    assert invalid_token.json()["detail"] == "Could not validate credentials"

    expired_token = jwt.encode(
        {
            "sub": "1",
            "role": "librarian",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5)
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    expired = client.patch(
        f"/books/{book_id}",
        json={"title": "Expired"},
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert expired.status_code == 401
    assert expired.json()["detail"] == "Token has expired"


def test_admin_can_create_and_update_books(client, db):
    add_staff_user(db, "admin", "admin@example.com", name="Library Admin")
    admin = auth_header(login(client, "admin@example.com", "staffpass1"))

    created = client.post("/books/", json=BOOK, headers=admin)
    assert created.status_code == 201
    book_id = created.json()["id"]

    updated = client.patch(
        f"/books/{book_id}",
        json={"title": "Admin Edit"},
        headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Admin Edit"
