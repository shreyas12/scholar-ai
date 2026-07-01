"""Ollama client wrapper (SA-005).

Thin async wrapper over the local Ollama HTTP API. All calls degrade gracefully:
if Ollama isn't running we raise :class:`OllamaUnavailable` with an actionable
message instead of leaking a raw connection error.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..config import get_settings


class OllamaUnavailable(RuntimeError):
    """Raised when the Ollama server can't be reached or errors out."""


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout if timeout is not None else settings.ollama_timeout

    def _http_timeout(self) -> "httpx.Timeout":
        # Fail fast on connect (server down/unreachable) but allow a long read —
        # local generation is legitimately slow. Keeps graceful fallback snappy.
        return httpx.Timeout(self.timeout, connect=5.0)

    async def is_up(self) -> bool:
        """Cheap reachability + version check. Never raises (fast connect timeout)."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
                resp = await client.get(f"{self.base_url}/api/version")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=2.0)) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(_hint(self.base_url)) from exc

    async def generate(self, prompt: str, *, model: str | None = None) -> str:
        """Single-turn completion. Returns the response text."""
        payload = {"model": model or self.model, "prompt": prompt, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(_hint(self.base_url)) from exc

    def generate_sync(self, prompt: str, *, model: str | None = None) -> str:
        """Blocking completion for use inside the (synchronous) ingest pipeline."""
        payload = {"model": model or self.model, "prompt": prompt, "stream": False}
        try:
            with httpx.Client(timeout=self._http_timeout()) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(_hint(self.base_url)) from exc

    async def generate_stream(
        self, prompt: str, *, model: str | None = None
    ) -> AsyncIterator[str]:
        """Stream a completion token-by-token (SA-031).

        Yields text deltas. Raises :class:`OllamaUnavailable` if the server can't
        be reached before the first token.
        """
        payload = {"model": model or self.model, "prompt": prompt, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        if chunk.get("response"):
                            yield chunk["response"]
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(_hint(self.base_url)) from exc

    async def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> str:
        """Multi-turn chat. ``messages`` is a list of {role, content}."""
        payload = {"model": model or self.model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(_hint(self.base_url)) from exc


def _hint(base_url: str) -> str:
    return (
        f"Could not reach Ollama at {base_url}. Is it running? "
        "Install from https://ollama.com, then `ollama serve` and "
        "`ollama pull qwen3:8b`."
    )
