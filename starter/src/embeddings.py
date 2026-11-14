"""Local Sentence Transformers embedder (real model; no mock fallback)."""
from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """paraphrase-multilingual-MiniLM-L12-v2 is symmetric: no query/document prefixes.

    Vectors are L2-normalized, so cosine similarity == dot product. max_seq_length is
    raised from the model default (128) to 256 word pieces for every strategy, and the
    number of truncated chunks is reported by `count_truncated`.
    """

    def __init__(self, model_name: str, max_seq_length: int = 256, device: str = "cpu",
                 batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer  # raises if not installed

        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = max_seq_length
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size
        self.dimensions = int(self.model.get_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                 show_progress_bar=False, convert_to_numpy=True)
        return vecs.tolist()

    def embed_query(self, question: str) -> list[float]:
        return self.embed_documents([question])[0]

    def token_lengths(self, texts: list[str]) -> list[int]:
        tok = self.model.tokenizer
        return [len(tok(t, add_special_tokens=True)["input_ids"]) for t in texts]
