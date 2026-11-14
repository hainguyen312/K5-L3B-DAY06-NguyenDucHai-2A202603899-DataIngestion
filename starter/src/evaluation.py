"""Evidence-based retrieval scoring (Hit@1, Evidence Hit@3) and per-query traces.

A retrieved chunk is a *hit* only if it comes from a gold (source, page) AND contains
the whole gold evidence quote after match-normalization. Human labels (coherence,
grounding) are NOT inferred here; they live in results/manual_*.csv.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def match_norm(text: str) -> str:
    """Normalization used only for evidence matching (not for stored text)."""
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"(?m)^# ", "", t)            # heading markers added by normalize_text
    t = re.sub(r"-\n\s*", "-", t)            # re-join words hyphenated across lines
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def gold_items(question: dict[str, Any]) -> list[dict[str, Any]]:
    items = [{"source_id": question["gold_source_id"], "page": question["gold_page"],
              "evidence_quote": question["evidence_quote"]}]
    items += question.get("alternatives", [])
    return items


def judge_hit(question: dict[str, Any], hit: dict[str, Any]) -> dict[str, bool]:
    meta, body = hit["metadata"], match_norm(hit["text"])
    loc = ev = False
    for g in gold_items(question):
        same_loc = meta.get("document_id") == g["source_id"] and meta.get("page") == g["page"]
        loc = loc or same_loc
        ev = ev or (same_loc and match_norm(g["evidence_quote"]) in body)
    return {"gold_location": loc, "evidence_hit": ev}


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]],
                   strategy: str, applied_filter: dict | None) -> dict[str, Any]:
    judged = []
    for h in hits:
        j = judge_hit(question, h)
        judged.append({**h, **j})
    flt = question.get("filter")
    filter_ok = None
    if flt:
        filter_ok = all(all(h["metadata"].get(k) == v for k, v in flt.items()) for h in hits)
    return {
        "strategy": strategy,
        "id": question["id"], "split": question["split"], "type": question.get("type"),
        "question": question["question"], "expected_answer": question["expected_answer"],
        "gold": gold_items(question), "question_filter": flt, "applied_filter": applied_filter,
        "hit@1": bool(judged and judged[0]["evidence_hit"]),
        "hit@3": any(h["evidence_hit"] for h in judged[:3]),
        "page_hit@3": any(h["gold_location"] for h in judged[:3]),
        "top3_respects_filter": filter_ok,
        "hits": judged,
    }


def summarize(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    keys = sorted({(t["strategy"], t["split"]) for t in traces})
    for strategy, split in keys:
        ts = [t for t in traces if t["strategy"] == strategy and t["split"] == split]
        fts = [t for t in ts if t["question_filter"]]
        rows.append({
            "strategy": strategy, "split": split, "N": len(ts),
            "hit1": sum(t["hit@1"] for t in ts), "hit3": sum(t["hit@3"] for t in ts),
            "page_hit3": sum(t["page_hit@3"] for t in ts),
            "filter_questions": len(fts),
            "filter_respected": sum(bool(t["top3_respects_filter"]) for t in fts),
        })
    return rows
