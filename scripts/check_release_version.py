"""Fail when a release tag and package versions disagree."""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEMVER_PATTERN = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
TAG_PATTERN = re.compile(rf"^v(?P<version>{SEMVER_PATTERN})$")
MODULE_VERSION_PATTERN = re.compile(
    r'^__version__\s*=\s*"(?P<version>[^"]+)"$', re.MULTILINE
)
CITATION_VERSION_PATTERN = re.compile(
    rf'^version: "(?P<version>{SEMVER_PATTERN})"$', re.MULTILINE
)


class ReleaseValidationError(ValueError):
    """Raised when release metadata cannot be validated safely."""


def _validate_ci_context() -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return
    if os.environ.get("RELEASE_REF_TYPE") != "tag":
        raise ReleaseValidationError("release workflow must run from a tag ref")
    if os.environ.get("RELEASE_REF_PROTECTED", "").lower() != "true":
        raise ReleaseValidationError(
            "release tag is not protected by a GitHub ruleset or tag protection rule"
        )


def _read_python_versions() -> tuple[str, str]:
    path = ROOT / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            document: dict[str, Any] = tomllib.load(handle)
        package_version = document["project"]["version"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ReleaseValidationError(
            f"cannot read Python package version: {exc}"
        ) from exc
    if not isinstance(package_version, str) or not package_version:
        raise ReleaseValidationError(
            "Python package version must be a non-empty string"
        )

    module_path = ROOT / "packages/testseal/src/testseal/__init__.py"
    try:
        module_source = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseValidationError(
            f"cannot read Python module version: {exc}"
        ) from exc
    match = MODULE_VERSION_PATTERN.search(module_source)
    if match is None:
        raise ReleaseValidationError(
            "Python module has no literal __version__ assignment"
        )
    return package_version, match.group("version")


def _read_node_versions(directory: str, label: str) -> tuple[str, str]:
    package_path = ROOT / directory / "package.json"
    lock_path = ROOT / directory / "package-lock.json"
    try:
        with package_path.open(encoding="utf-8") as handle:
            package = json.load(handle)
        with lock_path.open(encoding="utf-8") as handle:
            lock = json.load(handle)
        package_version = package["version"]
        lock_version = lock["version"]
        lock_root_version = lock["packages"][""]["version"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReleaseValidationError(
            f"cannot read {label} package versions: {exc}"
        ) from exc
    if not isinstance(package_version, str) or not package_version:
        raise ReleaseValidationError(
            f"{label} package version must be a non-empty string"
        )
    if (
        not isinstance(lock_version, str)
        or not isinstance(lock_root_version, str)
        or lock_version != lock_root_version
    ):
        raise ReleaseValidationError(
            f"{label} package-lock top-level and root package versions must agree"
        )
    return package_version, lock_version


def _read_citation_version() -> str:
    try:
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseValidationError(f"cannot read CITATION.cff: {exc}") from exc

    citation_match = CITATION_VERSION_PATTERN.search(citation)
    if citation_match is None:
        raise ReleaseValidationError("CITATION.cff has no literal release version")
    return citation_match.group("version")


def _has_release_heading(version: str) -> bool:
    try:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseValidationError(f"cannot read CHANGELOG.md: {exc}") from exc
    heading = re.compile(
        rf"^## \[{re.escape(version)}\] - "
        r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$",
        re.MULTILINE,
    )
    match = heading.search(changelog)
    if match is None:
        return False
    try:
        date.fromisoformat(match.group("date"))
    except ValueError as exc:
        raise ReleaseValidationError(
            f"CHANGELOG.md release date is invalid: {match.group('date')}"
        ) from exc
    return True


def main() -> int:
    try:
        _validate_ci_context()
    except ReleaseValidationError as exc:
        print(f"Release context is invalid: {exc}", file=sys.stderr)
        return 2

    tag = os.environ.get("RELEASE_TAG", "")
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        print(
            "RELEASE_TAG must use canonical vMAJOR.MINOR.PATCH syntax "
            "without leading zeroes",
            file=sys.stderr,
        )
        return 2

    expected = match.group("version")
    try:
        python_version, python_module_version = _read_python_versions()
        action_version, action_lock_version = _read_node_versions(
            "packages/action", "Action"
        )
        site_version, site_lock_version = _read_node_versions("site", "Website")
        citation_version = _read_citation_version()
        has_release_heading = _has_release_heading(expected)
    except ReleaseValidationError as exc:
        print(f"Release metadata is invalid: {exc}", file=sys.stderr)
        return 2

    mismatches: list[str] = []
    if python_version != expected:
        mismatches.append(f"Python package is {python_version}")
    if python_module_version != expected:
        mismatches.append(f"Python module is {python_module_version}")
    if action_version != expected:
        mismatches.append(f"Action package is {action_version}")
    if action_lock_version != expected:
        mismatches.append(f"Action package lock is {action_lock_version}")
    if site_version != expected:
        mismatches.append(f"Website package is {site_version}")
    if site_lock_version != expected:
        mismatches.append(f"Website package lock is {site_lock_version}")
    if citation_version != expected:
        mismatches.append(f"CITATION.cff is {citation_version}")
    if not has_release_heading:
        mismatches.append(
            f"CHANGELOG.md has no '## [{expected}] - YYYY-MM-DD' release heading"
        )
    if mismatches:
        print(
            f"Release tag {tag} does not match: " + "; ".join(mismatches),
            file=sys.stderr,
        )
        return 1

    print(f"Release versions agree on {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
