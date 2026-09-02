from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.security import hash_password
from app.models import User
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
def list_users(db: DbSession, _: AdminUser, limit: int = 50, offset: int = 0) -> Page[UserRead]:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    users = (
        db.execute(select(User).order_by(User.id).limit(limit).offset(offset)).scalars().all()
    )
    return Page(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _: AdminUser) -> User:
    email = payload.email.strip().lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered."
        )
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: DbSession, admin: AdminUser) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    data = payload.model_dump(exclude_unset=True)
    if password := data.pop("password", None):
        user.hashed_password = hash_password(password)

    # Guard against an admin locking themselves out of their own instance.
    if user.id == admin.id:
        if data.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )
        if data.get("role") and data["role"] != user.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role.",
            )

    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: int, db: DbSession, current: CurrentUser) -> User:
    if current.id != user_id and current.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user
