from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# -------------------------
# USER SCHEMAS
# -------------------------

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# TOKEN SCHEMA
# -------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------------------------
# BOOK SCHEMAS
# -------------------------

class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=2, max_length=100)
    isbn: str = Field(min_length=10, max_length=20)
    category: str = Field(min_length=2, max_length=100)
    total_copies: int = Field(ge=0)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=2, max_length=100)
    isbn: str | None = Field(default=None, min_length=10, max_length=20)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    total_copies: int | None = Field(default=None, ge=0)


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    isbn: str
    category: str
    total_copies: int
    available_copies: int

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# BORROWING SCHEMAS
# -------------------------

class BorrowCreate(BaseModel):
    book_id: int = Field(gt=0)


class BorrowRecordResponse(BaseModel):
    id: int
    student_id: int
    book_id: int
    borrow_date: date
    due_date: date
    return_date: date | None
    fine_amount: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)