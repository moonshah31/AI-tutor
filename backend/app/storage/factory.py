from app.config import Settings
from app.storage.base import FileStorage
from app.storage.local import LocalFileStorage
from app.storage.r2 import R2FileStorage


def create_file_storage(settings: Settings) -> FileStorage:
    """Build the configured document storage implementation."""
    if settings.document_storage_backend == "local":
        return LocalFileStorage(settings.document_storage_path)

    required_settings = {
        "R2_ENDPOINT_URL": settings.r2_endpoint_url,
        "R2_BUCKET": settings.r2_bucket,
        "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
    }
    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise ValueError(
            "R2 storage requires these settings: " + ", ".join(missing)
        )

    return R2FileStorage(
        endpoint_url=settings.r2_endpoint_url,
        bucket=settings.r2_bucket,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
    )
