from __future__ import annotations

import pytest
from testseal.diff import (
    DiffError,
    changes_from_sources,
    make_unified_diff,
    parse_unified_diff,
)


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
