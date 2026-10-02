from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
    Date,
    Numeric,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func, DateTime
from datetime import date

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="student",
        nullable=False
    )

    borrow_records: Mapped[list["BorrowRecord"]] = relationship(
        back_populates="student"
    )


class Book(Base):
    __tablename__ = "books"

    __table_args__ = (
        CheckConstraint("total_copies >= 0"),
        CheckConstraint("available_copies >= 0"),
        CheckConstraint("available_copies <= total_copies"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )

    author: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    isbn: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    total_copies: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    available_copies: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    borrow_records: Mapped[list["BorrowRecord"]] = relationship(
        back_populates="book"
    )


class BorrowRecord(Base):
    __tablename__ = "borrow_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id"),
        nullable=False
    )

    borrow_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        nullable=False
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    return_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    fine_amount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        default=0.00,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="borrowed",
        nullable=False
    )

    student: Mapped["User"] = relationship(
        back_populates="borrow_records"
    )

    book: Mapped["Book"] = relationship(
        back_populates="borrow_records"
    )