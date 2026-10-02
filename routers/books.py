from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_role
from models import Book, BorrowRecord, User
from schemas import BookCreate, BookResponse, BookUpdate

router = APIRouter(
    prefix="/books",
    tags=["Books"]
)


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _integrity_detail(error: IntegrityError) -> str:
    message = str(getattr(error, "orig", error)).lower()
    if "unique" in message or "duplicate" in message:
        return "A book with this ISBN already exists"
    return "The book could not be saved because it conflicts with a database rule"


def _get_book_or_404(db: Session, book_id: int) -> Book:
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
    return book


@router.post(
    "/",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED
)
def create_book(
    book_data: BookCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("librarian", "admin"))
):
    existing_book = db.query(Book).filter(
        Book.isbn == book_data.isbn
    ).first()

    if existing_book:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A book with this ISBN already exists"
        )

    new_book = Book(
        title=book_data.title,
        author=book_data.author,
        isbn=book_data.isbn,
        category=book_data.category,
        total_copies=book_data.total_copies,
        available_copies=book_data.total_copies
    )

    db.add(new_book)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_integrity_detail(error)
        )

    db.refresh(new_book)
    return new_book


@router.get("/", response_model=list[BookResponse])
def get_all_books(
    title: str | None = Query(default=None),
    author: str | None = Query(default=None),
    category: str | None = Query(default=None),
    isbn: str | None = Query(default=None),
    available_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    query = db.query(Book)

    if title:
        query = query.filter(
            Book.title.ilike(f"%{_escape_like(title)}%", escape="\\")
        )

    if author:
        query = query.filter(
            Book.author.ilike(f"%{_escape_like(author)}%", escape="\\")
        )

    if category:
        query = query.filter(
            Book.category.ilike(f"%{_escape_like(category)}%", escape="\\")
        )

    if isbn:
        query = query.filter(Book.isbn == isbn)

    if available_only:
        query = query.filter(Book.available_copies > 0)

    return query.all()


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return _get_book_or_404(db, book_id)


@router.patch("/{book_id}", response_model=BookResponse)
def update_book(
    book_id: int,
    book_data: BookUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("librarian", "admin"))
):
    book = _get_book_or_404(db, book_id)
    updates = {
        key: value
        for key, value in book_data.model_dump(exclude_unset=True).items()
        if value is not None
    }

    if "isbn" in updates and updates["isbn"] != book.isbn:
        existing_book = db.query(Book).filter(
            Book.isbn == updates["isbn"]
        ).first()

        if existing_book:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A book with this ISBN already exists"
            )

    if "total_copies" in updates:
        new_total = updates.pop("total_copies")
        borrowed_copies = book.total_copies - book.available_copies

        if new_total < borrowed_copies:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot set total copies below the number of borrowed copies"
            )

        book.total_copies = new_total
        book.available_copies = new_total - borrowed_copies

    for field, value in updates.items():
        setattr(book, field, value)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_integrity_detail(error)
        )

    db.refresh(book)
    return book


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_book(
    book_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin"))
):
    book = _get_book_or_404(db, book_id)

    has_borrow_history = db.query(BorrowRecord).filter(
        BorrowRecord.book_id == book.id
    ).first()

    if has_borrow_history:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a book that has borrowing history"
        )

    db.delete(book)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a book that has borrowing history"
        )
