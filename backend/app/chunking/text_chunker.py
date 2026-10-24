from datetime import UTC, datetime

from app.models.document_chunk import DocumentChunk
from app.models.extracted_document import DocumentSection


class TextChunker:
    """Splits extracted document sections into retrieval-sized chunks."""

    def __init__(
        self,
        *,
        max_characters: int = 1200,
        overlap_characters: int = 200,
    ) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be greater than zero")

        if overlap_characters < 0:
            raise ValueError("overlap_characters cannot be negative")

        if overlap_characters >= max_characters:
            raise ValueError(
                "overlap_characters must be smaller than max_characters"
            )

        self._max_characters = max_characters
        self._overlap_characters = overlap_characters

    def chunk(
        self,
        sections: list[DocumentSection],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        for section in sections:
            section_chunks = self._chunk_section(section)

            for section_chunk in section_chunks:
                chunks.append(
                    {
                        "chunk_number": len(chunks) + 1,
                        "section_number": section["section_number"],
                        "location_label": section["location_label"],
                        "text": section_chunk,
                        "created_at": datetime.now(UTC),
                    }
                )

        return chunks

    def _chunk_section(
        self,
        section: DocumentSection,
    ) -> list[str]:
        text = section["text"].strip()

        if not text:
            return []

        if len(text) <= self._max_characters:
            return [text]

        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = min(
                start + self._max_characters,
                len(text),
            )

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            start = end - self._overlap_characters

        return chunks