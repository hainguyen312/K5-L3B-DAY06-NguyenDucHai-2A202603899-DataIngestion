"""Persistent vector store on Chroma (local PersistentClient, cosine, HNSW).

pgvector was the first choice, but the pgvector Docker image could not be pulled
(Docker Desktop proxy timeout to registry-1.docker.io, see results/run_log.md);
GUIDE.md allows a local Chroma store as the fallback. One collection per strategy,
same metric and HNSW settings for all three.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Chunk

HNSW = {"space": "cosine", "ef_construction": 200, "ef_search": 200, "max_neighbors": 32}
_META_KEYS = ("document_id", "source", "page", "page_id", "doc_type", "section", "title",
              "version", "char_start", "char_end", "content_hash", "strategy")


class ChromaStore:
    def __init__(self, path: Path, dimensions: int, model_name: str) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=str(path))
        self.dimensions = dimensions
        self.model_name = model_name

    def collection(self, strategy: str):
        col = self.client.get_or_create_collection(
            name=f"day6_{strategy}",
            configuration={"hnsw": HNSW},
            metadata={"embedding_model": self.model_name, "dimensions": self.dimensions},
            embedding_function=None,
        )
        meta = col.metadata or {}
        if meta.get("embedding_model") != self.model_name or meta.get("dimensions") != self.dimensions:
            raise RuntimeError(f"collection day6_{strategy} was built with {meta}; "
                               f"refusing to mix with {self.model_name}/{self.dimensions}")
        return col

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        """Idempotent write: stable IDs, upsert, and delete obsolete chunks of re-ingested docs."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError("vector dimension mismatch")
        ids = [c.chunk_id for c in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate chunk IDs in one ingest batch")
        col = self.collection(strategy)
        doc_ids = sorted({c.document_id for c in chunks})
        existing = col.get(where={"document_id": {"$in": doc_ids}}, include=[])["ids"]
        obsolete = sorted(set(existing) - set(ids))
        if obsolete:
            col.delete(ids=obsolete)
        metas = []
        for c in chunks:
            m = {"document_id": c.document_id, "source": c.source, "page": c.page, **c.metadata}
            metas.append({k: m[k] for k in _META_KEYS if k in m})
        for i in range(0, len(ids), 500):
            col.upsert(ids=ids[i:i + 500], embeddings=vectors[i:i + 500],
                       documents=[c.text for c in chunks[i:i + 500]], metadatas=metas[i:i + 500])
        return {"before": len(existing), "written": len(ids), "deleted_obsolete": len(obsolete),
                "after_total": col.count()}

    def count(self, strategy: str) -> int:
        return self.collection(strategy).count()

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where = None
        if filters:
            allowed = {"doc_type", "section", "version", "document_id"}
            bad = set(filters) - allowed
            if bad:
                raise ValueError(f"filter keys not allowed: {bad}")
            clauses = [{k: v} for k, v in filters.items()]
            where = clauses[0] if len(clauses) == 1 else {"$and": clauses}
        res = self.collection(strategy).query(
            query_embeddings=[query_vector], n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"])
        hits = []
        for rank, (cid, doc, meta, dist) in enumerate(zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]), 1):
            hits.append({"rank": rank, "chunk_id": cid, "score": round(1.0 - float(dist), 4),
                         "text": doc, "metadata": meta})
        return hits
