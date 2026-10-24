from app.chunking.text_chunker import TextChunker


def test_short_section_remains_single_chunk():
    sections = [
        {
            "section_number": 1,
            "location_label": "Page 1",
            "text": "Algorithms are step-by-step procedures.",
            "created_at": None,
        }
    ]

    chunks = TextChunker(
    max_characters=100,
    overlap_characters=20,
).chunk(sections)

    assert len(chunks) == 1
    assert chunks[0]["chunk_number"] == 1
    assert chunks[0]["section_number"] == 1
    assert chunks[0]["location_label"] == "Page 1"
    assert chunks[0]["text"] == (
        "Algorithms are step-by-step procedures."
    )


def test_long_section_is_split_into_multiple_chunks():
    sections = [
        {
            "section_number": 2,
            "location_label": "Page 2",
            "text": "A" * 2500,
            "created_at": None,
        }
    ]

    chunks = TextChunker(
        max_characters=1000,
        overlap_characters=100,
    ).chunk(sections)

    assert len(chunks) == 3
    assert all(
        len(chunk["text"]) <= 1000
        for chunk in chunks
    )


def test_chunk_numbers_are_global_across_sections():
    sections = [
        {
            "section_number": 1,
            "location_label": "Page 1",
            "text": "First page content.",
            "created_at": None,
        },
        {
            "section_number": 2,
            "location_label": "Page 2",
            "text": "Second page content.",
            "created_at": None,
        },
    ]

    chunks = TextChunker(
    max_characters=100,
    overlap_characters=20,
).chunk(sections)

    assert [chunk["chunk_number"] for chunk in chunks] == [1, 2]
    assert chunks[0]["section_number"] == 1
    assert chunks[1]["section_number"] == 2


def test_empty_sections_are_ignored():
    sections = [
        {
            "section_number": 1,
            "location_label": "Page 1",
            "text": "   ",
            "created_at": None,
        }
    ]

    chunks = TextChunker().chunk(sections)

    assert chunks == []


def test_invalid_chunk_configuration_is_rejected():
    try:
        TextChunker(
            max_characters=100,
            overlap_characters=100,
        )
        assert False
    except ValueError as error:
        assert "smaller than max_characters" in str(error)