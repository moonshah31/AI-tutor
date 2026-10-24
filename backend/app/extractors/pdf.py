from datetime import UTC, datetime
from typing import BinaryIO

from pypdf import PdfReader

from app.extractors.base import DocumentExtractor
from app.models.extracted_document import DocumentSection


class PDFExtractor(DocumentExtractor):
    """Extracts structured text from PDF documents."""

    def extract(
        self,
        file: BinaryIO,
    ) -> list[DocumentSection]:
        reader = PdfReader(file)

        sections: list[DocumentSection] = []

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = (page.extract_text() or "").strip()

            if not text:
                continue

            sections.append(
                {
                    "section_number": page_number,
                    "location_label": f"Page {page_number}",
                    "text": text,
                    "created_at": datetime.now(UTC),
                }
            )

        return sections