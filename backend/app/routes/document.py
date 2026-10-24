
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.constants.document import (
    ALLOWED_DOCUMENT_CONTENT_TYPES,
    ALLOWED_DOCUMENT_EXTENSIONS,
    get_file_extension,
)
from app.database import get_database
from app.dependencies import get_current_user
from app.schemas.document import DocumentResponse
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.storage.local import LocalFileStorage


router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


def get_document_service(
    database: Annotated[
        AsyncIOMotorDatabase,
        Depends(get_database),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> DocumentService:
    storage = LocalFileStorage(settings.document_storage_path)

    return DocumentService(
        database=database,
        storage=storage,
    )


def get_document_processing_service(
    database: Annotated[
        AsyncIOMotorDatabase,
        Depends(get_database),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> DocumentProcessingService:
    storage = LocalFileStorage(settings.document_storage_path)

    return DocumentProcessingService(
        database=database,
        storage=storage,
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
    processing_service: Annotated[
        DocumentProcessingService,
        Depends(get_document_processing_service),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> DocumentResponse:
    filename = file.filename or ""
    file_extension = get_file_extension(filename)

    if file_extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported document type",
        )

    allowed_content_types = ALLOWED_DOCUMENT_CONTENT_TYPES[file_extension]

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "File content type does not match the selected document type"
            ),
        )

    max_size = settings.max_document_size_mb * 1024 * 1024
    file_size = 0

    try:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)

            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"Document exceeds the maximum allowed size "
                        f"of {settings.max_document_size_mb} MB"
                    ),
                )

        await file.seek(0)

        document = await service.create(
            user_id=current_user["_id"],
            file=file.file,
            original_filename=filename,
            content_type=file.content_type,
            file_extension=file_extension,
            file_size=file_size,
        )

        await processing_service.process(
            user_id=current_user["_id"],
            document_id=document.id,
        )

        return await service.get_for_user(
            user_id=current_user["_id"],
            document_id=document.id,
        )

    finally:
        await file.close()


@router.get(
    "",
    response_model=list[DocumentResponse],
)
async def list_documents(
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
) -> list[DocumentResponse]:
    return await service.list_for_user(
        user_id=current_user["_id"],
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
) -> DocumentResponse:
    return await service.get_for_user(
        user_id=current_user["_id"],
        document_id=document_id,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
) -> None:
    await service.delete(
        user_id=current_user["_id"],
        document_id=document_id,
    )
