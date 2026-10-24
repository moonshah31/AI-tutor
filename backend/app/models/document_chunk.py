from datetime import datetime
from typing import TypedDict


class DocumentChunk(TypedDict):
    chunk_number: int
    section_number: int
    location_label: str
    text: str
    created_at: datetime