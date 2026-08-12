"""Phase 1 -- Inspect the RTS Dataset v1.0 split files before any feature engineering.

Loads `train.jsonl` / `validation.jsonl` / `test.jsonl`
(`evaluation/rts_builder/pilot/merged_dataset/`), validates their
schema against the contract documented in that directory's own
`dataset_card.md`, detects missing values, inspects category/
difficulty/candidate-count distributions, verifies that every query
has a well-formed "group" (its list of candidates, the LTR group unit)
and reports on label state (`grade`) -- including, critically, whether
any real numeric relevance grade exists yet at all, since RTS Dataset
v1.0 ships with every grade still `"TO_BE_ASSIGNED"`.

This module never invents or infers a value for a missing/placeholder
field; it only reports what is actually present. Run as a script, it
performs a live inspection against the real dataset files and writes
a Markdown report -- it does not train anything and does not require
any of `evaluation.rts_builder`'s heavier subsystems.

Usage:
    python -m evaluation.experiments.ltr.dataset_inspection
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - direct-execution convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evaluation.experiments.ltr.utils import (  # type: ignore[no-redef]
        MERGED_DATASET_DIR, REPORTS_DIR, TO_BE_ASSIGNED, get_logger, read_jsonl,
    )
else:
    from evaluation.experiments.ltr.utils import (
        MERGED_DATASET_DIR, REPORTS_DIR, TO_BE_ASSIGNED, get_logger, read_jsonl,
    )

logger = get_logger(__name__)

EXPECTED_QUERY_FIELDS = frozenset({"query_id", "repository_id", "category", "difficulty", "query_text", "notes"})
EXPECTED_CANDIDATE_FIELDS = frozenset({"file", "grade", "reason"})
EXPECTED_CATEGORIES = frozenset(
    {"bug_fix", "feature_implementation", "refactoring", "testing", "documentation", "api_usage", "code_search"}
)
EXPECTED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})


@dataclass
class SplitInspectionResult:
    """Everything Phase 1 checks for one split file."""

    split_name: str
    path: Path
    n_rows: int = 0
    schema_errors: list[str] = field(default_factory=list)
    missing_value_errors: list[str] = field(default_factory=list)
    repository_counts: Counter[str] = field(default_factory=Counter)
    category_counts: Counter[str] = field(default_factory=Counter)
    difficulty_counts: Counter[str] = field(default_factory=Counter)
    group_sizes: list[int] = field(default_factory=list)
    zero_candidate_query_ids: list[str] = field(default_factory=list)
    duplicate_query_ids: list[str] = field(default_factory=list)
    grade_value_counts: Counter[str] = field(default_factory=Counter)
    query_text_lengths: list[int] = field(default_factory=list)

    @property
    def is_schema_valid(self) -> bool:
        return not self.schema_errors

    @property
    def has_any_numeric_label(self) -> bool:
        """True iff at least one candidate row's `grade` is a real int, not the placeholder."""
        return any(
            key != TO_BE_ASSIGNED and _looks_numeric(key) for key in self.grade_value_counts
        )


