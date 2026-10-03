from dependencies import get_current_user, require_role
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import StaffCreate, UserCreate, UserResponse, UserLogin, TokenResponse
from auth_utils import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a student account"
)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    hashed_password = hash_password(user_data.password)

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hashed_password,
        role="student"
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    db.refresh(new_user)

    return new_user


@router.post(
    "/staff/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a librarian or admin",
    description=(
        "Only an authenticated admin can create a librarian or admin. "
        "The role must be librarian or admin."
    )
)
def register_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin"))
):
    existing_user = db.query(User).filter(
        User.email == staff_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    new_user = User(
        name=staff_data.name,
        email=staff_data.email,
        hashed_password=hash_password(staff_data.password),
        role=staff_data.role
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in as a student, librarian, or admin"
)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):

    # Find the user by email
    user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    # Check whether the user exists and the password is correct
    if not user or not verify_password(
        user_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create JWT access token
    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get(
    "/me",
    response_model=UserResponse,
    summary="View the logged-in user's profile"
)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user

