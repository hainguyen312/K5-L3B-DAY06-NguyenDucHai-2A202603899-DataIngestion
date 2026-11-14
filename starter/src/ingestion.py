"""Read and normalize the Python-docs plain-text corpus into traceable source units.

The corpus is plain text with no physical pages (Sphinx "text" builder output),
so, following GUIDE.md section 1, each document is split in order into source
units of at least MIN_UNIT_CHARS normalized characters, cut only at paragraph
boundaries. A unit plays the role of a "page": its 1-based index is stored as
`page`, and its stable ID is `<document_id>#p<NN>`.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from .models import DocumentPage

MIN_UNIT_CHARS = 1500

# Sphinx text builder underlines headings with one repeated punctuation char.
_UNDERLINE = re.compile(r"^([=\-*~^\"#+])\1{2,}\s*$")


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while keeping structure.

    - NFKC Unicode normalization, CRLF -> LF, tabs -> 4 spaces
    - remove zero-width / control characters (except newline)
    - RST-style "Title\\n=====" headings become "# Title" lines
    - strip trailing spaces, collapse runs of 3+ blank lines to one blank line
    Indentation is preserved because code examples depend on it.
    """
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", "    ")
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch)[0] != "C")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.strip() and not line.startswith(" ") and _UNDERLINE.match(nxt) \
                and abs(len(nxt.strip()) - len(line.strip())) <= 2:
            out.append("# " + line.strip())
            i += 2
            continue
        out.append(line)
        i += 1
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def split_paragraphs(text: str) -> list[str]:
    return [p for p in text.split("\n\n") if p.strip()]


def heading_of(paragraph: str) -> str | None:
    first = paragraph.lstrip("\n").split("\n", 1)[0]
    return first[2:].strip() if first.startswith("# ") else None


def split_units(text: str, min_chars: int = MIN_UNIT_CHARS) -> list[tuple[str, str]]:
    """Split normalized text into ordered units >= min_chars at paragraph boundaries.

    Returns (unit_text, section_at_unit_start). A trailing remainder shorter than
    min_chars is merged into the previous unit, so no content is dropped or duplicated.
    """
    units: list[tuple[list[str], str]] = []
    current: list[str] = []
    section = ""
    start_section = ""
    for para in split_paragraphs(text):
        if not current:
            start_section = section
        current.append(para)
        h = heading_of(para)
        if h:
            section = h
            if len(current) == 1:
                start_section = h
        # never end a unit on a bare heading: its content would land in the next unit
        if len("\n\n".join(current)) >= min_chars and not (h and "\n" not in para.strip()):
            units.append((current, start_section))
            current = []
    if current:
        if units and len("\n\n".join(current)) < min_chars:
            units[-1] = (units[-1][0] + current, units[-1][1])
        else:
            units.append((current, start_section))
    return [("\n\n".join(paras), sec) for paras, sec in units]


def load_text_document(path: Path, document_id: str, source: str,
                       metadata: dict) -> tuple[list[DocumentPage], dict]:
    """Read one text file, normalize it and return its units plus a manifest entry."""
    raw_bytes = path.read_bytes()
    errors: list[str] = []
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:  # recorded, never silently ignored
        errors.append(f"utf-8 decode error: {exc}; decoded with replacement")
        raw = raw_bytes.decode("utf-8", errors="replace")
    text = normalize_text(raw)
    doc_title = next((heading_of(p) for p in split_paragraphs(text) if heading_of(p)), path.stem)
    pages: list[DocumentPage] = []
    unit_entries = []
    for idx, (unit_text, section) in enumerate(split_units(text), start=1):
        page_id = f"{document_id}#p{idx:02d}"
        if not unit_text.strip():
            errors.append(f"{page_id}: empty unit")
            continue
        meta = dict(metadata, page_id=page_id, section=section or doc_title, title=doc_title)
        pages.append(DocumentPage(document_id, source, idx, unit_text, meta))
        first_line = unit_text.strip().split("\n", 1)[0][:80]
        unit_entries.append({
            "page_id": page_id, "page": idx, "chars": len(unit_text),
            "section_at_start": meta["section"], "starts_with": first_line,
            "sha256": hashlib.sha256(unit_text.encode()).hexdigest()[:16],
        })
    entry = {
        "source_id": document_id,
        "title": doc_title,
        "source_path_or_url": source,
        "local_path": str(path.as_posix()),
        "raw_chars": len(raw),
        "normalized_chars": len(text),
        "unit_count": len(pages),
        "units": unit_entries,
        "errors": errors,
        **metadata,
    }
    return pages, entry
