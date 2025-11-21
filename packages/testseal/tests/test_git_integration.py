from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path

import pytest
import testseal.diff as diff_module
from testseal import Auditor
from testseal.cli import main
from testseal.diff import DiffError, GitRepository

OLD = "def test_value():\n    assert value == expected\n"
NEW = "def test_value():\n    assert value\n"


def git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {process.stderr.strip()}")
    return process.stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, Path, str]:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "testseal@example.invalid")
    git(tmp_path, "config", "user.name", "TestSeal tests")
    test_file = tmp_path / "tests" / "test_value.py"
    test_file.parent.mkdir()
    test_file.write_text(OLD, encoding="utf-8")
    git(tmp_path, "add", "tests/test_value.py")
    git(tmp_path, "commit", "-q", "--no-gpg-sign", "--no-verify", "-m", "initial")
    base = git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, test_file, base


def test_worktree_and_staged_scans_hydrate_both_sources(tmp_path: Path) -> None:
    root, test_file, _ = repository(tmp_path)
    test_file.write_text(NEW, encoding="utf-8")
    repo = GitRepository(root)

    [working] = repo.working_changes()
    assert working.old_source == OLD
    assert working.new_source == NEW
    assert [item.rule_id for item in Auditor().audit([working]).findings] == ["TS003"]

    git(root, "add", "tests/test_value.py")
    [staged] = repo.staged_changes()
    assert staged.old_source == OLD
    assert staged.new_source == NEW
    assert [item.rule_id for item in Auditor().audit([staged]).findings] == ["TS003"]


def test_worktree_and_index_honor_python_encoding_cookie(tmp_path: Path) -> None:
    root, test_file, _ = repository(tmp_path)
    old = (
        b"# coding: latin-1\n# caf\xe9\n"
        b"def test_value():\n    assert value == expected\n"
    )
    new = b"# coding: latin-1\n# caf\xe9\ndef test_value():\n    assert value\n"
    test_file.write_bytes(old)
    git(root, "add", "tests/test_value.py")
    git(root, "commit", "-q", "--no-gpg-sign", "--no-verify", "-m", "latin-1")
    test_file.write_bytes(new)

    repo = GitRepository(root)
    [working] = repo.working_changes()
    assert "caf\u00e9" in (working.old_source or "")
    assert "caf\u00e9" in (working.new_source or "")
    assert [item.rule_id for item in Auditor().audit([working]).findings] == ["TS003"]

    git(root, "add", "tests/test_value.py")
    [staged] = repo.staged_changes()
    assert "caf\u00e9" in (staged.new_source or "")
    assert [item.rule_id for item in Auditor().audit([staged]).findings] == ["TS003"]


def test_worktree_scan_includes_filtered_non_ignored_untracked_files(
    tmp_path: Path,
) -> None:
    root, _, _ = repository(tmp_path)
    (root / ".gitignore").write_text("tests/test_ignored.py\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-q", "--no-gpg-sign", "--no-verify", "-m", "ignore")

    first = root / "tests" / "test_untracked.py"
    second = root / "tests" / "test_other.py"
    ignored = root / "tests" / "test_ignored.py"
    first.write_text(
        "import pytest\n\n@pytest.mark.skip(reason='later')\ndef test_new():\n    pass\n",
        encoding="utf-8",
    )
    second.write_text("def test_other():\n    assert value\n", encoding="utf-8")
    ignored.write_text("def test_ignored():\n    assert value\n", encoding="utf-8")

    repo = GitRepository(root)
    all_changes = repo.working_changes()
    assert [change.path for change in all_changes] == [
        "tests/test_other.py",
        "tests/test_untracked.py",
    ]

    changes = repo.working_changes(paths=["tests/test_untracked.py"])

    assert [change.path for change in changes] == ["tests/test_untracked.py"]
    assert changes[0].is_added
    assert changes[0].old_source is None
    assert changes[0].new_source == first.read_text(encoding="utf-8")
    assert len(changes[0].added_lines) == 5
    assert [finding.rule_id for finding in Auditor().audit(changes).findings] == [
        "TS002"
    ]


def test_revision_scan_uses_merge_base_and_head_blobs(tmp_path: Path) -> None:
    root, test_file, base = repository(tmp_path)
    test_file.write_text(NEW, encoding="utf-8")
    git(root, "add", "tests/test_value.py")
    git(root, "commit", "-q", "--no-gpg-sign", "--no-verify", "-m", "weaken test")

    [change] = GitRepository(root).revision_changes(base, "HEAD")
    assert change.old_source == OLD
    assert change.new_source == NEW
    assert [item.rule_id for item in Auditor().audit([change]).findings] == ["TS003"]


