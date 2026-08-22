from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from testseal import Auditor, __version__
from testseal.cli import main
from testseal.config import config_from_mapping
from testseal.diff import changes_from_sources, make_unified_diff, parse_unified_diff
from testseal.models import AuditResult
from testseal.reporters import render_json, render_sarif, render_text


def result_with_removal():
    return Auditor().audit(
        [
            changes_from_sources(
                "tests/test_x.py",
                "def test_x():\n    assert value\n",
                "def test_x():\n    pass\n",
            )
        ]
    )


def test_json_report_has_versioned_public_shape() -> None:
    payload = json.loads(render_json(result_with_removal()))
    assert list(payload) == ["version", "summary", "findings"]
    assert payload["version"] == "1"
    assert payload["summary"]["finding_count"] == 1
    assert payload["summary"]["suppressed_count"] == 0
    finding = payload["findings"][0]
    assert finding["rule_id"] == "TS001"
    assert finding["severity"] == "high"
    assert finding["confidence"] == "high"


def test_json_report_preserves_parse_warnings() -> None:
    payload = json.loads(
        render_json(
            AuditResult(
                files_scanned=1, parse_warnings=["tests/broken.py failed to parse"]
            )
        )
    )

    assert payload["warnings"] == ["tests/broken.py failed to parse"]


def test_text_report_is_actionable() -> None:
    result = result_with_removal()
    report = render_text(result)
    assert "[HIGH] TS001 tests/test_x.py:2:5 - Assertion removed" in report
    assert "Evidence: assert value" in report
    assert f"Fingerprint: {result.findings[0].fingerprint}" in report
    assert "Fix:" in report


def test_fingerprint_suppression_filters_after_deduplication_and_is_reported() -> None:
    change = changes_from_sources(
        "tests/test_x.py",
        "def test_x():\n    assert value\n",
        "def test_x():\n    pass\n",
    )
    baseline = Auditor().audit([change])
    fingerprint = baseline.findings[0].fingerprint
    assert fingerprint is not None

    config = config_from_mapping({"ignore_fingerprints": [fingerprint.upper()]})
    result = Auditor(config).audit([change, change])

    assert result.findings == []
    assert result.suppressed_count == 1
    assert result.summary == {
        "files_scanned": 2,
        "finding_count": 0,
        "suppressed_count": 1,
        "by_severity": {"low": 0, "medium": 0, "high": 0},
    }

    payload = json.loads(render_json(result))
    assert payload["version"] == "1"
    assert payload["summary"]["suppressed_count"] == 1
    assert payload["findings"] == []
    assert "no test-integrity findings across 2 changed file(s)" in render_text(result)
    assert "1 finding(s) suppressed by fingerprint" in render_text(result)


def test_fingerprint_suppression_does_not_hide_same_evidence_in_another_scope() -> None:
    change = changes_from_sources(
        "tests/test_x.py",
        ("def test_one():\n    assert value\n\ndef test_two():\n    assert value\n"),
        "def test_one():\n    pass\n\ndef test_two():\n    pass\n",
    )
    baseline = Auditor().audit([change])
    assert len(baseline.findings) == 2
    first_fingerprint = baseline.findings[0].fingerprint
    second_fingerprint = baseline.findings[1].fingerprint
    assert first_fingerprint is not None
    assert second_fingerprint is not None
    assert first_fingerprint != second_fingerprint

    config = config_from_mapping({"ignore_fingerprints": [first_fingerprint]})
    result = Auditor(config).audit([change])

    assert result.suppressed_count == 1
    assert [finding.fingerprint for finding in result.findings] == [second_fingerprint]


def test_fallback_fingerprints_distinguish_identical_scope_less_findings() -> None:
    patch = make_unified_diff(
        "tests/test_x.py",
        ("def test_one():\n    assert value\n\ndef test_two():\n    assert value\n"),
        "def test_one():\n    pass\n\ndef test_two():\n    pass\n",
    )
    changes = parse_unified_diff(patch)
    baseline = Auditor().audit(changes)
    fingerprints = [finding.fingerprint for finding in baseline.findings]
    assert len(fingerprints) == 2
    assert None not in fingerprints
    assert len(set(fingerprints)) == 2
    assert fingerprints == [
        finding.fingerprint for finding in Auditor().audit(changes).findings
    ]

    config = config_from_mapping({"ignore_fingerprints": [fingerprints[0]]})
    result = Auditor(config).audit(changes)
    assert result.suppressed_count == 1
    assert [finding.fingerprint for finding in result.findings] == [fingerprints[1]]


