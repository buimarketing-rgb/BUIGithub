"""Text embeddings.

Primary: sentence-transformers/all-MiniLM-L6-v2 (384-dim, runs on CPU).
Fallback: a deterministic feature-hashing embedder (also 384-dim) used automatically when
sentence-transformers or the model weights are unavailable (e.g. offline installs, CI).
The active embedder's signature is stored so the index can be rebuilt when it changes.
"""
import hashlib
import logging
import math
import re
import threading

import numpy as np

from app.core.config import get_settings

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")
_STOP = {
    "the", "a", "an", "of", "to", "and", "or", "is", "are", "was", "be", "for", "in", "on", "at", "by",
    "with", "what", "which", "how", "does", "do", "can", "i", "me", "my", "it", "its", "this", "that",
    "there", "please", "tell", "about", "you", "your", "we", "our", "from", "as", "if", "any", "all",
    "who", "when", "where", "why", "should", "would", "could", "need", "want", "get", "much", "many", "give",
    "know", "has", "have", "will", "should", "these", "those", "they", "them", "than", "then", "also", "some", "take", "takes", "mean", "means",
    "did", "done", "doing", "long", "make", "made", "let", "just", "like", "really", "kindly",
}


def stem(t: str) -> str:
    """Very light suffix stemmer so 'install', 'installed', 'installation' and 'installing' match."""
    if any(c.isdigit() for c in t):
        return t
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    for suffix, min_len in (("ations", 8), ("ation", 7), ("ings", 6), ("ing", 6), ("ed", 5)):
        if len(t) >= min_len and t.endswith(suffix):
            t = t[: -len(suffix)]
            if len(t) >= 3 and t[-1] == t[-2] and t[-1] not in "lsz":  # shipp -> ship, runn -> run
                t = t[:-1]
            return t
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    tokens = []
    for t in _TOKEN_RE.findall(text.lower()):
        if t in _STOP:
            continue
        tokens.append(stem(t))
    return tokens


class HashEmbedder:
    name = "hash-v3"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _features(self, text: str) -> list[tuple[str, float]]:
        toks = tokenize(text)
        feats: list[tuple[str, float]] = [("w:" + t, 1.0) for t in toks]
        feats += [("b:" + a + "_" + b, 0.7) for a, b in zip(toks, toks[1:])]
        for t in toks:
            padded = f"#{t}#"
            feats += [("c:" + padded[i : i + 3], 0.25) for i in range(len(padded) - 2)]
        return feats

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            counts: dict[str, float] = {}
            for f, w in self._features(text):
                counts[f] = counts.get(f, 0.0) + w
            for f, w in counts.items():
                h = hashlib.blake2b(f.encode(), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "little") % self.dim
                sign = 1.0 if h[4] & 1 else -1.0
                out[row, idx] += sign * (1.0 + math.log(w))
            norm = np.linalg.norm(out[row])
            if norm > 0:
                out[row] /= norm
        return out


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, done lazily

        self.model = SentenceTransformer(model_name, device="cpu")
        self.name = f"st:{model_name}"
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )


_embedder = None
_lock = threading.Lock()


def get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    with _lock:
        if _embedder is not None:
            return _embedder
        s = get_settings()
        if s.embedding_provider in ("auto", "sentence-transformers"):
            try:
                emb = SentenceTransformerEmbedder(s.embedding_model)
                if emb.dim != s.embedding_dim:
                    raise ValueError(f"model dim {emb.dim} != EMBEDDING_DIM {s.embedding_dim}")
                _embedder = emb
                log.info("Embeddings: using %s", emb.name)
                return _embedder
            except Exception as exc:
                if s.embedding_provider == "sentence-transformers":
                    raise
                log.warning("Embeddings: sentence-transformers unavailable (%s). Falling back to hash embedder.", exc)
        _embedder = HashEmbedder(s.embedding_dim)
        log.info("Embeddings: using %s", _embedder.name)
        return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embedder().encode(texts).tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
