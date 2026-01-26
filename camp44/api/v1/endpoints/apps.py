import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.app import App, AppCreate, AppRead
from camp44.models.user import User

router = APIRouter()


@router.post("/", response_model=AppRead)
def create_app(
        *, db: Session = Depends(deps.get_db), app_in: AppCreate, current_user: User = Depends(deps.get_current_active_user)
) -> App:
    """Create new app."""
    app = crud.app.create_app(session=db, app_in=app_in, owner=current_user)
    return app


@router.get("/", response_model=List[AppRead])
def read_apps(
        db: Session = Depends(deps.get_db),
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(deps.get_current_active_user),
) -> List[App]:
    """Retrieve apps."""
    apps = crud.app.get_multi_by_owner(
        session=db, owner=current_user, skip=skip, limit=limit
    )
    return apps


@router.get("/{id}", response_model=AppRead)
def read_app(
        *, db: Session = Depends(deps.get_db), id: uuid.UUID, current_user: User = Depends(deps.get_current_active_user)
) -> App:
    """Get app by ID."""
    app = crud.app.get_app(session=db, id=id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return app
