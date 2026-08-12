"""Inter-annotator agreement analysis for the final human relevance annotation.

Computes, per `RELEVANCE_ANNOTATION_HANDBOOK.md` §6, quadratic
-weighted Cohen's kappa and related statistics comparing two
independent annotation streams (`annotator_A`, `annotator_B`).

**This script refuses to compute anything -- including a kappa value
-- unless both streams are genuinely, independently complete.** It
does not fabricate a kappa, does not compute agreement between a
stream and a copy of itself, and does not proceed on partial data. See
`main`'s pre-flight checks, all three of which must pass:

1. Both input files pass `qc_validation.validate(..., mode="final")`
   (every judgment has a real grade in `{0,1,2,3}`, no structural
   errors) -- reuses `qc_validation.py` rather than re-implementing
   its checks.
2. The two streams have **different** `annotator_id` values throughout
   (catches the "same annotator duplicated" failure mode named
   explicitly in this task's Phase 9 instructions).
3. The two streams are not **byte-for-byte identical in every grade**
   (a second, independent signal against accidental duplication --
   even with different `annotator_id`s, two streams that agree on
   literally every single grade with 0 exceptions across hundreds of
   judgments is far more consistent with one stream having been copied
   and relabeled than with two humans independently agreeing on
   everything).

Usage:
    python agreement_analysis.py \\
        --annotator-a sessions/annotator_A/annotation_queue.jsonl \\
        --annotator-b sessions/annotator_B/annotation_queue.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from qc_validation import validate as qc_validate


class AgreementAnalysisError(Exception):
    """Raised when agreement cannot be honestly computed -- see module docstring's 3 pre-flight checks."""


