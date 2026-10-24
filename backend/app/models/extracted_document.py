from datetime import datetime
from typing import TypedDict


class DocumentSection(TypedDict):
    section_number: int
    location_label: str
    text: str
    created_at: datetime


class ExtractedDocument(TypedDict):
    document_id: str
    sections: list[DocumentSection]