import os
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, require_role
from models import Book, BorrowRecord, User
from schemas import BorrowCreate, BorrowRecordResponse

load_dotenv()

# Change the loan length with the LOAN_PERIOD_DAYS environment variable.
# If that variable is not set, a loan lasts 14 days.
LOAN_PERIOD_DAYS = int(os.getenv("LOAN_PERIOD_DAYS", "14"))

# Change the fine with the FINE_PER_DAY environment variable.
# If that variable is not set, the fine is 1.00 currency unit per overdue day.
FINE_PER_DAY = Decimal(os.getenv("FINE_PER_DAY", "1.00"))

if LOAN_PERIOD_DAYS < 1:
    raise ValueError("LOAN_PERIOD_DAYS must be at least 1")

if FINE_PER_DAY < 0:
    raise ValueError("FINE_PER_DAY cannot be negative")

router = APIRouter(
    prefix="/borrow",
    tags=["Borrowing"]
)


def calculate_fine(due_date: date, return_date: date) -> Decimal:
    """Return 0 when the book is back on or before the due date."""
    overdue_days = (return_date - due_date).days
    if overdue_days <= 0:
        return Decimal("0.00")

    fine = Decimal(overdue_days) * FINE_PER_DAY
    return fine.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_record_or_404(db: Session, record_id: int) -> BorrowRecord:
    record = db.query(BorrowRecord).filter(
        BorrowRecord.id == record_id
    ).first()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrow record not found"
        )

    return record


def _student_can_access_record(current_user: User, record: BorrowRecord) -> bool:
    if current_user.role in ("librarian", "admin"):
        return True
    return current_user.id == record.student_id


@router.post(
    "/",
    response_model=BorrowRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Borrow a book as a student"
)
def borrow_book(
    borrow_data: BorrowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can borrow books"
        )

    # Lock this book until the borrow is saved. On PostgreSQL this stops two
    # requests from taking the last copy at the same time. SQLite ignores
    # the lock, so the automated tests do not prove that behavior.
    book = db.query(Book).filter(
        Book.id == borrow_data.book_id
    ).with_for_update().first()

    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )

    if book.available_copies <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No copies of this book are available"
        )

    active_borrow = db.query(BorrowRecord).filter(
        BorrowRecord.student_id == current_user.id,
        BorrowRecord.book_id == book.id,
        BorrowRecord.status == "borrowed"
    ).first()

    if active_borrow:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active borrow for this book"
        )

    borrow_date = date.today()
    book.available_copies -= 1

    record = BorrowRecord(
        student_id=current_user.id,
        book_id=book.id,
        borrow_date=borrow_date,
        due_date=borrow_date + timedelta(days=LOAN_PERIOD_DAYS),
        return_date=None,
        fine_amount=Decimal("0.00"),
        status="borrowed"
    )

    db.add(record)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No copies of this book are available"
        )

    db.refresh(record)
    return record


@router.get(
    "/my-history",
    response_model=list[BorrowRecordResponse],
    summary="View the logged-in user's borrowing history"
)
def get_my_borrow_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    records = db.query(BorrowRecord).filter(
        BorrowRecord.student_id == current_user.id
    ).order_by(BorrowRecord.id.desc()).all()

    return records


@router.get(
    "/",
    response_model=list[BorrowRecordResponse],
    summary="View all borrowing records"
)
def list_borrow_records(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("librarian", "admin"))
):
    records = db.query(BorrowRecord).order_by(
        BorrowRecord.id.desc()
    ).all()

    return records


@router.get(
    "/{record_id}",
    response_model=BorrowRecordResponse,
    summary="View one borrowing record"
)
def get_borrow_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    record = _get_record_or_404(db, record_id)

    if not _student_can_access_record(current_user, record):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource"
        )

    return record


@router.post(
    "/{record_id}/return",
    response_model=BorrowRecordResponse,
    summary="Return a borrowed book"
)
def return_book(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    record = _get_record_or_404(db, record_id)

    if not _student_can_access_record(current_user, record):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource"
        )

    if record.status != "borrowed" or record.return_date is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This borrow record has already been returned"
        )

    book = db.query(Book).filter(
        Book.id == record.book_id
    ).with_for_update().first()

    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )

    if book.available_copies >= book.total_copies:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Available copies cannot exceed total copies"
        )

    return_date = date.today()
    record.return_date = return_date
    record.fine_amount = calculate_fine(record.due_date, return_date)
    record.status = "returned"
    book.available_copies += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Available copies cannot exceed total copies"
        )

    db.refresh(record)
    return record
