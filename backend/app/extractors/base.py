from abc import ABC, abstractmethod
from typing import BinaryIO

from app.models.extracted_document import DocumentSection


class DocumentExtractor(ABC):
    """Interface for extracting structured text from documents."""

    @abstractmethod
    def extract(
        self,
        file: BinaryIO,
    ) -> list[DocumentSection]:
        """Extract structured text sections from a document."""
        raise NotImplementedError