def _load_queue(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load a completed annotation queue, keyed by `(query_id, file_path)`."""
    records: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[(rec["query_id"], rec["file_path"])] = rec
    return records


def check_streams_are_independent(a: dict[tuple[str, str], dict], b: dict[tuple[str, str], dict]) -> None:
    """Pre-flight checks 2 and 3 from the module docstring.

    Raises:
        AgreementAnalysisError: If the two streams share an
            `annotator_id`, or if every single grade matches exactly
            (see module docstring for why the latter is treated as a
            duplication signal, not a legitimate perfect-agreement
            result).
    """
    annotator_ids_a = {rec["annotator_id"] for rec in a.values()}
    annotator_ids_b = {rec["annotator_id"] for rec in b.values()}
    overlap = annotator_ids_a & annotator_ids_b
    if overlap:
        raise AgreementAnalysisError(
            f"annotator_id overlap between the two streams: {overlap}. Agreement analysis requires two "
            "genuinely distinct annotators; refusing to compute agreement against a duplicated annotator."
        )

    common_keys = set(a.keys()) & set(b.keys())
    if not common_keys:
        return  # nothing to compare yet; handled as a separate error by the caller
    n_matching_grades = sum(1 for k in common_keys if a[k]["grade"] == b[k]["grade"])
    if n_matching_grades == len(common_keys) and len(common_keys) > 20:
        raise AgreementAnalysisError(
            f"All {len(common_keys)} compared judgments have byte-for-byte identical grades between the "
            "two streams. This is treated as a probable duplicated/copied stream, not genuine independent "
            "double annotation (see module docstring) -- refusing to report a kappa value. If this really "
            "is two independent annotators who happened to agree on everything, this check will need "
            "human override, not a silent pass."
        )


@dataclass
class AgreementResult:
    n_compared: int
    exact_agreement_rate: float
    disagreement_rate: float
    grade_difference_distribution: dict[int, int]
    n_disagreements_ge_2: int
    disagreement_details: list[dict[str, Any]]
    quadratic_weighted_kappa_overall: float
    quadratic_weighted_kappa_by_repository: dict[str, float]
    grade_distribution_a: dict[int, int]
    grade_distribution_b: dict[int, int]
    average_grade_a: float
    average_grade_b: float
    annotation_time_stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_agreement(a: dict[tuple[str, str], dict], b: dict[tuple[str, str], dict]) -> AgreementResult:
    """Compute every agreement statistic in this module's docstring.

    Args:
        a: Annotator A's records, keyed by `(query_id, file_path)`.
        b: Annotator B's records, keyed the same way.

    Returns:
        An `AgreementResult`.

    Raises:
        AgreementAnalysisError: If the two streams' key sets do not
            match (they must have graded the exact same candidate
            set -- a mismatch means one stream is incomplete or the
            two started from different queues, either of which
            invalidates a direct comparison).
    """
    from sklearn.metrics import cohen_kappa_score

    keys_a, keys_b = set(a.keys()), set(b.keys())
    if keys_a != keys_b:
        only_a = keys_a - keys_b
        only_b = keys_b - keys_a
        raise AgreementAnalysisError(
            f"The two streams graded different candidate sets: {len(only_a)} judgments only in A, "
            f"{len(only_b)} only in B. Both streams must grade the identical 439-judgment queue. "
            f"Example mismatches: A-only={list(only_a)[:3]}, B-only={list(only_b)[:3]}"
        )

    keys = sorted(keys_a)
    grades_a = [int(a[k]["grade"]) for k in keys]
    grades_b = [int(b[k]["grade"]) for k in keys]

    diffs = [abs(ga - gb) for ga, gb in zip(grades_a, grades_b)]
    diff_dist = dict(sorted(Counter(diffs).items()))
    n_exact = sum(1 for d in diffs if d == 0)
    n_ge2 = sum(1 for d in diffs if d >= 2)

    disagreement_details = [
        {
            "query_id": k[0], "file_path": k[1],
            "grade_a": grades_a[i], "grade_b": grades_b[i], "difference": diffs[i],
            "rationale_a": a[k].get("rationale", ""), "rationale_b": b[k].get("rationale", ""),
        }
        for i, k in enumerate(keys) if diffs[i] >= 2
    ]

    overall_kappa = float(cohen_kappa_score(grades_a, grades_b, weights="quadratic"))

    by_repo: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for i, k in enumerate(keys):
        repo = a[k]["repository"]
        by_repo[repo].append((grades_a[i], grades_b[i]))
    kappa_by_repo = {}
    for repo, pairs in sorted(by_repo.items()):
        ga = [p[0] for p in pairs]
        gb = [p[1] for p in pairs]
        # quadratic-weighted kappa is undefined (or degenerate) with fewer than 2 distinct grade
        # values present across both raters combined -- report explicitly rather than let sklearn's
        # internal handling silently produce a misleading number for a tiny/degenerate repo subset.
        if len(set(ga) | set(gb)) < 2:
            kappa_by_repo[repo] = None
        else:
            kappa_by_repo[repo] = float(cohen_kappa_score(ga, gb, weights="quadratic"))

    time_stats: dict[str, Any] = {"note": "Populated from session logs if present; see main()'s session-log loading."}

    return AgreementResult(
        n_compared=len(keys),
        exact_agreement_rate=n_exact / len(keys),
        disagreement_rate=1.0 - (n_exact / len(keys)),
        grade_difference_distribution=diff_dist,
        n_disagreements_ge_2=n_ge2,
        disagreement_details=disagreement_details,
        quadratic_weighted_kappa_overall=overall_kappa,
        quadratic_weighted_kappa_by_repository=kappa_by_repo,
        grade_distribution_a=dict(sorted(Counter(grades_a).items())),
        grade_distribution_b=dict(sorted(Counter(grades_b).items())),
        average_grade_a=sum(grades_a) / len(grades_a),
        average_grade_b=sum(grades_b) / len(grades_b),
        annotation_time_stats=time_stats,
    )


def format_report(result: AgreementResult) -> str:
    lines = [
        "# Inter-Annotator Agreement Analysis",
        "",
        f"Judgments compared: **{result.n_compared}**",
        f"Exact agreement rate: **{result.exact_agreement_rate:.4f}**",
        f"Disagreement rate: **{result.disagreement_rate:.4f}**",
        f"Quadratic-weighted Cohen's kappa (overall): **{result.quadratic_weighted_kappa_overall:.4f}**",
        "",
        "## Per-repository quadratic-weighted kappa",
        "",
        "| Repository | Kappa |",
        "|---|---|",
    ]
    for repo, k in result.quadratic_weighted_kappa_by_repository.items():
        lines.append(f"| {repo} | {k:.4f} |" if k is not None else f"| {repo} | undefined (< 2 distinct grades in this subset) |")

    lines += [
        "",
        "## Grade difference distribution",
        "",
        "| |Grade A - Grade B| | Count |",
        "|---|---|",
    ]
    for diff, count in result.grade_difference_distribution.items():
        lines.append(f"| {diff} | {count} |")

    lines += [
        "",
        f"## Disagreements requiring adjudication (|difference| >= 2): {result.n_disagreements_ge_2}",
        "",
        "Per `RELEVANCE_ANNOTATION_HANDBOOK.md` §6, every one of these must be reviewed by an independent "
        "third-party adjudicator -- not averaged, not resolved by this script.",
        "",
        "| Query | File | Grade A | Grade B | Diff |",
        "|---|---|---|---|---|",
    ]
    for d in result.disagreement_details[:50]:
        lines.append(f"| {d['query_id']} | `{d['file_path']}` | {d['grade_a']} | {d['grade_b']} | {d['difference']} |")
    if len(result.disagreement_details) > 50:
        lines.append(f"| ... | {len(result.disagreement_details) - 50} more in the JSON output | | | |")

    lines += [
        "",
        "## Per-annotator statistics",
        "",
        f"- Annotator A grade distribution: {result.grade_distribution_a}, average grade: {result.average_grade_a:.3f}",
        f"- Annotator B grade distribution: {result.grade_distribution_b}, average grade: {result.average_grade_b:.3f}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotator-a", type=Path, default=here / "sessions" / "annotator_A" / "annotation_queue.jsonl")
    parser.add_argument("--annotator-b", type=Path, default=here / "sessions" / "annotator_B" / "annotation_queue.jsonl")
    parser.add_argument("--report-path", type=Path, default=here / "agreement_report.md")
    parser.add_argument("--results-path", type=Path, default=here / "agreement_results.json")
    parser.add_argument("--adjudication-queue-path", type=Path, default=here / "adjudication_queue.jsonl")
    args = parser.parse_args(argv)

    for label, path in (("annotator_A", args.annotator_a), ("annotator_B", args.annotator_b)):
        if not path.is_file():
            print(f"REFUSING TO COMPUTE AGREEMENT: {label}'s annotation file does not exist yet: {path}")
            print("Both annotation streams must be complete before this script can run. See README.md's workflow.")
            return 1
        qc = qc_validate(path, mode="final")
        if not qc.is_valid_final:
            print(f"REFUSING TO COMPUTE AGREEMENT: {label}'s stream fails FINAL-ANNOTATION QC "
                  f"({qc.to_be_assigned_count} still TO_BE_ASSIGNED, {len(qc.invalid_grades)} invalid grades). "
                  f"Run `python qc_validation.py --mode final --input {path}` for the full report.")
            return 1

    a = _load_queue(args.annotator_a)
    b = _load_queue(args.annotator_b)

    try:
        check_streams_are_independent(a, b)
        result = compute_agreement(a, b)
    except AgreementAnalysisError as exc:
        print(f"REFUSING TO COMPUTE AGREEMENT: {exc}")
        return 1

    report = format_report(result)
    print(report)
    args.report_path.write_text(report, encoding="utf-8")
    args.results_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    # Prepare the third-party adjudicator's working file -- one record per
    # disagreement requiring adjudication (|diff| >= 2), grade left blank for
    # the adjudicator to fill in. Never pre-filled, never averaged.
    adjudication_records = [
        {
            "query_id": d["query_id"],
            "file_path": d["file_path"],
            "grade_a": d["grade_a"],
            "grade_b": d["grade_b"],
            "rationale_a": d["rationale_a"],
            "rationale_b": d["rationale_b"],
            "final_grade": "TO_BE_ASSIGNED",
            "adjudicator_id": "",
            "adjudication_rationale": "",
            "timestamp": "",
        }
        for d in result.disagreement_details
    ]
    with args.adjudication_queue_path.open("w", encoding="utf-8") as f:
        for rec in adjudication_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(adjudication_records)} disagreement(s) requiring adjudication to {args.adjudication_queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
