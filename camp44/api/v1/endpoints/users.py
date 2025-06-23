from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from camp44 import crud
from camp44.api import deps, deps_async
from camp44.models.user import User, UserRead, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> User:
    """Get current user."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_user_me(
    *, db: AsyncSession = Depends(deps_async.get_db), user_in: UserUpdate, current_user: User = Depends(deps.get_current_active_user)
) -> User:
    """Update own user."""
    user = await crud.user.update_user_async(session=db, db_user=current_user, user_in=user_in)
    return user
