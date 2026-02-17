"""
Admin endpoints for user and system management.

Requires admin role to access.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.app import App
from camp44.models.entity import Entity
from camp44.models.refresh_token import RefreshToken
from camp44.models.user import User, UserRead, UserUpdate

router = APIRouter()


def require_admin(current_user: User = Depends(deps.get_current_active_user)) -> User:
    """
    Dependency that requires user to be an admin.

    Checks if user has 'admin' role in their roles array.
    """
    if "admin" not in (current_user.roles or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


# =============================================================================
# Dashboard Stats
# =============================================================================


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """Get admin dashboard statistics."""
    # Count users
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = (
        db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    )

    # Count apps
    total_apps = db.query(func.count(App.id)).scalar() or 0

    # Count entities
    total_entities = db.query(func.count(Entity.id)).scalar() or 0

    # Entity types breakdown
    entity_types = (
        db.query(Entity.name, func.count(Entity.id).label("count"))
        .group_by(Entity.name)
        .all()
    )

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
        },
        "apps": {
            "total": total_apps,
        },
        "entities": {
            "total": total_entities,
            "by_type": {e.name: e.count for e in entity_types},
        },
    }


# =============================================================================
# User Management
# =============================================================================


@router.get("/users", response_model=List[UserRead])
def list_users(
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
) -> List[User]:
    """List all users (admin only)."""
    query = db.query(User)
    if active_only:
        query = query.filter(User.is_active == True)
    return query.offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> User:
    """Get a specific user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> User:
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return crud.user.update_user(session=db, db_user=user, user_in=user_in)


@router.post("/users/{user_id}/activate", response_model=UserRead)
def activate_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> User:
    """Activate a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Deactivate a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deactivating themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/make-admin", response_model=UserRead)
def make_admin(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> User:
    """Grant admin privileges to a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Add 'admin' role if not already present
    if "admin" not in (user.roles or []):
        user.roles = (user.roles or []) + ["admin"]
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/remove-admin", response_model=UserRead)
def remove_admin(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Remove admin privileges from a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from removing their own admin status
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="Cannot remove your own admin privileges"
        )

    # Remove 'admin' role if present
    if "admin" in (user.roles or []):
        user.roles = [r for r in user.roles if r != "admin"]
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    db: Session = Depends(deps.get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Delete a user (admin only). This is permanent!"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Delete related rows that have FK references to the user
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()

    db.delete(user)
    db.commit()
    return {"message": "User deleted", "user_id": str(user_id)}


# =============================================================================
# App Management
# =============================================================================


@router.get("/apps")
def list_apps(
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[dict]:
    """List all apps (admin only)."""
    apps = db.query(App).offset(skip).limit(limit).all()
    return [
        {
            "id": str(app.id),
            "name": app.name,
            "description": app.description,
            "owner_id": str(app.owner_id) if app.owner_id else None,
            "created_at": app.created_at.isoformat()
            if hasattr(app, "created_at") and app.created_at
            else None,
        }
        for app in apps
    ]


# =============================================================================
# Entity Management
# =============================================================================


@router.get("/entities")
def list_entity_types(
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> List[dict]:
    """List all entity types with counts (admin only)."""
    entity_types = (
        db.query(Entity.name, Entity.app_id, func.count(Entity.id).label("count"))
        .group_by(Entity.name, Entity.app_id)
        .all()
    )

    return [
        {"entity_type": e.name, "app_id": str(e.app_id), "count": e.count}
        for e in entity_types
    ]


@router.get("/entities/{app_id}/{entity_type}")
def list_entities(
    app_id: UUID,
    entity_type: str,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[dict]:
    """List entities of a specific type (admin only)."""
    entities = (
        db.query(Entity)
        .filter(Entity.app_id == app_id, Entity.name == entity_type)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(e.id),
            "name": e.name,
            "data": e.data,
            "app_id": str(e.app_id),
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
        for e in entities
    ]


@router.delete("/entities/{entity_id}")
def delete_entity(
    entity_id: UUID,
    db: Session = Depends(deps.get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """Delete an entity (admin only). This is permanent!"""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    db.delete(entity)
    db.commit()
    return {"message": "Entity deleted", "entity_id": str(entity_id)}
