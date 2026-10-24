from datetime import UTC, datetime
from typing import BinaryIO

from app.extractors.base import DocumentExtractor
from app.models.extracted_document import DocumentSection


class TextExtractor(DocumentExtractor):
    """Extracts structured text from plain-text and Markdown files."""

    def extract(
        self,
        file: BinaryIO,
    ) -> list[DocumentSection]:
        content = file.read()

        if isinstance(content, bytes):
            text = content.decode(
                "utf-8",
                errors="replace",
            )
        else:
            text = content

        text = text.strip()

        if not text:
            return []

        return [
            {
                "section_number": 1,
                "location_label": "Document",
                "text": text,
                "created_at": datetime.now(UTC),
            }
        ]