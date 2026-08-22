"""Unified-diff parsing and Git-backed source hydration."""

from __future__ import annotations

import difflib
import io
import re
import subprocess
import tokenize
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path


class DiffError(RuntimeError):
    """Raised when a diff cannot be obtained or interpreted."""


def _decode_source(data: bytes, path: str) -> str:
    """Decode a Git/worktree blob without ignoring valid Python encodings."""

    if not path.lower().endswith(".py"):
        text = data.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        text = data.decode(encoding)
        return text.replace("\r\n", "\n").replace("\r", "\n")
    except (LookupError, SyntaxError, UnicodeDecodeError) as exc:
        raise DiffError(f"cannot decode Python source {path!r}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class DiffLine:
    kind: str
    content: str
    old_line: int | None
    new_line: int | None


@dataclass(slots=True)
class ChangedFile:
    old_path: str | None
    new_path: str | None
    lines: list[DiffLine] = field(default_factory=list)
    old_source: str | None = None
    new_source: str | None = None

    @property
    def path(self) -> str:
        return (self.new_path or self.old_path or "<unknown>").replace("\\", "/")

    @property
    def is_deleted(self) -> bool:
        return self.new_path is None

    @property
    def is_added(self) -> bool:
        return self.old_path is None

    @property
    def added_lines(self) -> list[DiffLine]:
        return [line for line in self.lines if line.kind == "+"]

    @property
    def deleted_lines(self) -> list[DiffLine]:
        return [line for line in self.lines if line.kind == "-"]

    def new_line_for_old(self, old_line: int) -> int:
        """Map a removed line to the closest actionable line in the new file."""

        previous_new = 1
        for index, line in enumerate(self.lines):
            if line.new_line is not None:
                previous_new = line.new_line
            if line.old_line == old_line:
                if line.new_line is not None:
                    return line.new_line
                following = next(
                    (
                        candidate.new_line
                        for candidate in self.lines[index + 1 :]
                        if candidate.new_line is not None
                    ),
                    None,
                )
                return following or previous_new
            if line.old_line is not None and line.old_line > old_line:
                return previous_new
        return previous_new

    def is_old_line_changed(self, line_number: int) -> bool:
        return any(
            item.kind == "-" and item.old_line == line_number for item in self.lines
        )

    def is_new_line_changed(self, line_number: int) -> bool:
        return any(
            item.kind == "+" and item.new_line == line_number for item in self.lines
        )


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")

_C_ESCAPES = {
    "a": 0x07,
    "b": 0x08,
    "t": 0x09,
    "n": 0x0A,
    "v": 0x0B,
    "f": 0x0C,
    "r": 0x0D,
    '"': 0x22,
    "\\": 0x5C,
}


def _quoted_token(value: str) -> tuple[str, str] | None:
    """Return one Git C-quoted token and the unconsumed suffix."""

    if not value.startswith('"'):
        return None
    escaped = False
    for index, character in enumerate(value[1:], start=1):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            return value[: index + 1], value[index + 1 :]
    return None


def _decode_git_path(value: str) -> str:
    """Decode Git's C-style path quoting, including UTF-8 octal bytes."""

    if not (value.startswith('"') and value.endswith('"')):
        return value

    source = value[1:-1]
    decoded = bytearray()
    index = 0
    while index < len(source):
        character = source[index]
        if character != "\\":
            decoded.extend(character.encode("utf-8"))
            index += 1
            continue

        index += 1
        if index >= len(source):
            decoded.append(ord("\\"))
            break
        escape = source[index]
        if escape in _C_ESCAPES:
            decoded.append(_C_ESCAPES[escape])
            index += 1
            continue
        if escape in "01234567":
            end = index + 1
            while end < min(index + 3, len(source)) and source[end] in "01234567":
                end += 1
            decoded.append(int(source[index:end], 8))
            index = end
            continue

        # Be lossless for an escape Git itself does not currently emit.
        decoded.append(ord("\\"))
        decoded.extend(escape.encode("utf-8"))
        index += 1
    return decoded.decode("utf-8", errors="replace")


def _clean_header_path(value: str) -> str | None:
    value = value.strip()
    if value.startswith('"'):
        quoted = _quoted_token(value)
        if quoted is not None:
            value = quoted[0]
    else:
        # Ordinary unified diffs may append a timestamp after a tab.
        value = value.split("\t", 1)[0]
    value = _decode_git_path(value)
    if value == "/dev/null":
        return None
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value


def _git_header_paths(raw: str) -> tuple[str | None, str | None] | None:
    prefix = "diff --git "
    if not raw.startswith(prefix):
        return None
    remainder = raw[len(prefix) :].lstrip()
    tokens: list[str] = []
    for _ in range(2):
        if not remainder:
            return None
        if remainder.startswith('"'):
            quoted = _quoted_token(remainder)
            if quoted is None:
                return None
            token, remainder = quoted
        else:
            token, separator, remainder = remainder.partition(" ")
            if not separator and len(tokens) == 0:
                return None
        tokens.append(token)
        remainder = remainder.lstrip()
    if remainder:
        return None
    return _clean_header_path(tokens[0]), _clean_header_path(tokens[1])


def parse_unified_diff(text: str) -> list[ChangedFile]:
    """Parse Git or ordinary unified-diff text without third-party packages."""

    files: list[ChangedFile] = []
    current: ChangedFile | None = None
    old_line: int | None = None
    new_line: int | None = None
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_old_header = False
    saw_new_header = False
    current_has_content = False

    def incomplete_hunk_message() -> str:
        path = current.path if current is not None else "<unknown>"
        return (
            f"incomplete hunk for {path!r}: expected {old_remaining} more old "
            f"line(s) and {new_remaining} more new line(s)"
        )

    def incomplete_file_message() -> str:
        path = current.path if current is not None else "<unknown>"
        return f"incomplete file diff for {path!r}: no change content"

    for raw in text.splitlines():
        if in_hunk and current is not None:
            if raw.startswith("\\ No newline at end of file"):
                continue
            if raw.startswith("+"):
                if new_remaining <= 0:
                    raise DiffError(
                        f"malformed hunk for {current.path!r}: extra new line"
                    )
                current.lines.append(DiffLine("+", raw[1:], None, new_line))
                assert new_line is not None
                new_line += 1
                new_remaining -= 1
            elif raw.startswith("-"):
                if old_remaining <= 0:
                    raise DiffError(
                        f"malformed hunk for {current.path!r}: extra old line"
                    )
                current.lines.append(DiffLine("-", raw[1:], old_line, None))
                assert old_line is not None
                old_line += 1
                old_remaining -= 1
            elif raw.startswith(" ") or raw == "":
                if old_remaining <= 0 or new_remaining <= 0:
                    raise DiffError(
                        f"malformed hunk for {current.path!r}: extra context line"
                    )
                content = raw[1:] if raw.startswith(" ") else ""
                current.lines.append(DiffLine(" ", content, old_line, new_line))
                assert old_line is not None and new_line is not None
                old_line += 1
                new_line += 1
                old_remaining -= 1
                new_remaining -= 1
            else:
                raise DiffError(incomplete_hunk_message())
            if old_remaining <= 0 and new_remaining <= 0:
                in_hunk = False
            continue

        header = _git_header_paths(raw)
        if header is not None:
            if current is not None and not current_has_content:
                raise DiffError(incomplete_file_message())
            current = ChangedFile(*header)
            files.append(current)
            saw_old_header = False
            saw_new_header = False
            current_has_content = False
            continue

        if current is not None and raw.startswith("new file mode "):
            current.old_path = None
            current_has_content = True
            continue

        if current is not None and raw.startswith("deleted file mode "):
            current.new_path = None
            current_has_content = True
            continue

        if current is not None and raw.startswith(
            (
                "old mode ",
                "new mode ",
                "rename from ",
                "rename to ",
                "copy from ",
                "copy to ",
                "Binary files ",
                "GIT binary patch",
                "Submodule ",
            )
        ):
            current_has_content = True
            continue

        if raw.startswith("--- "):
            path = _clean_header_path(raw[4:])
            if current is None or saw_old_header:
                if current is not None and not current_has_content:
                    raise DiffError(incomplete_file_message())
                current = ChangedFile(path, None)
                files.append(current)
                saw_new_header = False
                current_has_content = False
            else:
                current.old_path = path
            saw_old_header = True
            continue
        if raw.startswith("+++ "):
            path = _clean_header_path(raw[4:])
            if current is None:
                current = ChangedFile(None, path)
                files.append(current)
            else:
                current.new_path = path
            saw_new_header = True
            in_hunk = False
            continue

        hunk = _HUNK.match(raw)
        if hunk:
            if current is None:
                raise DiffError("encountered a hunk before a file header")
            if not saw_old_header or not saw_new_header:
                raise DiffError(incomplete_file_message())
            current_has_content = True
            old_line = int(hunk.group(1))
            new_line = int(hunk.group(3))
            old_remaining = int(hunk.group(2) or "1")
            new_remaining = int(hunk.group(4) or "1")
            in_hunk = old_remaining > 0 or new_remaining > 0
            continue

    if in_hunk:
        raise DiffError(incomplete_hunk_message())
    if current is not None and not current_has_content:
        raise DiffError(incomplete_file_message())
    changes = [item for item in files if item.old_path or item.new_path]
    if text.strip() and not changes:
        raise DiffError("input does not contain a unified diff")
    return changes


def make_unified_diff(path: str, old_source: str, new_source: str) -> str:
    """Build a Git-shaped unified diff, primarily for API consumers and tests."""

    old_lines = old_source.splitlines()
    new_lines = new_source.splitlines()
    body = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "\n".join(body)


def changes_from_sources(path: str, old_source: str, new_source: str) -> ChangedFile:
    parsed = parse_unified_diff(make_unified_diff(path, old_source, new_source))
    if parsed:
        change = parsed[0]
    else:
        change = ChangedFile(path, path)
    change.old_source = old_source
    change.new_source = new_source
    return change


class GitRepository:
    """Read diffs and corresponding blobs from one Git work tree."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        discovered = self._run("rev-parse", "--show-toplevel").strip()
        if not discovered:
            raise DiffError(f"not a Git repository: {self.root}")
        self.root = Path(discovered)

    def _run(self, *args: str) -> str:
        try:
            process = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise DiffError(f"cannot execute Git: {exc}") from exc
        if process.returncode:
            detail = process.stderr.decode("utf-8", errors="replace").strip()
            raise DiffError(
                f"git {' '.join(args)} failed: {detail or process.returncode}"
            )
        return process.stdout.decode("utf-8", errors="replace")

    @staticmethod
    def _path_args(paths: Sequence[str]) -> tuple[str, ...]:
        return ("--", *paths) if paths else ()

    @staticmethod
    def _revision(value: str, *, label: str) -> str:
        if (
            not value
            or value.startswith("-")
            or any(character in value for character in ("\x00", "\r", "\n"))
        ):
            raise DiffError(f"invalid {label} revision: {value!r}")
        return value

    def _blob(self, revision: str, path: str | None) -> str | None:
        if path is None:
            return None
        try:
            process = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "show",
                    f":{path}" if revision == ":" else f"{revision}:{path}",
                ],
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise DiffError(f"cannot execute Git: {exc}") from exc
        if process.returncode:
            detail = process.stderr.decode("utf-8", errors="replace").strip()
            object_name = f":{path}" if revision == ":" else f"{revision}:{path}"
            raise DiffError(
                f"cannot read Git blob {object_name!r}: {detail or process.returncode}"
            )
        return _decode_source(process.stdout, path)

    def _worktree_file(self, path: str | None) -> str | None:
        if path is None:
            return None
        candidate = (self.root / path).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError:
            raise DiffError(
                f"refusing to read path outside repository: {path!r}"
            ) from None
        try:
            data = candidate.read_bytes()
        except OSError as exc:
            raise DiffError(f"cannot read worktree file {path!r}: {exc}") from exc
        return _decode_source(data, path)

    def working_changes(
        self, *, head: str = "HEAD", paths: Sequence[str] = ()
    ) -> list[ChangedFile]:
        head = self._revision(head, label="head")
        patch = self._run(
            "diff", "--no-ext-diff", "--unified=3", head, *self._path_args(paths)
        )
        files = parse_unified_diff(patch)
        for item in files:
            item.old_source = self._blob(head, item.old_path)
            item.new_source = self._worktree_file(item.new_path)
        untracked = self._run(
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            *self._path_args(paths),
        )
        for raw_path in untracked.split("\0"):
            if not raw_path:
                continue
            path = raw_path.replace("\\", "/")
            new_source = self._worktree_file(path)
            if new_source is None:
                raise DiffError(f"cannot hydrate untracked file {path!r}")
            lines = [
                DiffLine("+", content, None, line_number)
                for line_number, content in enumerate(new_source.splitlines(), start=1)
            ]
            files.append(
                ChangedFile(
                    old_path=None,
                    new_path=path,
                    lines=lines,
                    old_source=None,
                    new_source=new_source,
                )
            )
        return files

    def staged_changes(self, *, paths: Sequence[str] = ()) -> list[ChangedFile]:
        patch = self._run(
            "diff", "--cached", "--no-ext-diff", "--unified=3", *self._path_args(paths)
        )
        files = parse_unified_diff(patch)
        for item in files:
            item.old_source = self._blob("HEAD", item.old_path)
            item.new_source = self._blob(":", item.new_path)
        return files

    def revision_changes(
        self, base: str, head: str = "HEAD", *, paths: Sequence[str] = ()
    ) -> list[ChangedFile]:
        base = self._revision(base, label="base")
        head = self._revision(head, label="head")
        merge_base = self._run("merge-base", base, head).strip()
        if not merge_base:
            raise DiffError(f"no merge base between {base!r} and {head!r}")
        patch = self._run(
            "diff",
            "--no-ext-diff",
            "--unified=3",
            merge_base,
            head,
            *self._path_args(paths),
        )
        files = parse_unified_diff(patch)
        for item in files:
            item.old_source = self._blob(merge_base, item.old_path)
            item.new_source = self._blob(head, item.new_path)
        return files


def filter_changes(
    files: Iterable[ChangedFile], paths: Sequence[str]
) -> list[ChangedFile]:
    """Apply CLI path prefixes to externally supplied diffs."""

    if not paths:
        return list(files)
    prefixes = tuple(item.replace("\\", "/").rstrip("/") for item in paths)
    return [
        file
        for file in files
        if any(
            file.path == prefix or file.path.startswith(prefix + "/")
            for prefix in prefixes
        )
    ]
