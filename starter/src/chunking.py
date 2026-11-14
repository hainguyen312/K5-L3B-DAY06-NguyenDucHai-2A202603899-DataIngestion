"""Fixed-size (strategy A) and structure-aware (strategy B/C) chunking.

Chunks never cross a source-unit ("page") boundary, so every chunk maps to
exactly one (document_id, page) for traceability.
"""
from __future__ import annotations

import hashlib
import re

from .ingestion import heading_of, split_paragraphs
from .models import Chunk, DocumentPage


def _section_at(page: DocumentPage, offset: int) -> str:
    """Last heading that starts at or before `offset` in the page, else the inherited one."""
    section = page.metadata.get("section", "")
    for m in re.finditer(r"(?m)^# (.+)$", page.text):
        if m.start() <= offset:
            section = m.group(1).strip()
        else:
            break
    return section


def _make(page: DocumentPage, strategy: str, idx: int, text: str, start: int) -> Chunk:
    meta = dict(page.metadata)
    meta.update(
        section=_section_at(page, start),
        char_start=start,
        char_end=start + len(text),
        content_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
        strategy=strategy,
    )
    return Chunk(f"{strategy}:{meta['page_id']}:c{idx:02d}", page.document_id,
                 page.source, page.page, text, meta)


def fixed_size(page: DocumentPage, size: int, overlap: int, strategy: str = "A") -> list[Chunk]:
    """Character windows of `size` with `overlap`, ignoring structure (baseline)."""
    if not 0 <= overlap < size:
        raise ValueError("require 0 <= overlap < size")
    text, step, chunks = page.text, size - overlap, []
    start = 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append(_make(page, strategy, len(chunks), piece, start))
        if start + size >= len(text):
            break
        start += step
    return chunks


def _split_oversized(para: str, max_size: int) -> list[str]:
    """Split a paragraph longer than max_size at line, then sentence, then hard boundaries."""
    parts, buf = [], ""
    units = para.split("\n")
    if len(units) == 1:
        units = re.split(r"(?<=[.!?])\s+", para)
    for u in units:
        while len(u) > max_size:  # last resort: hard cut
            parts.append(u[:max_size])
            u = u[max_size:]
        cand = f"{buf}\n{u}" if buf else u
        if len(cand) <= max_size:
            buf = cand
        else:
            parts.append(buf)
            buf = u
    if buf:
        parts.append(buf)
    return parts


def by_paragraph(page: DocumentPage, max_size: int, strategy: str = "B",
                 min_size: int = 200) -> list[Chunk]:
    """Greedily group whole paragraphs up to max_size; a heading always starts a new chunk.

    A trailing fragment shorter than min_size (and not a heading) is appended to the
    previous chunk, which may then exceed max_size by at most min_size characters.

    A paragraph ending with ':' (text that introduces a code example) is kept with the
    following paragraph when possible, so explanations are not separated from examples.
    """
    blocks: list[str] = []
    for p in split_paragraphs(page.text):
        blocks.extend([p] if len(p) <= max_size else _split_oversized(p, max_size))

    groups: list[list[str]] = []
    cur: list[str] = []
    for b in blocks:
        joined = "\n\n".join(cur + [b])
        starts_section = heading_of(b) is not None
        # a heading that is the whole current group is kept with what follows
        cur_is_heading_only = len(cur) == 1 and heading_of(cur[0]) is not None \
            and cur[0].count("\n") == 0
        if cur and (len(joined) > max_size or (starts_section and not cur_is_heading_only)):
            groups.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if cur:
        groups.append(cur)

    # merge fragments shorter than min_size into the previous group of the same section
    merged: list[list[str]] = []
    for g in groups:
        size = len("\n\n".join(g))
        if merged and size < min_size and heading_of(g[0]) is None \
                and len("\n\n".join(merged[-1] + g)) <= max_size + min_size:
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    groups = merged

    chunks: list[Chunk] = []
    cursor = 0
    for g in groups:
        text = "\n\n".join(g)
        start = page.text.find(g[0], cursor)
        start = cursor if start < 0 else start
        chunks.append(_make(page, strategy, len(chunks), text, start))
        cursor = start + len(g[0])
    return chunks
