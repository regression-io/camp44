from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from camp44 import crud
from camp44.api import deps, deps_async
from camp44.core.security import create_access_token
from camp44.models.token import Token
from camp44.models.user import User, UserCreate

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(deps_async.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Logs a user in."""
    user = await crud.user.authenticate_async(
        session=db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token, token_type="bearer")


@router.post("/register", response_model=User)
async def register(
    *, db: AsyncSession = Depends(deps_async.get_db), user_in: UserCreate
) -> User:
    """Registers a new user."""
    user = await crud.user.get_user_by_email_async(session=db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    user = await crud.user.create_user_async(session=db, user_in=user_in)
    return user