def test_worktree_scan_decodes_git_quoted_unicode_path(tmp_path: Path) -> None:
    root, _, _ = repository(tmp_path)
    unicode_file = root / "tests" / "test_café.py"
    unicode_file.write_text(OLD, encoding="utf-8")
    git(root, "add", "tests/test_café.py")
    git(root, "commit", "-q", "--no-gpg-sign", "--no-verify", "-m", "add unicode test")
    unicode_file.write_text(NEW, encoding="utf-8")

    [change] = GitRepository(root).working_changes(paths=["tests/test_café.py"])
    assert change.path == "tests/test_café.py"
    assert change.old_source == OLD
    assert change.new_source == NEW


def test_cli_staged_scan_emits_json_and_enforces_threshold(tmp_path: Path) -> None:
    root, test_file, _ = repository(tmp_path)
    test_file.write_text(NEW, encoding="utf-8")
    git(root, "add", "tests/test_value.py")
    stdout = StringIO()
    code = main(
        [
            "scan",
            "--repo",
            str(root),
            "--staged",
            "--format",
            "json",
            "--fail-on",
            "high",
        ],
        stdout=stdout,
        stderr=StringIO(),
    )
    assert code == 1
    payload = json.loads(stdout.getvalue())
    assert payload["summary"]["files_scanned"] == 1
    assert payload["findings"][0]["rule_id"] == "TS003"


def test_cli_discovers_configuration_from_git_root(tmp_path: Path) -> None:
    root, test_file, _ = repository(tmp_path)
    (root / "testseal.toml").write_text(
        '[testseal]\nfail_on = "high"\n', encoding="utf-8"
    )
    test_file.write_text(NEW, encoding="utf-8")
    git(root, "add", "tests/test_value.py")

    code = main(
        ["scan", "--repo", str(root / "tests"), "--staged"],
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert code == 1


def test_cli_parse_warning_is_advisory_until_a_threshold_is_enabled(
    tmp_path: Path,
) -> None:
    root, test_file, _ = repository(tmp_path)
    test_file.write_text(
        "def test_value(:\n    assert value == expected\n", encoding="utf-8"
    )

    advisory_stdout = StringIO()
    advisory_code = main(
        ["scan", "--repo", str(root)],
        stdout=advisory_stdout,
        stderr=StringIO(),
    )
    blocking_stdout = StringIO()
    blocking_code = main(
        ["scan", "--repo", str(root), "--fail-on", "high"],
        stdout=blocking_stdout,
        stderr=StringIO(),
    )

    assert advisory_code == 0
    assert blocking_code == 2
    assert "Warning:" in advisory_stdout.getvalue()
    assert "Warning:" in blocking_stdout.getvalue()


@pytest.mark.parametrize(
    "method, revision",
    [
        ("working", "--no-index"),
        ("base", "--all"),
        ("head", "--output=stolen.patch"),
        ("base", "HEAD\n--all"),
        ("base", ""),
    ],
)
def test_revision_values_cannot_inject_git_options(
    tmp_path: Path, method: str, revision: str
) -> None:
    root, _, _ = repository(tmp_path)
    repo = GitRepository(root)
    with pytest.raises(DiffError, match="invalid .* revision"):
        if method == "working":
            repo.working_changes(head=revision)
        elif method == "base":
            repo.revision_changes(revision)
        else:
            repo.revision_changes("HEAD", revision)


def test_cli_accepts_head_for_worktree_and_base_modes(tmp_path: Path) -> None:
    root, _, base = repository(tmp_path)
    for arguments in (["--head", "HEAD"], ["--base", base, "--head", "HEAD"]):
        stdout = StringIO()
        code = main(
            ["scan", "--repo", str(root), *arguments, "--format", "json"],
            stdout=stdout,
            stderr=StringIO(),
        )
        assert code == 0
        assert json.loads(stdout.getvalue())["summary"]["files_scanned"] == 0


@pytest.mark.parametrize("revision_argument", ["--head=", "--base="])
def test_cli_rejects_empty_explicit_revisions(
    tmp_path: Path, revision_argument: str
) -> None:
    root, _, _ = repository(tmp_path)
    stderr = StringIO()
    code = main(
        ["scan", "--repo", str(root), revision_argument],
        stdout=StringIO(),
        stderr=stderr,
    )
    assert code == 2
    assert "invalid" in stderr.getvalue()


def test_cli_reports_missing_git_as_an_operational_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git executable not found")

    monkeypatch.setattr(diff_module.subprocess, "run", missing_git)
    stderr = StringIO()
    code = main(["scan"], stdout=StringIO(), stderr=stderr)

    assert code == 2
    assert "testseal: error: cannot execute Git" in stderr.getvalue()
