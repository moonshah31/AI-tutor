from datetime import datetime
from typing import Literal

from pydantic import BaseModel


DocumentStatus = Literal[
    "uploaded",
    "processing",
    "ready",
    "failed",
]


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    content_type: str
    file_extension: str
    file_size: int
    status: DocumentStatus
    processing_error: str | None
    section_count: int
    created_at: datetime
    updated_at: datetime