def test_sarif_report_is_valid_shape_and_uses_forward_slash_uri() -> None:
    payload = json.loads(render_sarif(result_with_removal()))
    assert payload["version"] == "2.1.0"
    run = payload["runs"][0]
    assert run["tool"]["driver"]["name"] == "TestSeal"
    assert run["tool"]["driver"]["semanticVersion"] == __version__
    assert run["tool"]["driver"]["informationUri"] == (
        "https://github.com/satwiksps/testseal"
    )
    assert run["tool"]["driver"]["rules"][0]["helpUri"].endswith(
        "/rules/#ts001-assertion-removed"
    )
    assert run["results"][0]["ruleId"] == "TS001"
    assert run["results"][0]["level"] == "error"
    assert (
        run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "tests/test_x.py"
    )


def test_sarif_surfaces_parse_warnings_as_tool_notifications() -> None:
    payload = json.loads(
        render_sarif(
            AuditResult(files_scanned=1, parse_warnings=["invalid syntax in test.py"])
        )
    )
    [notification] = payload["runs"][0]["invocations"][0]["toolExecutionNotifications"]
    assert notification["level"] == "warning"
    assert notification["descriptor"]["id"] == "TS-PARSE-WARNING"
    assert notification["message"]["text"] == "invalid syntax in test.py"


def test_cli_diff_stdin_is_advisory_by_default() -> None:
    patch = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert value\n",
        "def test_x():\n    pass\n",
    )
    stdout = StringIO()
    stderr = StringIO()
    code = main(
        ["scan", "--diff", "-", "--format", "json"],
        stdin=StringIO(patch),
        stdout=stdout,
        stderr=stderr,
    )
    assert code == 0
    assert json.loads(stdout.getvalue())["summary"]["finding_count"] == 1
    assert stderr.getvalue() == ""


def test_cli_fail_threshold_returns_one() -> None:
    patch = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert value\n",
        "def test_x():\n    pass\n",
    )
    assert (
        main(
            ["scan", "--diff", "-", "--fail-on", "high"],
            stdin=StringIO(patch),
            stdout=StringIO(),
            stderr=StringIO(),
        )
        == 1
    )


