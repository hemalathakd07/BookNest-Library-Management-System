# BookNest — Digital Library

BookNest is a college capstone API for a small digital library. Students can browse books and borrow or return them. Librarians manage the catalog and can help with returns. Admins can also delete books that have no borrowing history.

## Roles

| Role | What this person can do |
|---|---|
| Student | View books, borrow a book, return their own book, and view their own history |
| Librarian | Everything a student can view, plus create and update books, view all borrow records, and return any book |
| Admin | Everything a librarian can do, plus delete a book that has no borrowing history |

Visitors who are not logged in can view books. They cannot borrow, return, or change the catalog. Librarians cannot delete books. Only students can borrow. Public registration always creates a student.

## Features

- Student registration and login with hashed passwords and JWT access tokens
- Role checks for student, librarian, and admin
- Book catalog with search, availability filter, create, update, and admin delete
- Borrowing with a 14-day loan period, copy tracking, and one active borrow per student per book
- Returns with overdue fines stored on the borrow record
- Swagger documentation

## Technology stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- PyJWT
- pwdlib for password hashing

## Project structure

```text
BookNest/
├── routers/
│   ├── auth.py          # register, login, current user
│   ├── books.py         # catalog CRUD and search
│   └── borrow.py        # borrow, history, return, fines
├── tests/               # pytest suite (in-memory database)
├── auth_utils.py        # password hashing and JWT helpers
├── create_staff.py      # local librarian/admin setup
├── create_tables.py     # creates tables in PostgreSQL
├── database.py          # database connection
├── dependencies.py      # current user and role checks
├── main.py              # FastAPI application
├── models.py            # User, Book, BorrowRecord
├── schemas.py           # request and response models
├── requirements.txt
└── .env                 # local secrets, not committed
```

## Setup on Windows PowerShell

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked, run this once for your user, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Environment variables

Create a `.env` file in the project folder. Do not commit it. Use your own values. The names are:

| Name | Purpose |
|---|---|
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host, usually `localhost` |
| `DB_PORT` | PostgreSQL port, usually `5432` |
| `DB_NAME` | Development database name |
| `JWT_SECRET_KEY` | Secret used to sign login tokens |
| `JWT_ALGORITHM` | Optional. Defaults to `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional. Defaults to `30` |
| `LOAN_PERIOD_DAYS` | Optional. Defaults to `14` |
| `FINE_PER_DAY` | Optional. Defaults to `1.00` per overdue day |
| `STAFF_NAME` | Optional, only for `create_staff.py` |
| `STAFF_EMAIL` | Optional, only for `create_staff.py` |
| `STAFF_PASSWORD` | Optional, only for `create_staff.py` |
| `STAFF_ROLE` | Optional. `librarian` or `admin` |
| `STAFF_UPDATE_EXISTING` | Optional. `true` to update an existing account |

`LOAN_PERIOD_DAYS` and `FINE_PER_DAY` are read in `routers/borrow.py`. A book returned on or before the due date has a fine of `0.00`. Each overdue day adds `FINE_PER_DAY`.

## Database tables

The application does not drop or recreate an existing database. With the virtual environment active and `.env` pointing at your PostgreSQL database, create missing tables with:

```powershell
.\.venv\Scripts\python.exe create_tables.py
```

`create_tables.py` uses SQLAlchemy `create_all`. It adds tables that are not there yet. It does not delete users, books, or borrow records.

There is no separate migration folder. The current tables are `users`, `books`, and `borrow_records`.

Alembic is installed with the other packages, but this project does not have an Alembic configuration. That is intentional. The tables already match `models.py`, and `create_all` does not delete data. A migration would only be needed if a future change adds or changes a column. Do not drop or recreate the database to “set up” migrations.

## Run the API

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## API endpoints

### Authentication

| Method | Path | Who | Result |
|---|---|---|---|
| `POST` | `/auth/register` | public | Creates a student. Always role `student`. `201` |
| `POST` | `/auth/staff/register` | admin | Creates a librarian or admin. Students and librarians receive `403`. `201` |
| `POST` | `/auth/login` | public | Returns a bearer token. `200` or `401` |
| `GET` | `/auth/me` | logged-in user | Returns the current profile. `200` or `401` |

### Books

| Method | Path | Who | Result |
|---|---|---|---|
| `GET` | `/books/` | public | Lists books. Filters: `title`, `author`, `category`, `isbn`, `available_only` |
| `GET` | `/books/{book_id}` | public | One book, or `404` |
| `POST` | `/books/` | librarian, admin | Creates a book. Duplicate ISBN returns `409` |
| `PATCH` | `/books/{book_id}` | librarian, admin | Updates a book. `404` if missing, `409` for ISBN or copy conflicts |
| `DELETE` | `/books/{book_id}` | admin | Deletes a book with no borrow history. `204`, `403`, `404`, or `409` |

Students and visitors can view books. Changing `total_copies` keeps the number of borrowed copies the same. The new total cannot be lower than the number already borrowed.

### Borrowing and returns

| Method | Path | Who | Result |
|---|---|---|---|
| `POST` | `/borrow/` | student | Borrows a book. Body: `{"book_id": 1}` |
| `GET` | `/borrow/my-history` | logged-in user | That user's own records |
| `GET` | `/borrow/` | librarian, admin | All borrow records |
| `GET` | `/borrow/{record_id}` | owner, librarian, admin | One record. Other students get `403` |
| `POST` | `/borrow/{record_id}/return` | owner, librarian, admin | Returns the book and stores the fine |

Borrowing fails with `409` when no copies are available or the student already has that book borrowed. Returning an already returned record also returns `409`. A missing book or record returns `404`. Invalid JSON or fields return `422`.

In Swagger, call `POST /auth/login`, copy only the `access_token` value, click **Authorize**, and paste that value. Do not include the word `Bearer`. Swagger adds that itself.

A token lasts `ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes unless you set another value). If Swagger returns **401** with “Token has expired” or “Could not validate credentials,” log in again and authorize with the new token. A valid student token that is not allowed to change books returns **403**, not **401**.

Borrowing locks the book row on PostgreSQL so two people cannot take the last copy together. The automated tests use SQLite, which does not apply that lock, so those tests do not prove the PostgreSQL lock.

## Create a staff account

Public registration cannot create a librarian or admin. From the project folder, run:

```powershell
.\.venv\Scripts\python.exe create_staff.py
```

The script asks for a name, email, hidden password, and role (`librarian` or `admin`). If the email already exists, it asks before changing that account.

To run it without prompts, set `STAFF_NAME`, `STAFF_EMAIL`, `STAFF_PASSWORD`, and `STAFF_ROLE` in the environment for that command. Add `STAFF_UPDATE_EXISTING=true` only when you intend to change an existing account. Do not put staff passwords in the committed project.

## Run tests

The pytest suite uses an in-memory SQLite database. It does not write to your PostgreSQL database.

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

The older `test_*.py` files in the project folder are manual scripts. `pytest` is configured to run only the `tests` folder.

## Known limitations

- Login tokens expire. The default is 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`). There is no logout button that cancels a token early.
- Automated tests use SQLite. They do not, by themselves, prove that PostgreSQL locks the book row.
- On PostgreSQL, borrowing and returning lock the book row until the request finishes. That stops two overlapping borrows from taking the last copy. SQLite ignores that lock.
- Alembic is not configured. `create_tables.py` creates missing tables and does not change rows that already exist.
- A book with borrowing history cannot be deleted.
#   B o o k N e s t - L i b r a r y - M a n a g e m e n t - S y s t e m  
 