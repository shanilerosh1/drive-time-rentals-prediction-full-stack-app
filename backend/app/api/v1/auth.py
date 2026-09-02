from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.user import LoginRequest, Token, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _authenticate(db, email: str, password: str) -> User:
    user = db.execute(
        select(User).where(User.email == email.strip().lower())
    ).scalar_one_or_none()
    # Verify even when the user is missing would be ideal for timing symmetry,
    # but a prototype gains little from it; fail plainly and identically.
    if user is None or not verify_password(password, user.hashed_password):
        raise BAD_CREDENTIALS
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated."
        )
    return user


def _token_for(user: User) -> Token:
    return Token(
        access_token=create_access_token(subject=user.email, role=user.role.value),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=Token, summary="Log in with a JSON body")
def login(payload: LoginRequest, db: DbSession) -> Token:
    return _token_for(_authenticate(db, payload.email, payload.password))


@router.post("/token", response_model=Token, summary="OAuth2 password flow (Swagger UI)")
def login_form(
    db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    return _token_for(_authenticate(db, form.username, form.password))


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    return user
