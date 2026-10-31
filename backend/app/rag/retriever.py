"""Hybrid retrieval: pgvector semantic search + PostgreSQL full-text search, fused with
Reciprocal Rank Fusion, then re-ranked with product boosting and a relevance score."""
import math
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Product
from app.models.user import User
from app.rag.embeddings import embed_query, tokenize


@dataclass
class RetrievedChunk:
    id: int
    source_type: str
    source_id: int
    document_id: int | None
    product_id: int | None
    title: str
    section: str | None
    category: str
    verified: bool
    source_url: str | None
    version: int
    content: str
    meta: dict
    source_updated_at: datetime | None
    vector_score: float = 0.0
    keyword_rank: float = 0.0
    coverage: float = 0.0
    fused: float = 0.0
    relevance: float = 0.0


@dataclass
class ProductMatch:
    products: list[Product] = field(default_factory=list)
    ambiguous: list[Product] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def detect_products(db: Session, question: str) -> ProductMatch:
    """Finds products named in the question by model number or name; flags ambiguous family names."""
    q_norm = _norm(question)
    q_lower = question.lower()
    q_tokens = set(tokenize(question))
    products = db.scalars(select(Product).where(Product.status != "archived")).all()
    exact: list[Product] = []
    partial: dict[int, Product] = {}
    for p in products:
        model = _norm(p.model_number or "")
        name_l = p.name.lower()
        if (model and len(model) >= 3 and model in q_norm) or name_l in q_lower or (len(_norm(p.name)) >= 4 and _norm(p.name) in q_norm):
            exact.append(p)
            continue
        # family / first-word match, e.g. "AquaPure" for "AquaPure 500"
        name_tokens = [t for t in tokenize(p.name) if not t.isdigit() and len(t) >= 4]
        if name_tokens and name_tokens[0] in q_tokens and (not p.brand or name_tokens[0] != p.brand.lower()):
            partial[p.id] = p
    if exact:
        # Prefer longest match (e.g. "AquaPure 700 Pro" over "AquaPure 700")
        exact.sort(key=lambda p: -len(p.name))
        chosen: list[Product] = []
        for p in exact:
            if not any(p.name.lower() in c.name.lower() and p.id != c.id for c in chosen):
                chosen.append(p)
        def pos(p: Product) -> int:
            for needle in (p.name.lower(), (p.model_number or "").lower()):
                if needle and needle in q_lower:
                    return q_lower.index(needle)
            return len(q_lower)

        return ProductMatch(products=sorted(chosen, key=pos))
    if len(partial) > 1:
        return ProductMatch(ambiguous=list(partial.values()))
    if len(partial) == 1:
        return ProductMatch(products=list(partial.values()))
    return ProductMatch()


_idf_lock = threading.Lock()
_idf_state: dict = {"key": None, "df": {}, "n": 0}


def term_weights(db: Session) -> tuple[dict[str, int], int]:
    """Document frequency of each term across the index (cached until the index changes).
    Used so that rare/unknown question terms (e.g. a product we don't sell) weigh more than generic ones."""
    key = tuple(db.execute(text("SELECT count(*), coalesce(max(id), 0) FROM document_chunks")).one())
    if _idf_state["key"] == key:
        return _idf_state["df"], _idf_state["n"]
    with _idf_lock:
        df: dict[str, int] = {}
        for title, section, content in db.execute(text("SELECT title, coalesce(section, ''), content FROM document_chunks")):
            for t in set(tokenize(f"{title} {section} {content}")):
                df[t] = df.get(t, 0) + 1
        _idf_state.update(key=key, df=df, n=key[0])
    return df, key[0]


def weighted_coverage(q_terms: set[str], c_terms: set[str], df: dict[str, int], n: int) -> float:
    if not q_terms:
        return 0.0
    # Unknown terms weigh like the rarest known terms: enough to sink off-topic questions
    # ("Tesla"), without letting a single filler word ("take") veto a good match.
    weights = {t: math.log((n + 1) / (max(df.get(t, 0), 1) + 0.5)) for t in q_terms}
    total = sum(weights.values()) or 1.0
    return sum(w for t, w in weights.items() if t in c_terms) / total


def _tsquery_terms(question: str) -> str | None:
    terms = []
    for t in tokenize(question):
        t = re.sub(r"[^a-z0-9]", "", t)
        if len(t) >= 2 and t not in terms:
            terms.append(t)
    return " | ".join(terms[:24]) if terms else None


