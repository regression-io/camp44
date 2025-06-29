from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from camp44.api import deps

router = APIRouter()


@router.post("/{name}")
def run_function(
        *,
        db: Session = Depends(deps.get_db),
        name: str,
        payload: Dict[str, Any] = None
) -> dict:
    """(Stub) Run a backend function."""
    raise HTTPException(status_code=501, detail=f"Function '{name}' not implemented.")
