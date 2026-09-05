from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import testseal.diff as diff_module
from testseal import audit_diff
from testseal.diff import (
    DiffError,
    GitRepository,
    changes_from_sources,
    make_unified_diff,
    parse_unified_diff,
)


def test_audit_diff_reports_a_canonical_assertion_weakening() -> None:
    patch = make_unified_diff(
        "tests/test_value.py",
        "def test_value():\n    assert value == 1\n",
        "def test_value():\n    assert value\n",
    )

    result = audit_diff(patch)

    assert result.files_scanned == 1
    assert [finding.rule_id for finding in result.findings] == ["TS003"]


@pytest.mark.parametrize(
    "patch",
    [
        "--- a/tests/test_value.py\n",
        "+++ b/tests/test_value.py\n",
        "--- a/tests/test_value.py\n+++ b/tests/test_value.py\n",
        "diff --git a/tests/test_value.py b/tests/test_value.py\n",
        "--- a/tests/test_value.py\n@@ -1 +1 @@\n-old\n+new\n",
        "+++ b/tests/test_value.py\n@@ -1 +1 @@\n-old\n+new\n",
    ],
)
def test_parse_unified_diff_rejects_incomplete_file_sections(patch: str) -> None:
    with pytest.raises(DiffError, match="incomplete file diff"):
        parse_unified_diff(patch)


def test_parse_git_diff_tracks_old_and_new_line_numbers() -> None:
    patch = """diff --git a/tests/test_a.py b/tests/test_a.py
index 123..456 100644
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -2,3 +2,3 @@ def test_a():
 context
-assert value == 1
+assert value
 tail
"""
    [change] = parse_unified_diff(patch)
    assert change.path == "tests/test_a.py"
    assert [(line.kind, line.old_line, line.new_line) for line in change.lines] == [
        (" ", 2, 2),
        ("-", 3, None),
        ("+", None, 3),
        (" ", 4, 4),
    ]
    assert change.new_line_for_old(3) == 3


def test_parse_added_and_deleted_files() -> None:
    added = """diff --git a/tests/test_new.py b/tests/test_new.py
new file mode 100644
--- /dev/null
+++ b/tests/test_new.py
@@ -0,0 +1 @@
+pytest.skip('later')
"""
    [change] = parse_unified_diff(added)
    assert change.is_added
    assert change.old_path is None
    assert change.new_path == "tests/test_new.py"

    deleted = added.replace("new file mode", "deleted file mode").replace(
        "--- /dev/null\n+++ b/tests/test_new.py\n@@ -0,0 +1 @@\n+pytest",
        "--- a/tests/test_new.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-pytest",
    )
    [change] = parse_unified_diff(deleted)
    assert change.is_deleted


def test_changes_from_sources_hydrates_sources_without_blank_diff_lines() -> None:
    old = "def test_x():\n    assert answer == 42\n"
    new = "def test_x():\n    pass\n"
    change = changes_from_sources("tests/test_x.py", old, new)
    assert change.old_source == old
    assert change.new_source == new
    assert [line.content for line in change.deleted_lines] == [
        "    assert answer == 42"
    ]
    assert change.new_line_for_old(2) == 2


def test_make_diff_round_trips_multiple_hunks() -> None:
    old = "\n".join(f"line_{index}" for index in range(20))
    new_lines = old.splitlines()
    new_lines[1] = "changed_1"
    new_lines[18] = "changed_18"
    parsed = parse_unified_diff(
        make_unified_diff("data.txt", old, "\n".join(new_lines))
    )
    assert len(parsed) == 1
    assert len(parsed[0].added_lines) == 2


def test_parse_decodes_git_c_quoted_utf8_paths_before_normalizing() -> None:
    patch = r"""diff --git "a/tests/test_caf\303\251.py" "b/tests/test_caf\303\251.py"
index 123..456 100644
--- "a/tests/test_caf\303\251.py"
+++ "b/tests/test_caf\303\251.py"
@@ -1 +1 @@
-assert value == 1
+assert value
"""
    [change] = parse_unified_diff(patch)
    assert change.old_path == "tests/test_café.py"
    assert change.new_path == "tests/test_café.py"
    assert change.path == "tests/test_café.py"


def test_parse_ordinary_unified_diff_with_multiple_files() -> None:
    patch = """--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1 +1 @@
-assert a == 1
+assert a
--- a/tests/test_b.py
+++ b/tests/test_b.py
@@ -1 +1 @@
-assert b == 2
+assert b
"""
    changes = parse_unified_diff(patch)
    assert [change.path for change in changes] == [
        "tests/test_a.py",
        "tests/test_b.py",
    ]
    assert [line.content for line in changes[0].deleted_lines] == ["assert a == 1"]
    assert [line.content for line in changes[1].added_lines] == ["assert b"]