_COLUMNS = (
    "id, source_type, source_id, document_id, product_id, title, section, category, verified, "
    "source_url, version, content, meta, source_updated_at"
)


def hybrid_search(
    db: Session,
    question: str,
    user: User | None,
    top_k: int = 6,
    product_ids: list[int] | None = None,
    categories: list[str] | None = None,
    candidate_pool: int = 30,
) -> list[RetrievedChunk]:
    """Returns chunks ordered by fused relevance. Restricted chunks are hidden from team members."""
    can_see_restricted = bool(user and user.has_role("admin"))
    filters = ["1=1"]
    params: dict = {"pool": candidate_pool}
    if not can_see_restricted:
        filters.append("visibility = 'internal'")
    if categories:
        filters.append("category = ANY(:cats)")
        params["cats"] = categories
    where = " AND ".join(filters)

    qvec = embed_query(question)
    params["qvec"] = str(qvec)
    vec_rows = db.execute(
        text(
            f"SELECT {_COLUMNS}, 1 - (embedding <=> CAST(:qvec AS vector)) AS score FROM document_chunks "
            f"WHERE {where} ORDER BY embedding <=> CAST(:qvec AS vector) LIMIT :pool"
        ),
        params,
    ).mappings().all()

    kw_rows = []
    tsq = _tsquery_terms(question)
    if tsq:
        kw_rows = db.execute(
            text(
                f"SELECT {_COLUMNS}, ts_rank_cd(tsv, to_tsquery('english', :tsq)) AS score FROM document_chunks "
                f"WHERE {where} AND tsv @@ to_tsquery('english', :tsq) ORDER BY score DESC LIMIT :pool"
            ),
            {**params, "tsq": tsq},
        ).mappings().all()

    # Product-specific candidates: always include the mentioned products' own chunks
    prod_rows = []
    if product_ids:
        prod_rows = db.execute(
            text(
                f"SELECT {_COLUMNS}, 1 - (embedding <=> CAST(:qvec AS vector)) AS score FROM document_chunks "
                f"WHERE {where} AND product_id = ANY(:pids) ORDER BY embedding <=> CAST(:qvec AS vector) LIMIT :pool"
            ),
            {**params, "pids": product_ids},
        ).mappings().all()

    chunks: dict[int, RetrievedChunk] = {}

    def get(row) -> RetrievedChunk:
        c = chunks.get(row["id"])
        if c is None:
            c = RetrievedChunk(**{k: row[k] for k in _COLUMNS.replace(" ", "").split(",")})
            chunks[row["id"]] = c
        return c

    k = 60.0
    for rank, row in enumerate(vec_rows):
        c = get(row)
        c.vector_score = float(row["score"] or 0)
        c.fused += 1.0 / (k + rank)
    for rank, row in enumerate(kw_rows):
        c = get(row)
        c.keyword_rank = float(row["score"] or 0)
        c.fused += 1.0 / (k + rank)
    for row in prod_rows:
        c = get(row)
        c.vector_score = float(row["score"] or 0)

    q_terms = set(tokenize(question))
    df, n = term_weights(db)
    for c in chunks.values():
        c_terms = set(tokenize(f"{c.title} {c.section or ''} {c.content}"))
        c.coverage = weighted_coverage(q_terms, c_terms, df, n)
        rel = 0.5 * max(c.vector_score, 0.0) + 0.5 * c.coverage
        if product_ids:
            if c.product_id in product_ids:
                rel += 0.15
                c.fused += 0.02
            elif c.product_id is not None:
                rel -= 0.15
        if not c.verified:
            rel -= 0.05  # prefer verified company information over third-party research
        c.relevance = max(0.0, min(1.0, rel))

    ranked = sorted(chunks.values(), key=lambda c: (c.relevance + c.fused * 5), reverse=True)
    if product_ids and len(product_ids) > 1:
        # comparisons: make sure every product is represented
        picked: list[RetrievedChunk] = []
        per = max(2, top_k // len(product_ids))
        for pid in product_ids:
            picked += [c for c in ranked if c.product_id == pid][:per]
        rest = [c for c in ranked if c not in picked]
        ranked = picked + rest
        return ranked[: max(top_k, len(picked))]
    return ranked[:top_k]
