import json
from copy import deepcopy

import pytest

from benchmarks import technical_description as benchmark


def test_full_corpus_has_explicit_passing_expectations():
    report = benchmark.run_benchmark()
    assert report["summary"]["cases"] == 25
    assert report["summary"]["failed"] == 0
    assert report["summary"]["exact_supported_courses"] == 71
    assert report["summary"]["supported_course_recovery"] == 1.0
    assert report["summary"]["diagnostic_category_accuracy"] == 1.0
    assert report["summary"]["status_counts"] == {
        "complete": 15,
        "partial": 8,
        "rejected": 2,
    }
    assert report["core"]["version"] == benchmark.ptr_core.__version__
    assert set(report["core"]) == {"version", "commit", "dirty"}


def test_historical_corpus_is_preserved_and_cannot_be_a_v2_baseline():
    original_path = benchmark.DEFAULT_CORPUS.parent.parent / "td-v1" / "corpus.json"
    original, digest = benchmark.load_corpus(original_path)
    assert original["corpus_version"] == "td-v1.0.0"
    assert digest == "6d760d15f4460a52026375e6a7c28045010a8773b274eb3a0fd82491e44c8190"
    historical = benchmark.run_benchmark(original_path)
    assert {case["id"] for case in historical["cases"] if not case["passed"]} == {
        "unparsed-middle-row",
        "unsupported-number-words",
    }
    current = benchmark.run_benchmark()
    assert current["corpus"]["version"] == "td-v2.0.0"
    with pytest.raises(ValueError, match="Baseline"):
        benchmark.compare_reports(current, historical)


def test_ci_subset_represents_every_family_and_is_deterministic():
    full = benchmark.run_benchmark()
    subset = benchmark.run_benchmark(subset="ci")
    assert subset == benchmark.run_benchmark(subset="ci")
    assert subset["summary"]["failed"] == 0
    assert 0 < subset["summary"]["cases"] < full["summary"]["cases"]
    assert subset["by_family"].keys() == full["by_family"].keys()
    assert all(subset["summary"]["status_counts"].values())


def test_regression_comparison_detects_changed_course_and_family(monkeypatch):
    baseline = benchmark.run_benchmark()
    baseline["core"] = {
        "version": "previous",
        "commit": "previous-commit",
        "dirty": False,
    }
    observe = benchmark.observe

    def changed_parser(text):
        actual = observe(text)
        if text.startswith("thence North, 10 m; thence East"):
            actual["courses"][0][1] = 11.0
        return actual

    monkeypatch.setattr(benchmark, "observe", changed_parser)
    current = benchmark.run_benchmark(baseline=baseline)
    assert current["summary"]["failed"] == 1
    assert current["summary"]["supported_course_recovery"] == 70 / 71
    assert current["by_family"]["cardinal"]["failed"] == 1
    assert current["comparison"]["regressions"] == ["cardinal-square"]
    assert current["comparison"]["changed_cases"] == ["cardinal-square"]
    assert current["comparison"]["baseline_core"]["version"] == "previous"
    assert benchmark.compare_reports(baseline, current)["improvements"] == [
        "cardinal-square"
    ]


@pytest.mark.parametrize("field", ["corpus", "subset", "cases"])
def test_comparison_refuses_incompatible_baseline(field):
    report = benchmark.run_benchmark()
    baseline = deepcopy(report)
    baseline[field] = [] if field == "cases" else "different"
    with pytest.raises(ValueError, match="Baseline"):
        benchmark.compare_reports(report, baseline)


def test_corpus_hash_ignores_json_formatting_and_line_endings(tmp_path):
    corpus, digest = benchmark.load_corpus(benchmark.DEFAULT_CORPUS)
    path = tmp_path / "reformatted.json"
    path.write_bytes(json.dumps(corpus, indent=4).replace("\n", "\r\n").encode())
    assert benchmark.load_corpus(path)[1] == digest


@pytest.mark.parametrize("change", ["duplicate", "rights", "expected"])
def test_invalid_corpus_is_rejected(tmp_path, change):
    corpus, _ = benchmark.load_corpus(benchmark.DEFAULT_CORPUS)
    if change == "duplicate":
        corpus["cases"].append(corpus["cases"][0])
    elif change == "rights":
        corpus["rights"]["policy"] = "private-document"
    else:
        del corpus["cases"][0]["expected"]["courses"]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError):
        benchmark.load_corpus(path)


def test_cli_writes_report_and_returns_failure_for_mismatched_expectations(tmp_path):
    output = tmp_path / "reports" / "result.json"
    assert benchmark.main(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert benchmark.main(["--baseline", str(output), "--output", str(output)]) == 0
    assert (
        json.loads(output.read_text(encoding="utf-8"))["comparison"]["regressions"]
        == []
    )
    corpus, _ = benchmark.load_corpus(benchmark.DEFAULT_CORPUS)
    corpus["cases"][0]["expected"]["courses"][0][1] = 11
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    assert benchmark.main(["--corpus", str(path), "--output", str(output)]) == 1
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["failed"] == 1
    assert report["summary"]["failed"] == 0


def test_cli_invalid_baseline_has_clear_exit_status(tmp_path, capsys):
    baseline = tmp_path / "invalid.json"
    baseline.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--baseline", str(baseline)])
    assert error.value.code == 2
    assert "Benchmark input error" in capsys.readouterr().err


@pytest.mark.parametrize(
    "field", ["courses", "parser_diagnostic_codes", "record_created"]
)
def test_unsafe_acceptance_and_diagnostic_changes_cannot_pass(monkeypatch, field):
    corpus, _ = benchmark.load_corpus(benchmark.DEFAULT_CORPUS)
    case = next(c for c in corpus["cases"] if c["id"] == "ambiguous-azimuths")
    observed = benchmark.observe(case["text"])
    observed[field] = {
        "courses": [["N", 10], None, None],
        "parser_diagnostic_codes": [],
        "record_created": True,
    }[field]
    monkeypatch.setattr(benchmark, "observe", lambda text: observed)
    evaluated = benchmark.evaluate_case(case)
    assert not evaluated["passed"]
    assert field in evaluated["mismatches"]
