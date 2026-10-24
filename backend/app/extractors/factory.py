from app.extractors.base import DocumentExtractor
from app.extractors.docx import DOCXExtractor
from app.extractors.pdf import PDFExtractor
from app.extractors.pptx import PPTXExtractor
from app.extractors.text import TextExtractor


_EXTRACTORS: dict[str, type[DocumentExtractor]] = {
    ".pdf": PDFExtractor,
    ".docx": DOCXExtractor,
    ".pptx": PPTXExtractor,
    ".txt": TextExtractor,
    ".md": TextExtractor,
}


def get_extractor(file_extension: str) -> DocumentExtractor:
    """Return the extractor associated with a file extension."""

    extension = file_extension.lower()

    extractor_class = _EXTRACTORS.get(extension)

    if extractor_class is None:
        raise ValueError(
            f"No extractor available for '{file_extension}'"
        )

    return extractor_class()