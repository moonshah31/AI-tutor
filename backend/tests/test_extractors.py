import io

import pytest

from app.extractors.docx import DOCXExtractor
from app.extractors.factory import get_extractor
from app.extractors.pdf import PDFExtractor
from app.extractors.pptx import PPTXExtractor
from app.extractors.text import TextExtractor


def test_text_extractor():
    file = io.BytesIO(
        b"Introduction to Algorithms\n\n"
        b"Algorithms are step-by-step procedures."
    )

    result = TextExtractor().extract(file)

    assert len(result) == 1
    assert result[0]["location_label"] == "Document"
    assert "Introduction to Algorithms" in result[0]["text"]
    assert "Algorithms are step-by-step procedures." in result[0]["text"]


def test_markdown_uses_text_extractor():
    extractor = get_extractor(".md")

    assert isinstance(extractor, TextExtractor)


def test_pdf_factory():
    extractor = get_extractor(".pdf")

    assert isinstance(extractor, PDFExtractor)


def test_docx_factory():
    extractor = get_extractor(".docx")

    assert isinstance(extractor, DOCXExtractor)


def test_pptx_factory():
    extractor = get_extractor(".pptx")

    assert isinstance(extractor, PPTXExtractor)


def test_factory_rejects_unsupported_extension():
    with pytest.raises(
        ValueError,
        match="No extractor available",
    ):
        get_extractor(".exe")