def _looks_numeric(value: str) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def inspect_split(split_name: str, path: Path) -> SplitInspectionResult:
    """Load and validate one split file, returning a structured result.

    Never raises on a *data-quality* problem (schema mismatch, missing
    value, duplicate ID, all-placeholder labels) -- those are recorded
    in the returned result for the caller/report to surface. It does
    raise if the file itself cannot be read at all (missing file,
    malformed JSON), since that is an environment/reproducibility
    problem, not a data-quality finding to report descriptively.

    Args:
        split_name: One of "train", "validation", "test" (informational only).
        path: Path to the split's `.jsonl` file.

    Returns:
        The populated `SplitInspectionResult`.
    """
    rows = read_jsonl(path)
    result = SplitInspectionResult(split_name=split_name, path=path, n_rows=len(rows))

    seen_query_ids: set[str] = set()
    for row in rows:
        qid = row.get("query_id", "<missing>")

        # --- schema ---
        missing_fields = EXPECTED_QUERY_FIELDS - row.keys()
        extra_fields = row.keys() - EXPECTED_QUERY_FIELDS - {"candidates"}
        if missing_fields:
            result.schema_errors.append(f"{qid}: missing top-level field(s) {sorted(missing_fields)}")
        if extra_fields:
            result.schema_errors.append(f"{qid}: unexpected top-level field(s) {sorted(extra_fields)}")
        if "candidates" not in row:
            result.schema_errors.append(f"{qid}: missing 'candidates' field")

        # --- duplicate IDs ---
        if qid in seen_query_ids:
            result.duplicate_query_ids.append(qid)
        seen_query_ids.add(qid)

        # --- missing values (empty string / None in a required field) ---
        for f in ("query_id", "repository_id", "category", "difficulty", "query_text"):
            v = row.get(f)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                result.missing_value_errors.append(f"{qid}: empty/null required field {f!r}")

        # --- distributions ---
        result.repository_counts[row.get("repository_id", "<missing>")] += 1
        result.category_counts[row.get("category", "<missing>")] += 1
        result.difficulty_counts[row.get("difficulty", "<missing>")] += 1
        if row.get("category") not in EXPECTED_CATEGORIES and row.get("category") is not None:
            result.schema_errors.append(f"{qid}: unexpected category {row.get('category')!r}")
        if row.get("difficulty") not in EXPECTED_DIFFICULTIES and row.get("difficulty") is not None:
            result.schema_errors.append(f"{qid}: unexpected difficulty {row.get('difficulty')!r}")

        query_text = row.get("query_text")
        if isinstance(query_text, str):
            result.query_text_lengths.append(len(query_text.split()))

        # --- group (candidates) checks -- this is the LTR "group" unit ---
        candidates = row.get("candidates", [])
        if not isinstance(candidates, list):
            result.schema_errors.append(f"{qid}: 'candidates' is not a list")
            candidates = []
        result.group_sizes.append(len(candidates))
        if len(candidates) == 0:
            result.zero_candidate_query_ids.append(qid)

        seen_files_this_query: set[str] = set()
        for c in candidates:
            if not isinstance(c, dict):
                result.schema_errors.append(f"{qid}: a candidate entry is not an object")
                continue
            cand_missing = EXPECTED_CANDIDATE_FIELDS - c.keys()
            if cand_missing:
                result.schema_errors.append(f"{qid}: candidate missing field(s) {sorted(cand_missing)}")
            for f in ("file", "grade"):
                v = c.get(f)
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    result.missing_value_errors.append(f"{qid}: candidate has empty/null {f!r}")
            grade = c.get("grade")
            result.grade_value_counts[str(grade)] += 1
            file_path = c.get("file")
            if file_path is not None:
                if file_path in seen_files_this_query:
                    result.schema_errors.append(f"{qid}: duplicate candidate file {file_path!r} within one query")
                seen_files_this_query.add(file_path)

    return result


