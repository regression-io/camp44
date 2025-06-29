from typing import Any, Dict

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from camp44.api import deps
from camp44.core.s3 import get_minio_client
from camp44.models.app import App

router = APIRouter()

CORE_INTEGRATIONS = [
    {
        "pkg": "Core",
        "fn": "UploadFile",
        "description": "Upload a file to your app's storage.",
        "path": "/api/v1/apps/{app_id}/integrations/Core.UploadFile",
        "method": "POST",
    }
]


@router.get("/")
def discover_integrations(
        *,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path)
) -> dict:
    """Discover available integrations for the app."""
    return {"integrations": CORE_INTEGRATIONS}


@router.post("/{pkg}/{fn}")
def invoke_integration(
        *,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        pkg: str,
        fn: str,
        payload: Dict[str, Any] = None,
) -> dict:
    """Invoke an integration function."""
    integration_id = f"{pkg}.{fn}"

    if integration_id == "Core.UploadFile":
        raise HTTPException(
            status_code=400,
            detail=f"Integration '{integration_id}' should be called via its dedicated endpoint.",
        )

    # In the future, this could dynamically call registered functions.
    raise HTTPException(status_code=501, detail=f"Integration '{integration_id}' not implemented.")


@router.post("/Core.UploadFile")
def upload_file(
        *,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        file: UploadFile = File(...)
) -> dict:
    """Upload a file to the app's bucket."""
    bucket_name = str(app.id)

    # Handle MinIO operations directly
    minio_client = get_minio_client()
    found = minio_client.bucket_exists(bucket_name)
    if not found:
        minio_client.make_bucket(bucket_name)

    # Read file contents
    file_contents = file.file.read()
    file.file.seek(0)  # Reset file position to beginning after reading

    # Upload to MinIO
    minio_client.put_object(
        bucket_name,
        file.filename,
        data=file.file,
        length=len(file_contents),
        content_type=file.content_type
    )

    return {"filename": file.filename, "content_type": file.content_type, "size": len(file_contents)}
