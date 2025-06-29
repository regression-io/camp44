from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.user import User, UserRead, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserRead)
def read_user_me(
        current_user: User = Depends(deps.get_current_active_user),
) -> User:
    """Get current user."""
    return current_user


@router.patch("/me", response_model=UserRead)
def update_user_me(
        *, db: Session = Depends(deps.get_db), user_in: UserUpdate, current_user: User = Depends(deps.get_current_active_user)
) -> User:
    """Update own user."""
    user = crud.user.update_user(session=db, db_user=current_user, user_in=user_in)
    return user
