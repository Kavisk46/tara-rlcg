"""QC validation for the final human relevance annotation workspace.

Structural validation only (schema conformance, referential integrity,
file existence) — this is necessary but not sufficient for quality per
`RELEVANCE_ANNOTATION_HANDBOOK.md` §7: it cannot detect a
well-formed-but-wrong grade. That requires the handbook's own
spot-check auditing and agreement analysis (`agreement_analysis.py`),
not this script.

Two modes, matching the handbook's distinction between the raw
annotation-in-progress state and the finished, submittable state:

- `pre` (default): validates `annotation_queue.jsonl` as prepared by
  this workspace, before any human grading. `"TO_BE_ASSIGNED"` is
  **expected** on every record in this mode — flagging it as an error
  would be wrong.
- `final`: validates a completed (or claimed-to-be-completed)
  annotation stream or merged file. `"TO_BE_ASSIGNED"` **must** be
  zero in this mode; every other completeness/correctness check also
  applies.

Usage:
    python qc_validation.py --mode pre --input annotation_queue.jsonl
    python qc_validation.py --mode final --input sessions/annotator_A/annotation_queue.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_GRADES = {0, 1, 2, 3}
PLACEHOLDER_GRADE = "TO_BE_ASSIGNED"

REPO_LOCAL_PATHS: dict[str, str] = {
    "fastapi": r"C:\Projects\tara-rlcg\fastapi",
    "flask": r"C:\Projects\tara-rlcg\flask",
    "requests": r"C:\Projects\tara-rlcg\requests",
    "click": r"C:\Projects\tara-rlcg\click",
    "celery": r"C:\Projects\tara-rlcg\celery",
    "sqlalchemy": r"C:\Projects\tara-rlcg\sqlalchemy",
    "pandas": r"C:\Projects\tara-rlcg\pandas",
    "scikit-learn": r"C:\Projects\tara-rlcg\scikit-learn",
}

COMMIT_SHAS: dict[str, str] = {
    "fastapi": "a375f6b948b99fa4260129856bbf11d037f363ef",
    "flask": "6a2f545bfd8ed31e19066a299296917e034aca58",
    "requests": "1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e",
    "click": "00e592cea702e0b2caa0dee42489fdb1c22cd845",
    "celery": "f109abf852525b69a1b6eee0457c6cd5561e0529",
    "sqlalchemy": "dc6a8b18a5bcda653e34aab2a70c7469dcd4300d",
    "pandas": "d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8",
    "scikit-learn": "9b9be3abddd88675c5dc2e3623e652cb7545a26c",
}

REQUIRED_FIELDS = (
    "query_id", "repository", "commit_sha", "query_text", "file_path",
    "grade", "rationale", "annotator_id", "timestamp",
)


@dataclass
class QcResult:
    mode: str
    input_path: Path
    n_records: int = 0
    malformed_lines: list[tuple[int, str]] = field(default_factory=list)
    missing_query_ids: list[int] = field(default_factory=list)  # line numbers
    invalid_repositories: list[tuple[int, str]] = field(default_factory=list)
    invalid_commits: list[tuple[int, str, str]] = field(default_factory=list)
    invalid_file_paths: list[tuple[str, str, str]] = field(default_factory=list)  # (query_id, repo, file)
    duplicate_pairs: dict[tuple[str, str], int] = field(default_factory=dict)
    to_be_assigned_count: int = 0
    invalid_grades: list[tuple[str, str, Any]] = field(default_factory=list)
    missing_rationale: list[tuple[str, str]] = field(default_factory=list)  # grade >= 1 with empty rationale
    missing_annotator_id: list[tuple[str, str]] = field(default_factory=list)
    missing_timestamp: list[tuple[str, str]] = field(default_factory=list)
    grade_distribution: Counter[int] = field(default_factory=Counter)

    @property
    def is_valid_pre(self) -> bool:
        """PRE-ANNOTATION passes iff structure is sound (placeholder grades are expected, not an error)."""
        return not (
            self.malformed_lines or self.missing_query_ids or self.invalid_repositories
            or self.invalid_commits or self.invalid_file_paths or self.duplicate_pairs
        )

    @property
    def is_valid_final(self) -> bool:
        """FINAL-ANNOTATION passes iff structurally sound AND fully, validly graded."""
        return (
            self.is_valid_pre
            and self.to_be_assigned_count == 0
            and not self.invalid_grades
            and not self.missing_rationale
            and not self.missing_annotator_id
            and not self.missing_timestamp
        )


def validate(input_path: Path, mode: str) -> QcResult:
    """Run every structural QC check against `input_path`.

    Args:
        input_path: A `.jsonl` file matching `annotation_queue.jsonl`'s schema.
        mode: `"pre"` or `"final"` — see module docstring.

    Returns:
        A populated `QcResult`.

    Raises:
        ValueError: If `mode` is not `"pre"` or `"final"`.
        FileNotFoundError: If `input_path` does not exist.
    """
    if mode not in ("pre", "final"):
        raise ValueError(f"mode must be 'pre' or 'final', got {mode!r}")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    result = QcResult(mode=mode, input_path=input_path)
    seen_pairs: Counter[tuple[str, str]] = Counter()
    records: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                result.malformed_lines.append((line_no, str(exc)))
                continue
            records.append(rec)

    result.n_records = len(records)

    for line_no, rec in enumerate(records, start=1):
        qid = rec.get("query_id")
        repo = rec.get("repository")
        file_path = rec.get("file_path")

        if not qid:
            result.missing_query_ids.append(line_no)

        if repo not in REPO_LOCAL_PATHS:
            result.invalid_repositories.append((line_no, str(repo)))

        expected_commit = COMMIT_SHAS.get(repo)
        actual_commit = rec.get("commit_sha")
        if expected_commit is not None and actual_commit != expected_commit:
            result.invalid_commits.append((line_no, str(actual_commit), expected_commit))

        if repo in REPO_LOCAL_PATHS and file_path:
            full_path = os.path.join(REPO_LOCAL_PATHS[repo], str(file_path).replace("/", os.sep))
            if not os.path.isfile(full_path):
                result.invalid_file_paths.append((qid, repo, file_path))

        if qid and file_path:
            seen_pairs[(qid, file_path)] += 1

        grade = rec.get("grade")
        if grade == PLACEHOLDER_GRADE:
            result.to_be_assigned_count += 1
        else:
            valid_int_grade = isinstance(grade, int) and not isinstance(grade, bool) and grade in VALID_GRADES
            if not valid_int_grade:
                result.invalid_grades.append((qid, file_path, grade))
            else:
                result.grade_distribution[grade] += 1
                if grade >= 1 and not str(rec.get("rationale", "")).strip():
                    result.missing_rationale.append((qid, file_path))
                if not str(rec.get("annotator_id", "")).strip():
                    result.missing_annotator_id.append((qid, file_path))
                if not str(rec.get("timestamp", "")).strip():
                    result.missing_timestamp.append((qid, file_path))

    result.duplicate_pairs = {k: v for k, v in seen_pairs.items() if v > 1}
    return result


def format_report(result: QcResult) -> str:
    lines = [
        f"# QC Validation Report -- mode={result.mode}",
        "",
        f"Input: `{result.input_path}`",
        f"Records: {result.n_records}",
        "",
        "## Structural checks",
        "",
        f"- Malformed JSONL lines: {len(result.malformed_lines)}" + (f" {result.malformed_lines[:5]}" if result.malformed_lines else ""),
        f"- Missing query IDs (by line): {len(result.missing_query_ids)}" + (f" {result.missing_query_ids[:10]}" if result.missing_query_ids else ""),
        f"- Invalid repository values: {len(result.invalid_repositories)}" + (f" {result.invalid_repositories[:5]}" if result.invalid_repositories else ""),
        f"- Commit SHA mismatches: {len(result.invalid_commits)}" + (f" {result.invalid_commits[:5]}" if result.invalid_commits else ""),
        f"- Invalid/nonexistent file paths (checked against local clones just now): {len(result.invalid_file_paths)}" + (f" {result.invalid_file_paths[:5]}" if result.invalid_file_paths else ""),
        f"- Duplicate (query_id, file_path) pairs: {len(result.duplicate_pairs)}" + (f" {list(result.duplicate_pairs.items())[:5]}" if result.duplicate_pairs else ""),
        "",
        "## Grade-related checks",
        "",
        f"- Remaining `TO_BE_ASSIGNED`: {result.to_be_assigned_count}",
        f"- Invalid grade values (not TO_BE_ASSIGNED and not in {{0,1,2,3}}): {len(result.invalid_grades)}" + (f" {result.invalid_grades[:5]}" if result.invalid_grades else ""),
        f"- Missing rationale (grade >= 1): {len(result.missing_rationale)}" + (f" {result.missing_rationale[:5]}" if result.missing_rationale else ""),
        f"- Missing annotator_id (on graded records): {len(result.missing_annotator_id)}" + (f" {result.missing_annotator_id[:5]}" if result.missing_annotator_id else ""),
        f"- Missing timestamp (on graded records): {len(result.missing_timestamp)}" + (f" {result.missing_timestamp[:5]}" if result.missing_timestamp else ""),
        f"- Grade distribution (of validly-graded records): {dict(sorted(result.grade_distribution.items()))}",
        "",
    ]
    if result.mode == "pre":
        verdict = "PASS" if result.is_valid_pre else "FAIL"
        lines.append(f"## Verdict: PRE-ANNOTATION {verdict}")
        lines.append("")
        lines.append(
            "(`TO_BE_ASSIGNED` is expected and not counted against this verdict in `pre` mode -- "
            "only structural checks gate PRE-ANNOTATION validity.)"
        )
    else:
        verdict = "PASS" if result.is_valid_final else "FAIL"
        lines.append(f"## Verdict: FINAL-ANNOTATION {verdict}")
        lines.append("")
        if result.to_be_assigned_count > 0:
            lines.append(
                f"**FAIL reason: {result.to_be_assigned_count} judgment(s) still `TO_BE_ASSIGNED`.** "
                "Final annotation requires this to be exactly 0."
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["pre", "final"], default="pre")
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parent / "annotation_queue.jsonl")
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)

    result = validate(args.input, args.mode)
    report = format_report(result)
    print(report)

    report_path = args.report_path or (args.input.parent / f"qc_report_{args.mode}_{args.input.stem}.md")
    report_path.write_text(report, encoding="utf-8")

    passed = result.is_valid_pre if args.mode == "pre" else result.is_valid_final
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
