"""Single place for corpus, model and strategy settings (shared by every strategy)."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW_DIR = REPO / "data" / "raw" / "python-docs-3.15"
MANIFEST = REPO / "data" / "manifest.json"
BENCHMARK = REPO / "benchmark" / "questions.json"
RESULTS = REPO / "results"
VECTOR_DIR = REPO / "vectordb" / "chroma"

DOCS_BASE = "https://docs.python.org/3.15/"
ARCHIVE_URL = "https://docs.python.org/3/archives/python-3.15-docs-text.tar.bz2"
ARCHIVE_SHA256 = "5b2d847afedb4b14b715485b84d30fe4993f80562e3a7f7508680afa5fec8a00"
ACCESSED_AT = "2026-11-14"
DOCS_VERSION = "3.15"  # archive landing page reported "Python 3.15.2 documentation"
LICENSE = ("PSF License Version 2 (tài liệu Python); code mẫu dual-license "
           "PSF-2.0 / 0BSD từ 3.8.6 - xem data/raw/python-docs-3.15/LICENSE-python-docs.txt")

# (document_id, relative path, doc_type). doc_type is the metadata filter field:
# it is the top-level section of docs.python.org the page belongs to ("tutorial/" or "howto/").
DOCUMENTS = [
    ("tut-datastructures", "tutorial/datastructures.txt", "tutorial"),
    ("tut-modules", "tutorial/modules.txt", "tutorial"),
    ("tut-inputoutput", "tutorial/inputoutput.txt", "tutorial"),
    ("tut-errors", "tutorial/errors.txt", "tutorial"),
    ("tut-venv", "tutorial/venv.txt", "tutorial"),
    ("tut-stdlib", "tutorial/stdlib.txt", "tutorial"),
    ("tut-stdlib2", "tutorial/stdlib2.txt", "tutorial"),
    ("howto-sorting", "howto/sorting.txt", "howto"),
    ("howto-logging", "howto/logging.txt", "howto"),
]

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"  # local HF snapshot
MAX_SEQ_LENGTH = 256
TOP_K = 3

STRATEGIES = {
    "A": {"chunking": "fixed_size", "size": 500, "overlap": 50, "use_filter": False},
    "B": {"chunking": "by_paragraph", "max_size": 800, "min_size": 200, "use_filter": False},
    "C": {"chunking": "by_paragraph", "max_size": 800, "min_size": 200, "use_filter": True},
}
