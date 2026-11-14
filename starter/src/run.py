"""Day 06 pipeline entry point.

Run from starter/:
    python -m src.run manifest            # read + normalize corpus, write data/manifest.json
    python -m src.run verify-benchmark    # locate every evidence quote in the normalized units
    python -m src.run ingest              # chunk + embed + store strategies A, B, C
    python -m src.run reload-check        # re-ingest: prove no duplicates, obsolete chunks removed
    python -m src.run evaluate --split dev
    python -m src.run evaluate --split test
    python -m src.run samples             # templates for manual coherence/metadata/grounding audit
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone

os.environ.setdefault("HF_HUB_OFFLINE", "1")          # use the pinned local snapshot only
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from . import config as C  # noqa: E402
from .chunking import by_paragraph, fixed_size  # noqa: E402
from .evaluation import evaluate_query, match_norm, summarize  # noqa: E402
from .ingestion import MIN_UNIT_CHARS, load_text_document  # noqa: E402
from .models import Chunk, DocumentPage  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_corpus() -> tuple[list[DocumentPage], list[dict]]:
    pages, entries = [], []
    for doc_id, rel, doc_type in C.DOCUMENTS:
        path = C.RAW_DIR / rel
        if not path.exists():
            sys.exit(f"missing corpus file {path}")
        p, e = load_text_document(path, doc_id, C.DOCS_BASE + rel.replace(".txt", ".html"),
                                  {"doc_type": doc_type, "version": C.DOCS_VERSION})
        e["local_path"] = str(path.relative_to(C.REPO))
        pages += p
        entries.append(e)
    return pages, entries


def cmd_manifest(_args) -> None:
    pages, entries = load_corpus()
    if len(pages) < 30:
        sys.exit(f"only {len(pages)} source units; need >= 30")
    manifest = {
        "corpus": "Tài liệu Python 3.15 (bản plain-text): một số chương Tutorial và HOWTO được chọn",
        "archive_url": C.ARCHIVE_URL, "archive_sha256": C.ARCHIVE_SHA256,
        "accessed_at": C.ACCESSED_AT, "docs_version": C.DOCS_VERSION,
        "license_or_permission": C.LICENSE,
        "unit_rule": (f"Không có trang vật lý (HTML/text). Mỗi tài liệu được chuẩn hóa rồi chia theo thứ tự "
                      f"tại ranh giới đoạn thành các đơn vị >= {MIN_UNIT_CHARS} ký tự đã chuẩn hóa; "
                      f"phần dư ngắn hơn được gộp vào đơn vị trước; không đơn vị nào kết thúc bằng heading trơ. "
                      f"`page` = số thứ tự đơn vị (bắt đầu từ 1), page_id = <source_id>#pNN. Không nhân bản."),
        "excluded": "Không chọn các trang Tutorial index/appetite/whatnow...; không cắt bỏ gì bên trong các file đã chọn.",
        "total_units": len(pages),
        "total_normalized_chars": sum(len(p.text) for p in pages),
        "documents": entries,
    }
    C.MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    C.RESULTS.mkdir(exist_ok=True)
    errs = [f"{e['source_id']}: {x}" for e in entries for x in e["errors"]]
    short = [u["page_id"] for e in entries for u in e["units"] if u["chars"] < MIN_UNIT_CHARS]
    (C.RESULTS / "ingest_errors.log").write_text(
        f"# tạo lúc {now()}\n# lỗi decode/đơn vị rỗng: {len(errs)}\n" + "\n".join(errs) +
        f"\n# đơn vị dưới {MIN_UNIT_CHARS} ký tự: {len(short)} {short}\n", encoding="utf-8")
    print(f"manifest: {len(entries)} documents, {len(pages)} units, errors={len(errs)}")


def cmd_verify(_args) -> None:
    pages, _ = load_corpus()
    qs = json.loads(C.BENCHMARK.read_text(encoding="utf-8"))
    rows, problems = [], []
    for q in qs:
        quote = match_norm(q["evidence_quote"])
        found = [p for p in pages if quote in match_norm(p.text)]
        same_doc = [p for p in found if p.document_id == q["gold_source_id"]]
        if not same_doc:
            problems.append(f"{q['id']}: evidence not found in {q['gold_source_id']}")
            continue
        if q["gold_page"] is None:
            q["gold_page"] = same_doc[0].page
        elif q["gold_page"] not in [p.page for p in same_doc]:
            problems.append(f"{q['id']}: evidence not on declared page {q['gold_page']}")
        q["alternatives"] = [{"source_id": p.document_id, "page": p.page,
                              "evidence_quote": q["evidence_quote"]}
                             for p in found if (p.document_id, p.page) != (q["gold_source_id"], q["gold_page"])]
        filt_ok = all(any(p.metadata.get(k) == v for p in same_doc) for k, v in (q["filter"] or {}).items())
        if not filt_ok:
            problems.append(f"{q['id']}: gold page does not satisfy its filter")
        rows.append({"id": q["id"], "split": q["split"], "gold": f"{q['gold_source_id']}#p{q['gold_page']:02d}",
                     "found_in_units": ";".join(p.metadata["page_id"] for p in found),
                     "quote_chars": len(q["evidence_quote"]), "filter": json.dumps(q["filter"]),
                     "filter_consistent": filt_ok})
    if problems:
        sys.exit("benchmark verification failed:\n" + "\n".join(problems))
    C.BENCHMARK.write_text(json.dumps(qs, indent=1, ensure_ascii=False), encoding="utf-8")
    write_csv(C.RESULTS / "benchmark_verification.csv", rows)
    n = {s: sum(q["split"] == s for q in qs) for s in ("dev", "test")}
    nf = {s: sum(bool(q["filter"]) and q["split"] == s for q in qs) for s in ("dev", "test")}
    print(f"verified {len(qs)} questions; dev={n['dev']} test={n['test']}; filter dev={nf['dev']} test={nf['test']}")


def build_chunks(strategy: str, pages: list[DocumentPage]) -> list[Chunk]:
    cfg = C.STRATEGIES[strategy]
    if cfg["chunking"] == "fixed_size":
        return [c for p in pages for c in fixed_size(p, cfg["size"], cfg["overlap"], strategy)]
    return [c for p in pages for c in by_paragraph(p, cfg["max_size"], strategy, cfg["min_size"])]


def get_embedder():
    from .embeddings import SentenceTransformerEmbedder
    return SentenceTransformerEmbedder(C.EMBEDDING_MODEL, max_seq_length=C.MAX_SEQ_LENGTH)


def get_store(emb):
    from .store import ChromaStore
    C.VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    return ChromaStore(C.VECTOR_DIR, emb.dimensions, emb.model_name)


def write_csv(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def cmd_ingest(args) -> None:
    pages, _ = load_corpus()
    t0 = time.perf_counter()
    emb = get_embedder()
    load_s = time.perf_counter() - t0
    store = get_store(emb)
    stats = {"run_at": now(), "model": C.EMBEDDING_MODEL, "model_revision": C.EMBEDDING_REVISION,
             "dimensions": emb.dimensions, "max_seq_length": emb.max_seq_length,
             "model_load_seconds": round(load_s, 2), "device": "cpu",
             "platform": platform.platform(), "python": platform.python_version(),
             "cost_usd": 0.0, "strategies": {}}
    for s in args.strategies:
        t = time.perf_counter()
        chunks = build_chunks(s, pages)
        t_chunk = time.perf_counter() - t
        t = time.perf_counter()
        vecs = emb.embed_documents([c.text for c in chunks])
        t_embed = time.perf_counter() - t
        t = time.perf_counter()
        report = store.upsert(s, chunks, vecs)
        t_store = time.perf_counter() - t
        lens = [len(c.text) for c in chunks]
        toks = emb.token_lengths([c.text for c in chunks])
        q = statistics.quantiles(lens, n=10)
        stats["strategies"][s] = {
            "config": C.STRATEGIES[s], "chunks": len(chunks), "total_chars": sum(lens),
            "chars_min": min(lens), "chars_p10": round(q[0]), "chars_median": statistics.median(lens),
            "chars_p90": round(q[-1]), "chars_max": max(lens),
            "tokens_total": sum(toks), "tokens_median": statistics.median(toks), "tokens_max": max(toks),
            "chunks_truncated_at_max_seq": sum(x > emb.max_seq_length for x in toks),
            "seconds_chunk": round(t_chunk, 3), "seconds_embed": round(t_embed, 2),
            "seconds_store": round(t_store, 2),
            "seconds_total": round(t_chunk + t_embed + t_store, 2), "upsert": report,
        }
        with open(C.RESULTS / f"chunks_{s}.jsonl", "w", encoding="utf-8") as f:
            for c, n in zip(chunks, toks):
                f.write(json.dumps({"chunk_id": c.chunk_id, "document_id": c.document_id, "source": c.source,
                                    "page": c.page, "tokens": n, "metadata": c.metadata, "text": c.text},
                                   ensure_ascii=False) + "\n")
        print(f"{s}: {len(chunks)} chunks, embed {t_embed:.1f}s, store {report}")
    out = C.RESULTS / "ingest_stats.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prev_runs = prev.get("history", [])
    prev_runs.append({k: v for k, v in stats.items() if k != "history"})
    stats["history"] = prev_runs[-5:]
    out.write_text(json.dumps(stats, indent=1), encoding="utf-8")


def cmd_reload_check(_args) -> None:
    """Re-ingest strategy A and B twice and simulate a changed document."""
    pages, _ = load_corpus()
    emb = get_embedder()
    store = get_store(emb)
    lines = [f"# kiểm tra nạp lại {now()}"]
    for s in ("A", "B"):
        chunks = build_chunks(s, pages)
        vecs = emb.embed_documents([c.text for c in chunks])
        before = store.count(s)
        r1 = store.upsert(s, chunks, vecs)
        r2 = store.upsert(s, chunks, vecs)
        lines.append(f"{s}: số chunk trước={before}; nạp lại lần 1 {r1}; nạp lại lần 2 {r2}; "
                     f"kỳ vọng {len(chunks)} -> {'OK' if r2['after_total'] == len(chunks) else 'FAIL'}")
        # simulate: tut-venv loses its last unit (document changed) -> its chunks must disappear
        changed = [c for c in chunks if not (c.document_id == "tut-venv" and c.page == 4)]
        cvecs = [v for c, v in zip(chunks, vecs) if not (c.document_id == "tut-venv" and c.page == 4)]
        doc_chunks = [c for c in changed if c.document_id == "tut-venv"]
        doc_vecs = [v for c, v in zip(changed, cvecs) if c.document_id == "tut-venv"]
        r3 = store.upsert(s, doc_chunks, doc_vecs)
        lines.append(f"{s}: giả lập tài liệu đổi (bỏ tut-venv#p04) {r3}; "
                     f"kỳ vọng tổng {len(changed)} -> {'OK' if r3['after_total'] == len(changed) else 'FAIL'}")
        r4 = store.upsert(s, chunks, vecs)
        lines.append(f"{s}: khôi phục bản gốc {r4}")
    text = "\n".join(lines) + "\n"
    (C.RESULTS / "reload_check.log").write_text(text, encoding="utf-8")
    print(text)


def cmd_evaluate(args) -> None:
    qs = [q for q in json.loads(C.BENCHMARK.read_text(encoding="utf-8")) if args.split in ("all", q["split"])]
    if any(q["gold_page"] is None for q in qs):
        sys.exit("run verify-benchmark first")
    emb = get_embedder()
    store = get_store(emb)
    traces, timing = [], {}
    for s in args.strategies:
        use_filter = C.STRATEGIES[s]["use_filter"]
        t = time.perf_counter()
        for q in qs:
            applied = q["filter"] if (use_filter and q["filter"]) else None
            hits = store.search(s, emb.embed_query(q["question"]), C.TOP_K, applied)
            traces.append(evaluate_query(q, hits, s, applied))
        timing[s] = round((time.perf_counter() - t) / len(qs) * 1000, 1)
    with open(C.RESULTS / f"traces_{args.split}.jsonl", "w", encoding="utf-8") as f:
        for tr in traces:
            f.write(json.dumps(tr, ensure_ascii=False) + "\n")
    rows = summarize(traces)
    for r in rows:
        r["ms_per_query"] = timing[r["strategy"]]
        r["run_at"] = now()
    write_csv(C.RESULTS / f"metrics_{args.split}.csv", rows)
    for r in rows:
        print(f"{r['strategy']} {r['split']}: Hit@1 {r['hit1']}/{r['N']}  Hit@3 {r['hit3']}/{r['N']}  "
              f"page-only@3 {r['page_hit3']}/{r['N']}  filter {r['filter_respected']}/{r['filter_questions']}")
    for tr in traces:
        mark = "".join("E" if h["evidence_hit"] else ("p" if h["gold_location"] else ".") for h in tr["hits"])
        print(f"  {tr['strategy']} {tr['id']} [{mark}] " +
              " | ".join(h["metadata"]["page_id"] for h in tr["hits"]))


# 10 coherence positions, fixed before looking at any score: the midpoint of unit p02 of
# each of the 9 documents, plus the midpoint of howto-logging#p10 (largest document).
COHERENCE_POSITIONS = [f"{d}#p02" for d, _, _ in C.DOCUMENTS] + ["howto-logging#p10"]


def cmd_samples(_args) -> None:
    pages, _ = load_corpus()
    by_id = {p.metadata["page_id"]: p for p in pages}
    rows = []
    for s in ("A", "B", "C"):
        chunks = [json.loads(x) for x in open(C.RESULTS / f"chunks_{s}.jsonl", encoding="utf-8")]
        for pos_id in COHERENCE_POSITIONS:
            mid = len(by_id[pos_id].text) // 2
            cover = [c for c in chunks if c["metadata"]["page_id"] == pos_id
                     and c["metadata"]["char_start"] <= mid < c["metadata"]["char_end"]]
            c = cover[0]
            rows.append({"strategy": s, "position": f"{pos_id}@{mid}", "chunk_id": c["chunk_id"],
                         "chars": len(c["text"]), "text": c["text"], "score_0_2": "", "reason": ""})
    write_csv(C.RESULTS / "coherence_sample.csv", rows)
    print(f"wrote {len(rows)} coherence rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("manifest")
    sub.add_parser("verify-benchmark")
    p = sub.add_parser("ingest")
    p.add_argument("--strategies", nargs="+", default=list(C.STRATEGIES))
    sub.add_parser("reload-check")
    p = sub.add_parser("evaluate")
    p.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    p.add_argument("--strategies", nargs="+", default=list(C.STRATEGIES))
    sub.add_parser("samples")
    args = ap.parse_args()
    C.RESULTS.mkdir(exist_ok=True)
    {"manifest": cmd_manifest, "verify-benchmark": cmd_verify, "ingest": cmd_ingest,
     "reload-check": cmd_reload_check, "evaluate": cmd_evaluate, "samples": cmd_samples}[args.cmd](args)


if __name__ == "__main__":
    main()
