from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from camp44.api import deps, deps_async

router = APIRouter()


@router.post("/{name}")
async def run_function(
    *, 
    db: AsyncSession = Depends(deps_async.get_db),
    name: str,
    payload: Dict[str, Any] = None
) -> dict:
    """(Stub) Run a backend function."""
    raise HTTPException(status_code=501, detail=f"Function '{name}' not implemented.")
