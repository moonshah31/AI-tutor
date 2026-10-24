from datetime import datetime
from typing import Literal, TypedDict

from bson import ObjectId


DocumentStatus = Literal[
    "uploaded",
    "processing",
    "ready",
    "failed",
]


class DocumentSectionDocument(TypedDict):
    section_number: int
    location_label: str
    text: str
    created_at: datetime


class DocumentDocument(TypedDict):
    _id: ObjectId
    user_id: ObjectId
    original_filename: str
    stored_filename: str
    content_type: str
    file_extension: str
    file_size: int
    storage_reference: str
    status: DocumentStatus
    processing_error: str | None
    sections: list[DocumentSectionDocument]
    created_at: datetime
    updated_at: datetime