"""Unit tests for the deterministic knowledge stages (Slice B)."""

from app.knowledge import analysis, chunkers, cleaning, structure


# --- structure (SA-040, SA-042) ---------------------------------------------

def test_parse_markdown_blocks():
    md = "# Title\n\nIntro para line one\nline two\n\n## Sub\n\n- item a\n- item b"
    blocks = structure.parse_markdown(md)
    types = [(b["type"], b["level"]) for b in blocks]
    assert ("heading", 1) in types
    assert ("heading", 2) in types
    assert ("list", 0) in types
    # wrapped lines joined into one paragraph
    para = next(b for b in blocks if b["type"] == "paragraph")
    assert para["text"] == "Intro para line one line two"


def test_parse_plain_heading_heuristic_and_hyphen_repair():
    txt = "Vector Search\n\nHNSW is an approx-\nimate nearest neighbor algorithm."
    blocks = structure.parse_plain(txt)
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["text"] == "Vector Search"
    assert "approximate" in blocks[1]["text"]  # hyphenation repaired


def test_build_sections_nests_heading_path():
    blocks = [
        {"type": "heading", "level": 1, "text": "Vector Search", "page": 1},
        {"type": "heading", "level": 2, "text": "HNSW", "page": 1},
        {"type": "paragraph", "level": 0, "text": "graph based ANN", "page": 1},
    ]
    sections = structure.build_sections(blocks)
    assert len(sections) == 1
    assert sections[0]["heading_path"] == ["Vector Search", "HNSW"]
    assert sections[0]["text"] == "graph based ANN"


# --- cleaning (SA-041) ------------------------------------------------------

def test_clean_removes_page_numbers():
    blocks = [
        {"type": "paragraph", "level": 0, "text": "real content", "page": 1},
        {"type": "paragraph", "level": 0, "text": "12", "page": 1},
        {"type": "paragraph", "level": 0, "text": "Page 3", "page": 3},
    ]
    cleaned = cleaning.clean_blocks(blocks)
    assert [b["text"] for b in cleaned] == ["real content"]


def test_clean_removes_repeated_headers():
    blocks = []
    for page in range(1, 5):
        blocks.append({"type": "paragraph", "level": 0, "text": "ACME Confidential", "page": page})
        blocks.append({"type": "paragraph", "level": 0, "text": f"body {page}", "page": page})
    cleaned = cleaning.clean_blocks(blocks)
    texts = [b["text"] for b in cleaned]
    assert "ACME Confidential" not in texts
    assert "body 1" in texts


def test_clean_normalizes_whitespace():
    blocks = [{"type": "paragraph", "level": 0, "text": "too    much\n\n  space", "page": None}]
    assert cleaning.clean_blocks(blocks)[0]["text"] == "too much space"


# --- chunkers (SA-052, SA-054) ----------------------------------------------

def test_detect_doc_type():
    assert chunkers.detect_doc_type("def f(): return {a: 1}\n```")[0] == "code"
    assert chunkers.detect_doc_type("Abstract\nWe study X. References [1] et al.")[0] == "paper"
    assert chunkers.detect_doc_type("Just some ordinary prose.")[0] == "general"


def test_sliding_windows_overlap():
    words = [f"w{i}" for i in range(400)]
    windows = chunkers.sliding_windows(words, size=200, overlap=0.25)
    assert len(windows) == 3
    assert set(windows[0]) & set(windows[1])  # overlap


def test_multi_level_small_yields_more_than_large():
    section = {"heading_path": ["S"], "page": 1, "text": " ".join(f"w{i}" for i in range(1000))}
    chunks = chunkers.chunk_multi_level([section], chunkers.DEFAULT_LEVELS, overlap=0.2)
    levels = {lv: sum(1 for c in chunks if c["level"] == lv) for lv in ("large", "medium", "small")}
    assert levels["small"] > levels["large"] >= 1


# --- analysis (SA-055, SA-057) ----------------------------------------------

def test_keywords_rank_by_frequency_excluding_stopwords():
    kws = analysis.extract_keywords("HNSW HNSW graph and the and vector HNSW graph")
    assert kws[0] == "hnsw"
    assert "and" not in kws and "the" not in kws


def test_quality_score_penalizes_garbage():
    good = analysis.quality_score("This is a clean, readable paragraph about vector search.")
    junk = analysis.quality_score("@#$ 12 %^& 999 ~~~")
    assert good > 80
    assert junk < good
