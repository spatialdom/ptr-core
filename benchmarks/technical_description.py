"""Deterministic recovered-text interpretation benchmark; no document pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import ptr_core
from ptr_core import intake_parcel, parse_technical_description

DEFAULT_CORPUS = Path(__file__).parent / "corpora" / "td-v1" / "corpus.json"
EXPECTED_FIELDS = {
    "courses",
    "destinations",
    "returns",
    "tie_courses",
    "references",
    "stated_areas",
    "parser_complete",
    "record_created",
    "status",
    "parser_diagnostic_codes",
    "intake_diagnostic_codes",
}


def load_corpus(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_bytes()
    corpus = json.loads(content)
    if (
        not isinstance(corpus, dict)
        or corpus.get("schema_version") != 1
        or not corpus.get("corpus_version")
    ):
        raise ValueError("Unsupported or missing corpus version.")
    rights = corpus.get("rights", {})
    if (
        not isinstance(rights, dict)
        or rights.get("policy") != "synthetic-only"
        or not rights.get("provenance")
    ):
        raise ValueError("Corpus must declare synthetic-only rights and provenance.")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Corpus must contain cases.")
    ids = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"]
            or case["id"] in ids
        ):
            raise ValueError("Case IDs must be unique nonempty strings.")
        ids.add(case["id"])
        if (
            not isinstance(case.get("text"), str)
            or not isinstance(case.get("family"), str)
            or not case["family"]
            or type(case.get("ci")) is not bool
        ):
            raise ValueError(f"Invalid text, family or CI selection: {case['id']}")
        expected = case.get("expected", {})
        if not isinstance(expected, dict) or set(expected) != EXPECTED_FIELDS:
            raise ValueError(f"Expected outputs must be explicit: {case['id']}")
        courses = expected["courses"]
        if not isinstance(courses, list) or not (
            len(courses) == len(expected["destinations"]) == len(expected["returns"])
        ):
            raise ValueError(
                f"Expected ordered rows have inconsistent lengths: {case['id']}"
            )
        if expected["status"] not in ("complete", "partial", "rejected"):
            raise ValueError(f"Unknown expected status: {case['id']}")
        if (
            type(expected["parser_complete"]) is not bool
            or type(expected["record_created"]) is not bool
        ):
            raise ValueError(f"Expected completeness must be boolean: {case['id']}")
    canonical = json.dumps(
        corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return corpus, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def core_revision() -> dict[str, Any]:
    """Identify the actual imported Core checkout, not just the runner checkout."""
    source = Path(ptr_core.__file__).resolve()
    try:

        def git(*args: str) -> str:
            return subprocess.check_output(
                ["git", "-C", str(source.parent), *args],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()

        git("ls-files", "--error-unmatch", source.name)
        commit, dirty = git("rev-parse", "HEAD"), bool(git("status", "--porcelain"))
    except (OSError, ValueError, subprocess.SubprocessError):
        commit, dirty = None, None
    return {"version": ptr_core.__version__, "commit": commit, "dirty": dirty}


def observe(text: str) -> dict[str, Any]:
    parsed = parse_technical_description(text)
    intake = intake_parcel(text)
    return {
        "courses": [
            r.course.to_json_value() if r.course else None for r in parsed.rows
        ],
        "destinations": [r.destination_point for r in parsed.rows],
        "returns": [r.returns_to_beginning for r in parsed.rows],
        "tie_courses": [
            r.course.to_json_value() if r.course else None for r in parsed.tie_lines
        ],
        "references": [r.value for r in parsed.reference_points],
        "stated_areas": [r.value for r in parsed.stated_areas],
        "parser_complete": parsed.complete,
        "record_created": intake.conforms,
        "status": "complete"
        if intake.conforms
        else ("partial" if parsed.courses else "rejected"),
        "parser_diagnostic_codes": sorted({d.code for d in parsed.diagnostics}),
        "intake_diagnostic_codes": sorted({d.code for d in intake.diagnostics}),
    }


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    actual = observe(case["text"])
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in sorted(EXPECTED_FIELDS)
        if expected[key] != actual[key]
    }
    expected_courses = expected["courses"]
    actual_courses = actual["courses"]
    exact_courses = sum(
        course is not None
        and index < len(actual_courses)
        and actual_courses[index] == course
        for index, course in enumerate(expected_courses)
    )
    return {
        "id": case["id"],
        "family": case["family"],
        "passed": not mismatches,
        "actual": actual,
        "mismatches": mismatches,
        "expected_supported_courses": sum(c is not None for c in expected_courses),
        "exact_supported_courses": exact_courses,
        "diagnostic_categories_match": all(
            expected[key] == actual[key]
            for key in ("parser_diagnostic_codes", "intake_diagnostic_codes")
        ),
    }


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    supported = sum(c["expected_supported_courses"] for c in cases)
    exact = sum(c["exact_supported_courses"] for c in cases)
    diagnostic_matches = sum(c["diagnostic_categories_match"] for c in cases)
    return {
        "cases": total,
        "passed": sum(c["passed"] for c in cases),
        "failed": sum(not c["passed"] for c in cases),
        "status_counts": {
            status: sum(c["actual"]["status"] == status for c in cases)
            for status in ("complete", "partial", "rejected")
        },
        "expected_supported_courses": supported,
        "exact_supported_courses": exact,
        "supported_course_recovery": exact / supported if supported else None,
        "diagnostic_category_accuracy": diagnostic_matches / total if total else None,
    }


def compare_reports(
    current: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    if baseline.get("report_version") != 1 or any(
        baseline.get(key) != current[key] for key in ("corpus", "subset")
    ):
        raise ValueError("Baseline must use the same corpus hash/version and subset.")
    before = {case["id"]: case for case in baseline["cases"]}
    after = {case["id"]: case for case in current["cases"]}
    if len(before) != len(baseline["cases"]) or before.keys() != after.keys():
        raise ValueError("Baseline case IDs do not match the selected corpus.")
    return {
        "baseline_core": baseline["core"],
        "regressions": sorted(
            key for key in after if before[key]["passed"] and not after[key]["passed"]
        ),
        "improvements": sorted(
            key for key in after if not before[key]["passed"] and after[key]["passed"]
        ),
        "changed_cases": sorted(
            key for key in after if before[key]["actual"] != after[key]["actual"]
        ),
    }


def run_benchmark(
    corpus_path: Path = DEFAULT_CORPUS,
    *,
    subset: str = "full",
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if subset not in ("ci", "full"):
        raise ValueError("Subset must be ci or full.")
    corpus, digest = load_corpus(corpus_path)
    selected = [case for case in corpus["cases"] if subset == "full" or case["ci"]]
    if not selected:
        raise ValueError("Selected subset is empty.")
    cases = [evaluate_case(case) for case in selected]
    families = sorted(Counter(case["family"] for case in cases))
    report = {
        "report_version": 1,
        "corpus": {"version": corpus["corpus_version"], "sha256": digest},
        "subset": subset,
        "core": core_revision(),
        "python": platform.python_version(),
        "summary": summarize(cases),
        "by_family": {
            family: summarize([c for c in cases if c["family"] == family])
            for family in families
        },
        "cases": cases,
    }
    if baseline is not None:
        report["comparison"] = compare_reports(report, baseline)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--subset", choices=("ci", "full"), default="full")
    parser.add_argument(
        "--output", type=Path, help="Write JSON report; default is stdout"
    )
    parser.add_argument(
        "--baseline", type=Path, help="Compare with a prior JSON report"
    )
    args = parser.parse_args(argv)
    try:
        baseline = (
            json.loads(args.baseline.read_text(encoding="utf-8"))
            if args.baseline
            else None
        )
        report = run_benchmark(args.corpus, subset=args.subset, baseline=baseline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Benchmark input error: {exc}\n")
    content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
