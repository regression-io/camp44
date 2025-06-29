from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.core.security import create_access_token
from camp44.models.token import Token
from camp44.models.user import User, UserCreate

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
        db: Session = Depends(deps.get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Logs a user in."""
    user = crud.user.authenticate(
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
def register(
        *, db: Session = Depends(deps.get_db), user_in: UserCreate
) -> User:
    """Registers a new user."""
    user = crud.user.get_user_by_email(session=db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    user = crud.user.create_user(session=db, user_in=user_in)
    return user
