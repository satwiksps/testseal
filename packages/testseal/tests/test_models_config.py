from __future__ import annotations

from pathlib import Path

import pytest
from testseal.config import Config, ConfigError, config_from_mapping, load_config
from testseal.models import AuditResult, Confidence, Finding, Severity


def finding(severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        rule_id="TS001",
        title="Assertion removed",
        message="removed",
        severity=severity,
        confidence=Confidence.HIGH,
        path=r"tests\test_api.py",
        line=0,
        evidence="assert value",
    )


def test_finding_normalizes_location_path_and_fingerprint() -> None:
    first = finding()
    second = finding()
    assert first.line == 1
    assert first.fingerprint == second.fingerprint
    assert first.to_dict()["path"] == "tests/test_api.py"
    assert "help_uri" not in first.to_dict()


def test_audit_result_summary_and_threshold() -> None:
    result = AuditResult(2, [finding(Severity.MEDIUM), finding(Severity.LOW)])
    assert result.summary == {
        "files_scanned": 2,
        "finding_count": 2,
        "suppressed_count": 0,
        "by_severity": {"low": 1, "medium": 1, "high": 0},
    }
    assert result.fails_at(Severity.MEDIUM)
    assert not result.fails_at(Severity.HIGH)
    assert not result.fails_at(None)


def test_default_config_recognizes_conventional_tests_and_excludes_venv() -> None:
    config = Config()
    assert config.includes_path("tests/test_api.py")
    assert config.is_test_path("tests/test_api.py")
    assert config.is_test_path("tests/conftest.py")
    assert config.is_test_path("pkg/tests/test_model.py")
    assert config.is_test_path("pkg/tests/conftest.py")
    assert config.is_test_path("widget_test.py")
    assert not config.includes_path(".venv/lib/test_noise.py")
    assert not config.includes_path(".git/hooks/test_noise.py")
    assert not config.includes_path("vendor/node_modules/pkg/test_noise.py")
    assert not config.includes_path("pkg/build/generated.py")


def test_config_mapping_supports_rule_policy() -> None:
    config = config_from_mapping(
        {
            "fail_on": "medium",
            "disabled_rules": ["TS006"],
            "rules": {"TS001": {"enabled": True, "severity": "medium"}},
            "guarding_tests": {"src/**/*.py": ["tests/**/*.py"]},
            "ignore_fingerprints": ["ABCDEF0123456789ABCDEF01"],
        }
    )
    assert config.fail_on is Severity.MEDIUM
    assert not config.rule_enabled("TS006")
    assert config.severity_for("TS001", Severity.HIGH) is Severity.MEDIUM
    assert config.guarding_tests["src/**/*.py"] == ("tests/**/*.py",)
    assert config.ignore_fingerprints == frozenset({"abcdef0123456789abcdef01"})


@pytest.mark.parametrize(
    "document",
    [
        'fail_on = "high"\n',
        '[testseal]\nfail_on = "high"\n',
        '[tool.testseal]\nfail_on = "high"\n',
    ],
)
def test_explicit_config_supports_flat_standalone_and_pyproject_shapes(
    tmp_path: Path, document: str
) -> None:
    path = tmp_path / "testseal.toml"
    path.write_text(document, encoding="utf-8")
    assert load_config(path).fail_on is Severity.HIGH


def test_auto_discovered_pyproject_without_table_uses_defaults(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n', encoding="utf-8"
    )
    assert load_config(cwd=tmp_path) == Config()


def test_auto_discovered_testseal_toml_precedes_pyproject(tmp_path: Path) -> None:
    (tmp_path / "testseal.toml").write_text(
        '[testseal]\nfail_on = "low"\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.testseal]\nfail_on = "high"\n', encoding="utf-8"
    )
    assert load_config(cwd=tmp_path).fail_on is Severity.LOW


@pytest.mark.parametrize(
    "mapping, message",
    [
        ({"fail_on": "urgent"}, "invalid fail_on"),
        ({"exclude": "build/**"}, "exclude must be an array"),
        ({"rules": {"TS001": {"enabled": "yes"}}}, "must be a boolean"),
        ({"rules": {"TS001": {"severity": 3}}}, "invalid severity"),
        ({"guarding_tests": []}, "guarding_tests must be a table"),
        ({"fail_on_typo": "high"}, "unknown configuration key"),
        ({"disabled_rules": ["TS999"]}, "unknown rule id in disabled_rules"),
        ({"rules": {"TS999": {}}}, "unknown rule id in rules"),
        ({"rules": {"TS001": {"severty": "high"}}}, "unknown key in rules.TS001"),
        (
            {"ignore_fingerprints": ["too-short"]},
            "exactly 24 hexadecimal characters",
        ),
        (
            {"ignore_fingerprints": ["z" * 24]},
            "exactly 24 hexadecimal characters",
        ),
        (
            {"ignore_fingerprints": "abcdef0123456789abcdef01"},
            "ignore_fingerprints must be an array",
        ),
    ],
)
def test_invalid_config_is_rejected(mapping: object, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        config_from_mapping(mapping)  # type: ignore[arg-type]


def test_missing_explicit_config_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")