def test_cli_demo_is_config_independent_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "testseal.toml").write_text(
        '[testseal]\ndisabled_rules = ["TS003"]\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()

    code = main(["demo"], stdout=stdout, stderr=StringIO())

    assert code == 0
    assert stdout.getvalue() == (
        "[HIGH] TS003 tests/test_totals.py:10:1 - Assertion weakened\n"
        "  A specific equality assertion was replaced by a truthy/non-null check\n"
        '  Evidence: assert total == Decimal("19.99")  ->  assert total\n'
        "  Fingerprint: 3c056c0da89673cd1a42eacc\n"
        "  Fix: Assert the specific expected value, type, relationship, or exception.\n"
        "\n"
        "TestSeal: 1 finding(s) in 1 changed file(s) "
        "(high 1, medium 0, low 0).\n"
    )


def test_cli_failed_atomic_replace_preserves_existing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "report.txt"
    previous = "previous report\n"
    output.write_text(previous, encoding="utf-8")
    patch = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert value\n",
        "def test_x():\n    pass\n",
    )

    def fail_replace(source: Path, target: str | Path) -> Path:
        assert Path(target) == output
        assert output.read_text(encoding="utf-8") == previous
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    stderr = StringIO()
    code = main(
        ["scan", "--diff", "-", "--output", str(output)],
        stdin=StringIO(patch),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert code == 2
    assert output.read_text(encoding="utf-8") == previous
    assert "cannot write report" in stderr.getvalue()
    assert "simulated replacement failure" in stderr.getvalue()
    assert list(tmp_path.iterdir()) == [output]


def test_cli_output_writes_the_rendered_report(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "testseal.json"
    patch = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert value\n",
        "def test_x():\n    pass\n",
    )
    stdout = StringIO()

    code = main(
        ["scan", "--diff", "-", "--format", "json", "--output", str(output)],
        stdin=StringIO(patch),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == ""
    assert (
        json.loads(output.read_text(encoding="utf-8"))["summary"]["finding_count"] == 1
    )


def test_cli_filters_an_external_diff_by_positional_path() -> None:
    patch = (
        make_unified_diff(
            "tests/test_one.py",
            "def test_one():\n    assert one\n",
            "def test_one():\n    pass\n",
        )
        + "\n"
        + make_unified_diff(
            "tests/test_two.py",
            "def test_two():\n    assert two\n",
            "def test_two():\n    pass\n",
        )
    )
    stdout = StringIO()

    code = main(
        ["scan", "--diff", "-", "--format", "json", "tests/test_one.py"],
        stdin=StringIO(patch),
        stdout=stdout,
        stderr=StringIO(),
    )

    payload = json.loads(stdout.getvalue())
    assert code == 0
    assert payload["summary"]["files_scanned"] == 1
    assert [finding["path"] for finding in payload["findings"]] == ["tests/test_one.py"]


def test_cli_piped_diff_detects_canonical_assertion_downgrade() -> None:
    patch = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert result == expected\n",
        "def test_x():\n    assert result is not None\n",
    )
    stdout = StringIO()
    code = main(
        ["scan", "--diff", "-", "--format", "json"],
        stdin=StringIO(patch),
        stdout=stdout,
        stderr=StringIO(),
    )
    assert code == 0
    assert [item["rule_id"] for item in json.loads(stdout.getvalue())["findings"]] == [
        "TS003"
    ]


def test_cli_piped_diff_detects_literal_tolerance_widening_only() -> None:
    wider = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert x == pytest.approx(1, rel=1e-6)\n",
        "def test_x():\n    assert x == pytest.approx(1, rel=1e-2)\n",
    )
    stdout = StringIO()
    main(
        ["scan", "--diff", "-", "--format", "json"],
        stdin=StringIO(wider),
        stdout=stdout,
        stderr=StringIO(),
    )
    assert "TS004" in [
        item["rule_id"] for item in json.loads(stdout.getvalue())["findings"]
    ]

    tighter = make_unified_diff(
        "tests/test_x.py",
        "def test_x():\n    assert x == pytest.approx(1, rel=1e-2)\n",
        "def test_x():\n    assert x == pytest.approx(1, rel=1e-6)\n",
    )
    stdout = StringIO()
    main(
        ["scan", "--diff", "-", "--format", "json"],
        stdin=StringIO(tighter),
        stdout=stdout,
        stderr=StringIO(),
    )
    assert "TS004" not in [
        item["rule_id"] for item in json.loads(stdout.getvalue())["findings"]
    ]


def test_cli_missing_diff_returns_operational_error() -> None:
    stderr = StringIO()
    code = main(
        ["scan", "--diff", "does-not-exist.patch"],
        stdout=StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert "testseal: error:" in stderr.getvalue()


def test_cli_truncated_diff_returns_operational_error() -> None:
    patch = """--- a/tests/test_x.py
+++ b/tests/test_x.py
@@ -1,2 +1,2 @@
 context
-assert value == 1
"""
    stderr = StringIO()
    code = main(
        ["scan", "--diff", "-"],
        stdin=StringIO(patch),
        stdout=StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert "testseal: error: incomplete hunk" in stderr.getvalue()


def test_cli_non_diff_input_returns_an_operational_error() -> None:
    stdout = StringIO()
    stderr = StringIO()

    code = main(
        ["scan", "--diff", "-", "--fail-on", "high"],
        stdin=StringIO("this is not a unified diff\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 2
    assert stdout.getvalue() == ""
    assert "does not contain a unified diff" in stderr.getvalue()


def test_cli_non_string_rule_severity_is_a_config_error(tmp_path: Path) -> None:
    config = tmp_path / "testseal.toml"
    config.write_text("[rules.TS001]\nseverity = 3\n", encoding="utf-8")
    stderr = StringIO()
    code = main(
        ["scan", "--config", str(config), "--diff", "-"],
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert "testseal: error: invalid severity for rules.TS001" in stderr.getvalue()


def test_cli_rejects_explicit_head_for_diff_and_staged_modes(tmp_path: Path) -> None:
    for mode in (["--diff", "-"], ["--staged"]):
        stderr = StringIO()
        code = main(
            ["scan", "--repo", str(tmp_path), *mode, "--head", "HEAD"],
            stdin=StringIO(""),
            stdout=StringIO(),
            stderr=stderr,
        )
        assert code == 2
        assert "--head cannot be combined" in stderr.getvalue()
