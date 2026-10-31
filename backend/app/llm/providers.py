"""Model-provider abstraction. Swap models via settings without touching application code.

- OllamaProvider: local open-source models (default, free).
- OpenAICompatibleProvider: any OpenAI-compatible API (OpenAI, Groq, OpenRouter, Together,
  LM Studio, vLLM, llama.cpp server...). Configured only through environment variables.
- ExtractiveProvider (in app.rag.extractive): no model at all - composes answers directly from
  retrieved, verified knowledge. Used when no LLM is configured/reachable.
"""
import json
import logging
from collections.abc import Iterator

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    pass


class LLMProvider:
    name = "base"

    def stream_chat(self, messages: list[dict], temperature: float) -> Iterator[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def health(self) -> dict:  # pragma: no cover - interface
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str) -> None:
        s = get_settings()
        self.base = s.ollama_base_url.rstrip("/")
        self.model = model
        self.timeout = s.llm_timeout_seconds

    def stream_chat(self, messages: list[dict], temperature: float) -> Iterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True, "options": {"temperature": temperature}}
        try:
            with httpx.stream("POST", f"{self.base}/api/chat", json=payload, timeout=httpx.Timeout(self.timeout, connect=3)) as r:
                if r.status_code != 200:
                    r.read()
                    raise ProviderUnavailable(f"Ollama returned {r.status_code}: {r.text[:200]}")
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise ProviderUnavailable(data["error"])
                    token = data.get("message", {}).get("content")
                    if token:
                        yield token
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Cannot reach Ollama at {self.base}: {exc}") from exc

    def health(self) -> dict:
        try:
            r = httpx.get(f"{self.base}/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            ok = any(m == self.model or m.split(":")[0] == self.model.split(":")[0] for m in models)
            return {"ok": ok, "detail": "ready" if ok else f"model '{self.model}' not pulled (run: ollama pull {self.model})", "models": models}
        except Exception as exc:
            return {"ok": False, "detail": f"Ollama unreachable: {exc}"}


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str) -> None:
        s = get_settings()
        self.base = s.openai_base_url.rstrip("/")
        self.key = s.openai_api_key
        self.model = model
        self.timeout = s.llm_timeout_seconds

    def stream_chat(self, messages: list[dict], temperature: float) -> Iterator[str]:
        if not self.key and "localhost" not in self.base and "127.0.0.1" not in self.base:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured")
        headers = {"Authorization": f"Bearer {self.key or 'none'}"}
        payload = {"model": self.model, "messages": messages, "stream": True, "temperature": temperature}
        try:
            with httpx.stream(
                "POST", f"{self.base}/chat/completions", json=payload, headers=headers, timeout=httpx.Timeout(self.timeout, connect=5)
            ) as r:
                if r.status_code != 200:
                    r.read()
                    raise ProviderUnavailable(f"Provider returned {r.status_code}: {r.text[:200]}")
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    choice = (json.loads(data).get("choices") or [{}])[0]
                    token = (choice.get("delta") or {}).get("content")
                    if token:
                        yield token
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Cannot reach {self.base}: {exc}") from exc

    def health(self) -> dict:
        if not self.key:
            return {"ok": False, "detail": "OPENAI_API_KEY not set"}
        try:
            r = httpx.get(f"{self.base}/models", headers={"Authorization": f"Bearer {self.key}"}, timeout=5)
            return {"ok": r.status_code == 200, "detail": "ready" if r.status_code == 200 else f"HTTP {r.status_code}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}


def build_provider(provider: str, model: str | None) -> LLMProvider | None:
    """Returns an LLM provider, or None for extractive (no-LLM) mode."""
    s = get_settings()
    if provider == "ollama":
        return OllamaProvider(model or s.ollama_model)
    if provider == "openai":
        return OpenAICompatibleProvider(model or s.openai_model)
    return None