def test_header_like_changed_lines_are_not_parsed_as_file_headers() -> None:
    patch = """--- a/tests/test_markers.py
+++ b/tests/test_markers.py
@@ -1 +1 @@
--- old-looking-content
+++ new-looking-content
"""
    [change] = parse_unified_diff(patch)
    assert change.old_path == "tests/test_markers.py"
    assert change.new_path == "tests/test_markers.py"
    assert [line.content for line in change.deleted_lines] == ["-- old-looking-content"]
    assert [line.content for line in change.added_lines] == ["++ new-looking-content"]


def test_parse_rejects_a_truncated_hunk_instead_of_returning_partial_data() -> None:
    patch = """--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1,2 +1,2 @@
 context
-assert value == 1
"""
    with pytest.raises(DiffError, match="incomplete hunk.*1 more new line"):
        parse_unified_diff(patch)


def test_patch_control_characters_do_not_create_phantom_lines() -> None:
    patch = (
        "--- a/data.bin\n+++ b/data.bin\n@@ -1 +1 @@\n"
        "-old\x00\v\f\x85\u2028value\n+new\x00\v\f\x85\u2028value\n"
    )
    [change] = parse_unified_diff(patch)
    assert [(line.kind, line.content) for line in change.lines] == [
        ("-", "old\x00\v\f\x85\u2028value"),
        ("+", "new\x00\v\f\x85\u2028value"),
    ]


@pytest.mark.parametrize(
    "suffix",
    [
        "@@ -bad +2 @@\n-assert other == 2\n+assert other\n",
        "@@ -2 +2 @\n-assert other == 2\n+assert other\n",
        "-assert extra == 3\n",
        "+assert extra\n",
        "+++ b/another_file.py\n",
    ],
)
def test_parser_rejects_malformed_content_after_a_complete_hunk(suffix: str) -> None:
    patch = "--- a/test_x.py\n+++ b/test_x.py\n@@ -1 +1 @@\n-old\n+new\n"
    with pytest.raises(DiffError):
        parse_unified_diff(patch + suffix)


def test_parser_accepts_git_format_patch_signature() -> None:
    patch = "--- a/test_x.py\n+++ b/test_x.py\n@@ -1 +1 @@\n-old\n+new\n-- \n2.49.0\n"
    [change] = parse_unified_diff(patch)
    assert [line.content for line in change.added_lines] == ["new"]


@pytest.mark.parametrize("kind", ["rename", "copy"])
def test_parser_uses_exact_extended_paths_for_space_named_files(kind: str) -> None:
    patch = (
        "diff --git a/a/old name.py b/b/new name.py\n"
        "similarity index 100%\n"
        f"{kind} from a/old name.py\n"
        f"{kind} to b/new name.py\n"
    )
    [change] = parse_unified_diff(patch)
    assert change.old_path == "a/old name.py"
    assert change.new_path == "b/new name.py"
    assert change.lines == []


def test_parser_keeps_space_named_rename_separate_from_previous_file() -> None:
    patch = (
        "diff --git a/test_x.py b/test_x.py\n"
        "--- a/test_x.py\n+++ b/test_x.py\n@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/old name.py b/new name.py\n"
        "similarity index 100%\nrename from old name.py\nrename to new name.py\n"
    )
    changes = parse_unified_diff(patch)
    assert [(change.old_path, change.new_path) for change in changes] == [
        ("test_x.py", "test_x.py"),
        ("old name.py", "new name.py"),
    ]


def test_real_git_staged_rename_with_spaces_hydrates_both_sources(
    tmp_path: Path,
) -> None:
    def git(*arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    old = tmp_path / "test_old name.py"
    new = tmp_path / "test_new name.py"
    source = "def test_value():\n    assert value == 1\n"
    old.write_text(source, encoding="utf-8")
    git("add", "--", old.name)
    git(
        "-c",
        "user.name=TestSeal test",
        "-c",
        "user.email=testseal@example.invalid",
        "commit",
        "--no-gpg-sign",
        "--no-verify",
        "-m",
        "initial test",
    )
    old.rename(new)
    git("add", "-A")

    [change] = GitRepository(tmp_path).staged_changes()
    assert (change.old_path, change.new_path) == (old.name, new.name)
    assert change.old_source == change.new_source == source


@pytest.mark.skipif(os.name != "nt", reason="Windows executable lookup")
def test_windows_git_lookup_works_without_pathext_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_which = diff_module.shutil.which

    def which_without_pathext(command: str) -> str | None:
        # Python 3.11 does not expand PATHEXT for path-containing commands.
        if not command.lower().endswith(".exe"):
            return None
        return original_which(command)

    monkeypatch.setattr(diff_module.shutil, "which", which_without_pathext)
    assert Path(GitRepository._find_git()).is_file()
