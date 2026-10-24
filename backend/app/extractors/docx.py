from datetime import UTC, datetime
from typing import BinaryIO

from docx import Document

from app.extractors.base import DocumentExtractor
from app.models.extracted_document import DocumentSection


class DOCXExtractor(DocumentExtractor):
    """Extracts structured text from Word documents."""

    def extract(
        self,
        file: BinaryIO,
    ) -> list[DocumentSection]:
        document = Document(file)

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        if not paragraphs:
            return []

        return [
            {
                "section_number": 1,
                "location_label": "Document",
                "text": "\n\n".join(paragraphs),
                "created_at": datetime.now(UTC),
            }
        ]