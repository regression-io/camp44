from minio import Minio

from camp44.core.config import settings

_minio_client = None

def get_minio_client():
    """Get a Minio client instance, creating it if it doesn't exist."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.MINIO_URL,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False  # Set to True if using HTTPS
        )
    return _minio_client
