"""Produce `final_relevance_judgments.jsonl` from completed, adjudicated annotation streams.

Implements `RELEVANCE_ANNOTATION_HANDBOOK.md` §9.2's "final aggregated
file" schema. **Refuses to run unless both annotator streams pass
FINAL-ANNOTATION QC and every disagreement with |grade_A - grade_B| >=
2 has a recorded adjudication.** This is intentional -- see
`AGGREGATION RULES` below for the exact per-judgment resolution logic
this script applies, all of which are read from real, present data;
nothing is inferred, defaulted from confidence, or fabricated.

========================================================================
AGGREGATION RULES (read before running -- one rule is an extrapolation
from the handbook, disclosed explicitly, not an unambiguous protocol
requirement)
========================================================================

For each `(query_id, file_path)` in the 439-judgment candidate set:

- **|grade_A - grade_B| == 0** (exact agreement): use that grade
  directly. `adjudicated = false`.
- **|grade_A - grade_B| == 1**: `RELEVANCE_ANNOTATION_HANDBOOK.md` §6
  states this "is common and not automatically escalated" to
  adjudication, but the handbook (as provided to this workspace) does
  not spell out a resolution rule for this case, and this task's own
  Phase 10 instructions likewise only mandate adjudication for
  differences `>= 2`. **This script's default is to take the lower of
  the two grades** -- an extrapolation of §4's stated project-wide
  principle ("a deliberate, documented bias toward precision... over
  -grading distorts Recall@k/Context Precision more harmfully than a
  single file being graded one level conservatively... applied
  consistently, not case-by-case"), which that section states in the
  context of one annotator's own indecision but whose stated rationale
  (protecting Recall@k/Context Precision from inflated relevance sets)
  applies equally to a two-annotator diff of 1. **This is this
  script's interpretation, not an explicit handbook rule** -- every
  diff-1 resolution is listed separately in the run report so the
  project can review and, if a different rule is preferred, override
  before treating any merged output as final.
- **|grade_A - grade_B| >= 2**: requires a matching record in the
  adjudication file (`adjudicated_disagreements.jsonl`, produced by
  hand or via a review of `agreement_analysis.py`'s
  `adjudication_queue.jsonl` output) with a non-empty `final_grade` in
  `{0,1,2,3}` and a non-null `adjudicator_id`. The adjudicator's grade
  is used verbatim -- **never averaged or split** between A and B, per
  the handbook. Missing adjudication for any such pair is a hard error.

Per handbook §8, the final file never writes an explicit grade of `0`
-- a file's absence from `relevance_grades` **is** its grade-0 status.
Grades `1`/`2`/`3` are written as floats (`RelevanceJudgment.relevance_grades`
is typed `dict[str, float]`), matching the frozen schema exactly.

Usage:
    python merge_final_judgments.py \\
        --annotator-a sessions/annotator_A/annotation_queue.jsonl \\
        --annotator-b sessions/annotator_B/annotation_queue.jsonl \\
        --adjudications adjudicated_disagreements.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qc_validation import validate as qc_validate


class MergeBlockedError(Exception):
    """Raised when the merge cannot proceed honestly -- see module docstring's aggregation rules."""


