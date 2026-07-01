"""Tests for the simple chunker (SA-021)."""

from app.services import chunking


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def test_empty_segment_yields_nothing():
    assert chunking.chunk_segments([{"page": None, "text": "   "}]) == []


def test_single_short_chunk():
    chunks = chunking.chunk_segments([{"page": 3, "text": _words(50)}], chunk_words=220)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 3


def test_overlap_advances_by_step():
    # 400 words, window 200, overlap 0.25 -> step 150 -> starts at 0,150,300
    chunks = chunking.chunk_segments(
        [{"page": None, "text": _words(400)}], chunk_words=200, overlap=0.25
    )
    assert len(chunks) == 3
    # consecutive chunks should share words (overlap)
    first_words = set(chunks[0]["text"].split())
    second_words = set(chunks[1]["text"].split())
    assert first_words & second_words


def test_pages_preserved_per_segment():
    segs = [{"page": 1, "text": _words(300)}, {"page": 2, "text": _words(300)}]
    chunks = chunking.chunk_segments(segs, chunk_words=200, overlap=0.2)
    pages = {c["page"] for c in chunks}
    assert pages == {1, 2}


def test_invalid_overlap_raises():
    import pytest

    with pytest.raises(ValueError):
        chunking.chunk_segments([{"page": None, "text": "a b c"}], overlap=1.0)
