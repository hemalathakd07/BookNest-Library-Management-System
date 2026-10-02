from datetime import date, timedelta
from decimal import Decimal

from models import Book, BorrowRecord
from routers.borrow import LOAN_PERIOD_DAYS, calculate_fine
from tests.support import add_staff_user, auth_header, login, register_user

BOOK = {
    "title": "Database Systems",
    "author": "Ada Lovelace",
    "isbn": "9780000000001",
    "category": "Databases",
    "total_copies": 1
}


def _student_token(client, email):
    register_user(client, "Student", email)
    return auth_header(login(client, email))


def _create_book(client, db, isbn="9780000000001", total_copies=1):
    add_staff_user(db, "librarian", "librarian@example.com")
    librarian = auth_header(login(client, "librarian@example.com", "staffpass1"))
    payload = {**BOOK, "isbn": isbn, "total_copies": total_copies}
    response = client.post("/books/", json=payload, headers=librarian)
    assert response.status_code == 201, response.text
    return response.json(), librarian


def test_fine_is_zero_on_time_and_one_unit_per_overdue_day():
    today = date(2026, 10, 2)
    assert calculate_fine(today, today) == Decimal("0.00")
    assert calculate_fine(today, today - timedelta(days=1)) == Decimal("0.00")
    assert calculate_fine(today, today + timedelta(days=3)) == Decimal("3.00")
    assert LOAN_PERIOD_DAYS == 14


def test_student_can_borrow_and_see_only_own_history(client, db):
    book, librarian = _create_book(client, db, total_copies=2)
    student = _student_token(client, "student@example.com")
    other = _student_token(client, "other@example.com")

    denied = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=librarian
    )
    assert denied.status_code == 403

    borrowed = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    assert borrowed.status_code == 201, borrowed.text
    record = borrowed.json()
    assert record["status"] == "borrowed"
    assert record["fine_amount"] == "0.00" or Decimal(record["fine_amount"]) == Decimal("0.00")
    due = date.fromisoformat(record["due_date"])
    borrowed_on = date.fromisoformat(record["borrow_date"])
    assert due - borrowed_on == timedelta(days=14)

    listed = client.get(f"/books/{book['id']}")
    assert listed.json()["available_copies"] == 1

    duplicate = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    assert duplicate.status_code == 409
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 1

    mine = client.get("/borrow/my-history", headers=student)
    assert mine.status_code == 200
    assert len(mine.json()) == 1

    other_history = client.get("/borrow/my-history", headers=other)
    assert other_history.json() == []

    hidden = client.get(f"/borrow/{record['id']}", headers=other)
    assert hidden.status_code == 403

    visible = client.get(f"/borrow/{record['id']}", headers=librarian)
    assert visible.status_code == 200

    staff_list = client.get("/borrow/", headers=librarian)
    assert staff_list.status_code == 200
    assert len(staff_list.json()) == 1

    student_list = client.get("/borrow/", headers=student)
    assert student_list.status_code == 403


def test_unavailable_book_and_missing_book(client, db):
    book, _librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")

    db.rollback()
    stored = db.query(Book).filter(Book.id == book["id"]).one()
    stored.available_copies = 0
    db.commit()

    unavailable = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    assert unavailable.status_code == 409

    missing = client.post(
        "/borrow/",
        json={"book_id": 999},
        headers=student
    )
    assert missing.status_code == 404

    invalid = client.post(
        "/borrow/",
        json={"book_id": 0},
        headers=student
    )
    assert invalid.status_code == 422


def test_return_fine_privacy_and_second_return(client, db):
    book, librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")
    other = _student_token(client, "other@example.com")
    add_staff_user(db, "admin", "admin@example.com", name="Library Admin")
    admin = auth_header(login(client, "admin@example.com", "staffpass1"))

    borrowed = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    record_id = borrowed.json()["id"]

    blocked = client.post(f"/borrow/{record_id}/return", headers=other)
    assert blocked.status_code == 403

    db.rollback()
    record = db.query(BorrowRecord).filter(BorrowRecord.id == record_id).one()
    record.due_date = date.today() - timedelta(days=2)
    db.commit()

    returned = client.post(f"/borrow/{record_id}/return", headers=student)
    assert returned.status_code == 200, returned.text
    body = returned.json()
    assert body["status"] == "returned"
    assert body["return_date"] == date.today().isoformat()
    assert Decimal(body["fine_amount"]) == Decimal("2.00")
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 1

    again = client.post(f"/borrow/{record_id}/return", headers=student)
    assert again.status_code == 409

    cannot_delete = client.delete(f"/books/{book['id']}", headers=admin)
    assert cannot_delete.status_code == 409


def test_librarian_can_return_and_on_time_fine_is_zero(client, db):
    book, librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")

    borrowed = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    record_id = borrowed.json()["id"]

    returned = client.post(
        f"/borrow/{record_id}/return",
        headers=librarian
    )
    assert returned.status_code == 200
    assert Decimal(returned.json()["fine_amount"]) == Decimal("0.00")
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 1


def test_borrow_requires_authentication(client):
    response = client.post("/borrow/", json={"book_id": 1})
    assert response.status_code == 401

    history = client.get("/borrow/my-history")
    assert history.status_code == 401

    one_record = client.get("/borrow/1")
    assert one_record.status_code == 401

    all_records = client.get("/borrow/")
    assert all_records.status_code == 401

    returned = client.post("/borrow/1/return")
    assert returned.status_code == 401


def test_student_can_borrow_again_after_returning(client, db):
    book, _librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")

    first = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    assert first.status_code == 201

    returned = client.post(
        f"/borrow/{first.json()['id']}/return",
        headers=student
    )
    assert returned.status_code == 200
    assert Decimal(returned.json()["fine_amount"]) == Decimal("0.00")

    second = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 0


def test_admin_can_return_a_student_book(client, db):
    book, _librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")
    add_staff_user(db, "admin", "admin@example.com", name="Library Admin")
    admin = auth_header(login(client, "admin@example.com", "staffpass1"))

    borrowed = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    returned = client.post(
        f"/borrow/{borrowed.json()['id']}/return",
        headers=admin
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 1


def test_return_stops_when_available_copies_already_match_total(client, db):
    book, _librarian = _create_book(client, db, total_copies=1)
    student = _student_token(client, "student@example.com")
    borrowed = client.post(
        "/borrow/",
        json={"book_id": book["id"]},
        headers=student
    )
    record_id = borrowed.json()["id"]

    db.rollback()
    stored = db.query(Book).filter(Book.id == book["id"]).one()
    stored.available_copies = stored.total_copies
    db.commit()

    rejected = client.post(f"/borrow/{record_id}/return", headers=student)
    assert rejected.status_code == 409
    assert client.get(f"/books/{book['id']}").json()["available_copies"] == 1