def _load_queue(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                records[(rec["query_id"], rec["file_path"])] = rec
    return records


def _load_adjudications(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    records: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                records[(rec["query_id"], rec["file_path"])] = rec
    return records


def build_final_judgments(
    a: dict[tuple[str, str], dict[str, Any]],
    b: dict[tuple[str, str], dict[str, Any]],
    adjudications: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply the module docstring's aggregation rules to every judgment.

    Returns:
        `(final_records, diff1_resolutions)` -- `final_records` is the
        per-query list ready to write as
        `final_relevance_judgments.jsonl`; `diff1_resolutions` logs
        every diff-1 case this script resolved via its documented
        extrapolated rule, for the run report and for project review.

    Raises:
        MergeBlockedError: If the two streams' candidate sets differ,
            or if any `|grade_A - grade_B| >= 2` pair lacks a matching
            adjudication record with a valid `final_grade`.
    """
    keys_a, keys_b = set(a.keys()), set(b.keys())
    if keys_a != keys_b:
        raise MergeBlockedError(
            f"Streams cover different candidate sets ({len(keys_a - keys_b)} only in A, "
            f"{len(keys_b - keys_a)} only in B). Cannot merge."
        )

    missing_adjudication: list[tuple[str, str]] = []
    per_query_files: dict[tuple[str, str, str, str], dict[str, float]] = {}
    # keyed by (query_id, repository, commit_sha, query_text) -> {file_path: grade}
    per_query_meta: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    diff1_resolutions: list[dict[str, Any]] = []

    for key in sorted(keys_a):
        qid, file_path = key
        rec_a, rec_b = a[key], b[key]
        grade_a, grade_b = int(rec_a["grade"]), int(rec_b["grade"])
        diff = abs(grade_a - grade_b)
        meta_key = (qid, rec_a["repository"], rec_a["commit_sha"], rec_a["query_text"])

        if diff == 0:
            final_grade = grade_a
            adjudicated = False
            adjudicator_id = None
        elif diff == 1:
            final_grade = min(grade_a, grade_b)
            adjudicated = False
            adjudicator_id = None
            diff1_resolutions.append({
                "query_id": qid, "file_path": file_path, "grade_a": grade_a, "grade_b": grade_b,
                "resolved_grade": final_grade, "rule": "lower-of-two (extrapolated from handbook SS4 -- see script docstring)",
            })
        else:
            adj = adjudications.get(key)
            if adj is None or adj.get("final_grade") in (None, "TO_BE_ASSIGNED", ""):
                missing_adjudication.append(key)
                continue
            final_grade = int(adj["final_grade"])
            adjudicated = True
            adjudicator_id = adj.get("adjudicator_id")

        per_query_meta.setdefault(meta_key, {"contributing_annotator_ids": set(), "adjudicated": False, "adjudicator_ids": set(), "notes": []})
        per_query_meta[meta_key]["contributing_annotator_ids"].add(rec_a.get("annotator_id"))
        per_query_meta[meta_key]["contributing_annotator_ids"].add(rec_b.get("annotator_id"))
        if adjudicated:
            per_query_meta[meta_key]["adjudicated"] = True
            per_query_meta[meta_key]["adjudicator_ids"].add(adjudicator_id)

        if final_grade > 0:  # grade 0 is recorded by omission, per handbook SS8
            per_query_files.setdefault(meta_key, {})[file_path] = float(final_grade)
        else:
            per_query_files.setdefault(meta_key, {})  # ensure the query key exists even if empty so far

    if missing_adjudication:
        raise MergeBlockedError(
            f"{len(missing_adjudication)} judgment(s) have |grade_A - grade_B| >= 2 with no matching "
            f"adjudication record (or an incomplete one). Cannot merge until every one is adjudicated. "
            f"Examples: {missing_adjudication[:5]}"
        )

    final_records = []
    for meta_key, relevance_grades in per_query_files.items():
        qid, repo, commit_sha, query_text = meta_key
        meta = per_query_meta[meta_key]
        n_files_this_query = sum(1 for k in a if k[0] == qid)
        n_exact_this_query = sum(1 for k in a if k[0] == qid and int(a[k]["grade"]) == int(b[k]["grade"]))
        agreement = n_exact_this_query / n_files_this_query if n_files_this_query else None
        final_records.append({
            "query_id": qid,
            "repository_id": repo,
            "commit_sha": commit_sha,
            "query_text": query_text,
            "relevance_grades": relevance_grades,
            "contributing_annotator_ids": sorted(x for x in meta["contributing_annotator_ids"] if x),
            "inter_annotator_agreement": agreement,
            "adjudicated": meta["adjudicated"],
            "adjudicator_id": sorted(x for x in meta["adjudicator_ids"] if x)[0] if meta["adjudicator_ids"] else None,
            "notes": "",
        })

    return final_records, diff1_resolutions


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotator-a", type=Path, default=here / "sessions" / "annotator_A" / "annotation_queue.jsonl")
    parser.add_argument("--annotator-b", type=Path, default=here / "sessions" / "annotator_B" / "annotation_queue.jsonl")
    parser.add_argument("--adjudications", type=Path, default=here / "adjudication_queue.jsonl",
                         help="The file agreement_analysis.py produces as a template and a human adjudicator fills in.")
    parser.add_argument("--output", type=Path, default=here / "final_relevance_judgments.jsonl")
    args = parser.parse_args(argv)

    for label, path in (("annotator_A", args.annotator_a), ("annotator_B", args.annotator_b)):
        if not path.is_file():
            print(f"REFUSING TO MERGE: {label}'s file does not exist: {path}")
            return 1
        qc = qc_validate(path, mode="final")
        if not qc.is_valid_final:
            print(f"REFUSING TO MERGE: {label}'s stream fails FINAL-ANNOTATION QC "
                  f"({qc.to_be_assigned_count} still TO_BE_ASSIGNED). See qc_validation.py.")
            return 1

    a = _load_queue(args.annotator_a)
    b = _load_queue(args.annotator_b)
    adjudications = _load_adjudications(args.adjudications)

    try:
        final_records, diff1_resolutions = build_final_judgments(a, b, adjudications)
    except MergeBlockedError as exc:
        print(f"REFUSING TO MERGE: {exc}")
        return 1

    with args.output.open("w", encoding="utf-8") as f:
        for rec in final_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report_path = args.output.with_suffix(".merge_report.md")
    report_lines = [
        "# Final Merge Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Final judgment records (queries): {len(final_records)}",
        f"Diff-1 cases resolved via the documented lower-of-two rule: {len(diff1_resolutions)}",
        "",
        "## Diff-1 resolutions (review these -- see script docstring for why this rule is an extrapolation)",
        "",
    ]
    for d in diff1_resolutions[:100]:
        report_lines.append(f"- {d['query_id']} / `{d['file_path']}`: A={d['grade_a']}, B={d['grade_b']} -> resolved {d['resolved_grade']}")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Wrote {len(final_records)} final judgment records to {args.output}")
    print(f"Wrote merge report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