def format_report(results: list[SplitInspectionResult]) -> str:
    """Render all splits' inspection results as a single Markdown report.

    Args:
        results: One `SplitInspectionResult` per split, in the order to
            display them.

    Returns:
        A Markdown-formatted report string.
    """
    lines: list[str] = [
        "# Phase 1 -- Dataset Inspection Report",
        "",
        "Generated by `dataset_inspection.py` against the real files in "
        "`evaluation/rts_builder/pilot/merged_dataset/`. Every figure below "
        "was computed directly from those files; nothing here is asserted "
        "without having been counted.",
        "",
    ]

    total_rows = sum(r.n_rows for r in results)
    lines += [f"## Overview", "", f"Total rows across all splits inspected: **{total_rows}**", ""]

    for r in results:
        lines.append(f"## Split: `{r.split_name}` (`{r.path.name}`)")
        lines.append("")
        lines.append(f"- Rows: **{r.n_rows}**")
        lines.append(f"- Schema errors: **{len(r.schema_errors)}**" + (" -- see below" if r.schema_errors else ""))
        lines.append(
            f"- Missing-value errors: **{len(r.missing_value_errors)}**"
            + (" -- see below" if r.missing_value_errors else "")
        )
        lines.append(f"- Duplicate query IDs: **{len(r.duplicate_query_ids)}**" + (f" -- {r.duplicate_query_ids}" if r.duplicate_query_ids else ""))
        lines.append(
            f"- Queries with 0 candidates (empty LTR group): **{len(r.zero_candidate_query_ids)}**"
            + (f" -- {r.zero_candidate_query_ids}" if r.zero_candidate_query_ids else "")
        )
        if r.group_sizes:
            lines.append(
                f"- Group (candidate-list) size: min={min(r.group_sizes)}, "
                f"max={max(r.group_sizes)}, mean={sum(r.group_sizes) / len(r.group_sizes):.2f}"
            )
        if r.query_text_lengths:
            lines.append(
                f"- Query text length (words): min={min(r.query_text_lengths)}, "
                f"max={max(r.query_text_lengths)}, mean={sum(r.query_text_lengths) / len(r.query_text_lengths):.1f}"
            )
        lines.append("")

        lines.append("**Repository distribution:**")
        lines.append("")
        lines.append("| Repository | Rows |")
        lines.append("|---|---|")
        for repo, count in sorted(r.repository_counts.items()):
            lines.append(f"| {repo} | {count} |")
        lines.append("")

        lines.append("**Category distribution:**")
        lines.append("")
        lines.append("| Category | Rows |")
        lines.append("|---|---|")
        for cat, count in sorted(r.category_counts.items()):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

        lines.append("**Difficulty distribution:**")
        lines.append("")
        lines.append("| Difficulty | Rows |")
        lines.append("|---|---|")
        for diff, count in sorted(r.difficulty_counts.items()):
            lines.append(f"| {diff} | {count} |")
        lines.append("")

        lines.append("**Grade (label) value counts, across all candidates in this split:**")
        lines.append("")
        lines.append("| grade value | count |")
        lines.append("|---|---|")
        for val, count in sorted(r.grade_value_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| `{val}` | {count} |")
        lines.append("")
        if r.has_any_numeric_label:
            lines.append("**At least one real numeric relevance grade is present in this split.**")
        else:
            lines.append(
                "**No real numeric relevance grade is present in this split -- every candidate's "
                f"`grade` is the literal placeholder `\"{TO_BE_ASSIGNED}\"`.** This split cannot be "
                "used to train or evaluate a ranking model until human annotation assigns real grades. "
                "See `feature_pipeline.validate_labels_are_numeric`, which raises "
                "`UnlabeledDatasetError` rather than silently coercing this placeholder to a number."
            )
        lines.append("")

        if r.schema_errors:
            lines.append("**Schema errors (first 20 shown):**")
            lines.append("")
            for e in r.schema_errors[:20]:
                lines.append(f"- {e}")
            if len(r.schema_errors) > 20:
                lines.append(f"- ... and {len(r.schema_errors) - 20} more")
            lines.append("")

        if r.missing_value_errors:
            lines.append("**Missing-value errors (first 20 shown):**")
            lines.append("")
            for e in r.missing_value_errors[:20]:
                lines.append(f"- {e}")
            if len(r.missing_value_errors) > 20:
                lines.append(f"- ... and {len(r.missing_value_errors) - 20} more")
            lines.append("")

    # Cross-split checks
    lines.append("## Cross-split checks")
    lines.append("")
    all_qids: dict[str, list[str]] = {}
    for r in results:
        for row in read_jsonl(r.path):
            all_qids.setdefault(row["query_id"], []).append(r.split_name)
    leaked = {qid: splits for qid, splits in all_qids.items() if len(set(splits)) > 1}
    if leaked:
        lines.append(f"**{len(leaked)} query_id(s) appear in more than one split (data leakage):**")
        for qid, splits in leaked.items():
            lines.append(f"- {qid}: {splits}")
    else:
        lines.append(f"No query_id appears in more than one split (checked {len(all_qids)} distinct IDs across all splits).")
    lines.append("")

    return "\n".join(lines)


def run_inspection(merged_dataset_dir: Path = MERGED_DATASET_DIR) -> list[SplitInspectionResult]:
    """Inspect train/validation/test and return one result per split.

    Args:
        merged_dataset_dir: Directory containing `train.jsonl`,
            `validation.jsonl`, `test.jsonl`.

    Returns:
        Results in the fixed order [train, validation, test].
    """
    results = []
    for split_name in ("train", "validation", "test"):
        path = merged_dataset_dir / f"{split_name}.jsonl"
        logger.info("Inspecting %s split: %s", split_name, path)
        results.append(inspect_split(split_name, path))
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Writes `outputs/reports/phase1_dataset_inspection.md`.

    Returns:
        Process exit code: 0 always (this is a diagnostic report, not a
        gate -- findings, including a fully-placeholder label state,
        are reported, not treated as a hard failure at this phase).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--merged-dataset-dir", type=Path, default=MERGED_DATASET_DIR,
        help="Directory containing train/validation/test.jsonl (default: the frozen RTS Dataset v1.0 location).",
    )
    parser.add_argument(
        "--report-path", type=Path, default=REPORTS_DIR / "phase1_dataset_inspection.md",
        help="Where to write the Markdown report.",
    )
    args = parser.parse_args(argv)

    results = run_inspection(args.merged_dataset_dir)
    report = format_report(results)

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(report, encoding="utf-8")
    logger.info("Wrote report to %s", args.report_path)

    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
