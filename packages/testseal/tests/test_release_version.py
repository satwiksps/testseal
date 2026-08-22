from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_release_version as checker

EXPECTED = "1.2.3"


def configure_release_check(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    citation_version: str = EXPECTED,
) -> None:
    (root / "CITATION.cff").write_text(
        f'version: "{citation_version}"\n', encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", root)
    monkeypatch.setattr(checker, "_validate_ci_context", lambda: None)
    monkeypatch.setattr(checker, "_read_python_versions", lambda: (EXPECTED, EXPECTED))
    monkeypatch.setattr(
        checker,
        "_read_node_versions",
        lambda directory, label: (EXPECTED, EXPECTED),
    )
    monkeypatch.setattr(checker, "_has_release_heading", lambda version: True)
    monkeypatch.setenv("RELEASE_TAG", f"v{EXPECTED}")


def test_release_check_rejects_mismatched_citation_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_release_check(monkeypatch, tmp_path, citation_version="9.9.9")

    assert checker.main() == 1
    assert "CITATION.cff is 9.9.9" in capsys.readouterr().err
