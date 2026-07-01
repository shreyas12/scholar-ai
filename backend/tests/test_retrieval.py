"""Tests for deterministic retrieval quality (Slice E-det: SA-112/113/114)."""

from app.services import retrieval


def _hit(chunk_id, score, section_id=None, text="x"):
    return {"chunk_id": chunk_id, "score": score, "section_id": section_id, "text": text}


# --- rerank (SA-112) --------------------------------------------------------

def test_rerank_prefers_section_diversity():
    hits = [
        _hit("a:l:0", 0.9, "a:sec:0"),
        _hit("a:s:0", 0.88, "a:sec:0"),  # same section as top → deprioritized
        _hit("a:l:1", 0.80, "a:sec:1"),
    ]
    out = retrieval.rerank(hits, top_k=2)
    assert [h["chunk_id"] for h in out] == ["a:l:0", "a:l:1"]  # two distinct sections


def test_rerank_backfills_when_few_sections():
    hits = [
        _hit("a:l:0", 0.9, "a:sec:0"),
        _hit("a:s:0", 0.88, "a:sec:0"),
    ]
    out = retrieval.rerank(hits, top_k=2)
    assert len(out) == 2  # only one section, but backfilled to top_k


# --- confidence (SA-114) ----------------------------------------------------

def test_confidence_empty():
    c = retrieval.retrieval_confidence([])
    assert c["confidence"] == 0
    assert c["relevant_chunks"] == 0


def test_confidence_high_for_strong_hits():
    hits = [_hit("a", 0.85), _hit("b", 0.8), _hit("c", 0.78)]
    c = retrieval.retrieval_confidence(hits)
    assert c["confidence"] > 80
    assert c["relevant_chunks"] == 3
    assert "avg similarity" in c["reason"]


def test_confidence_low_for_weak_hits():
    hits = [_hit("a", 0.35), _hit("b", 0.32)]
    c = retrieval.retrieval_confidence(hits)
    assert c["confidence"] < 30
    assert c["relevant_chunks"] == 0  # below 0.5 threshold


# --- compression (SA-113) ---------------------------------------------------

def test_compress_respects_budget():
    hits = [_hit("a", 0.9, text="x" * 100), _hit("b", 0.8, text="y" * 100)]
    out = retrieval.compress_context(hits, budget_chars=100)
    assert len(out) == 1  # second block doesn't fit
    assert out[0]["chunk_id"] == "a"


def test_compress_truncates_tail_when_room():
    hits = [_hit("a", 0.9, text="x" * 60), _hit("b", 0.8, text="y" * 500)]
    out = retrieval.compress_context(hits, budget_chars=400)
    assert len(out) == 2
    assert out[1]["text"].endswith("…")  # tail truncated to fit
    assert len(out[1]["text"]) <= 400


def test_compress_under_budget_keeps_all():
    hits = [_hit("a", 0.9, text="short"), _hit("b", 0.8, text="also short")]
    assert len(retrieval.compress_context(hits, budget_chars=10_000)) == 2


# --- LLM-assisted retrieval (SA-110/111/115) --------------------------------

async def test_retrieve_advanced_merges_expanded(monkeypatch):
    async def fake_gen(self, prompt, model=None):
        return '["hnsw graph variant"]'

    monkeypatch.setattr(retrieval.OllamaClient, "generate", fake_gen)

    seen_queries = []

    def fake_retrieve(space_id, q, k):
        seen_queries.append(q)
        if "variant" in q:
            return [_hit("c2", 0.7, "s2")]
        return [_hit("c1", 0.9, "s1")]

    monkeypatch.setattr(retrieval._default_retriever, "retrieve", fake_retrieve)

    hits = await retrieval.retrieve_advanced("ml", "hnsw?", top_k=5, expand=True)
    assert {h["chunk_id"] for h in hits} == {"c1", "c2"}  # merged across queries
    assert any("variant" in q for q in seen_queries)


async def test_retrieve_advanced_graceful_when_ollama_down(monkeypatch):
    from app.services.ollama_client import OllamaUnavailable

    async def boom(self, prompt, model=None):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(retrieval.OllamaClient, "generate", boom)
    monkeypatch.setattr(
        retrieval._default_retriever, "retrieve", lambda s, q, k: [_hit("c1", 0.9, "s1")]
    )

    # expansion requested but Ollama down → falls back to the plain query
    hits = await retrieval.retrieve_advanced("ml", "q", top_k=5, expand=True, multi=True)
    assert [h["chunk_id"] for h in hits] == ["c1"]
