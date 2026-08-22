"""Configuration loading and path/rule policy."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from .models import Severity


class ConfigError(ValueError):
    """Raised for a malformed or unreadable TestSeal configuration."""


DEFAULT_INCLUDE = (
    "*.py",
    "**/*.py",
    "*.snap",
    "**/*.snap",
    "*.snapshot",
    "**/*.snapshot",
)
DEFAULT_EXCLUDE = (
    ".git/**",
    ".venv/**",
    "venv/**",
    "node_modules/**",
    "build/**",
    "dist/**",
)
DEFAULT_TEST_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "tests/**/*.py",
    "test/**/*.py",
    "**/tests/**/*.py",
)
KNOWN_RULE_IDS = frozenset(f"TS{number:03d}" for number in range(1, 9))
_CONFIG_KEYS = frozenset(
    {
        "fail_on",
        "include",
        "exclude",
        "test_patterns",
        "source_roots",
        "guarding_tests",
        "disabled_rules",
        "ignore_fingerprints",
        "rules",
    }
)
_RULE_KEYS = frozenset({"enabled", "severity"})


@dataclass(frozen=True, slots=True)
class RuleConfig:
    enabled: bool = True
    severity: Severity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ConfigError("rules.enabled must be a boolean")
        if self.severity is not None and not isinstance(self.severity, Severity):
            raise ConfigError("rules.severity must be a Severity or None")


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved configuration with conservative, zero-config defaults."""

    fail_on: Severity | None = None
    include: tuple[str, ...] = DEFAULT_INCLUDE
    exclude: tuple[str, ...] = DEFAULT_EXCLUDE
    test_patterns: tuple[str, ...] = DEFAULT_TEST_PATTERNS
    source_roots: tuple[str, ...] = ("src", "lib", "app")
    guarding_tests: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    disabled_rules: frozenset[str] = frozenset()
    ignore_fingerprints: frozenset[str] = frozenset()
    rules: Mapping[str, RuleConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fail_on is not None and not isinstance(self.fail_on, Severity):
            raise ConfigError("fail_on must be a Severity or None")
        for name in ("include", "exclude", "test_patterns", "source_roots"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(
                isinstance(item, str) for item in value
            ):
                raise ConfigError(f"{name} must be a tuple of strings")
        if not isinstance(self.guarding_tests, Mapping):
            raise ConfigError("guarding_tests must be a mapping")
        for source_pattern, test_patterns in self.guarding_tests.items():
            if (
                not isinstance(source_pattern, str)
                or not isinstance(test_patterns, tuple)
                or not all(isinstance(item, str) for item in test_patterns)
            ):
                raise ConfigError(
                    f"guarding_tests.{source_pattern} must be a tuple of strings"
                )
        if not isinstance(self.disabled_rules, frozenset):
            raise ConfigError("disabled_rules must be a frozenset of rule IDs")
        invalid_disabled = [
            item
            for item in self.disabled_rules
            if not isinstance(item, str) or item not in KNOWN_RULE_IDS
        ]
        if invalid_disabled:
            raise ConfigError(
                f"unknown rule id in disabled_rules: {invalid_disabled[0]!r}"
            )
        if not isinstance(self.ignore_fingerprints, frozenset):
            raise ConfigError("ignore_fingerprints must be a frozenset")
        invalid_fingerprints = [
            item
            for item in self.ignore_fingerprints
            if not isinstance(item, str)
            or re.fullmatch(r"[0-9a-fA-F]{24}", item) is None
        ]
        if invalid_fingerprints:
            raise ConfigError(
                "ignore_fingerprints entries must be exactly 24 hexadecimal characters"
            )
        object.__setattr__(
            self,
            "ignore_fingerprints",
            frozenset(item.lower() for item in self.ignore_fingerprints),
        )
        if not isinstance(self.rules, Mapping):
            raise ConfigError("rules must be a mapping")
        for rule_id, override in self.rules.items():
            if rule_id not in KNOWN_RULE_IDS:
                raise ConfigError(f"unknown rule id in rules: {rule_id!r}")
            if not isinstance(override, RuleConfig):
                raise ConfigError(f"rules.{rule_id} must be a RuleConfig")

    def includes_path(self, path: str) -> bool:
        return matches_path(path, self.include) and not matches_path(path, self.exclude)

    def is_test_path(self, path: str) -> bool:
        return matches_path(path, self.test_patterns)

    def rule_enabled(self, rule_id: str) -> bool:
        if rule_id in self.disabled_rules:
            return False
        override = self.rules.get(rule_id)
        return override.enabled if override else True

    def severity_for(self, rule_id: str, default: Severity) -> Severity:
        override = self.rules.get(rule_id)
        return override.severity if override and override.severity else default

    def with_fail_on(self, value: str | None) -> Config:
        if value is None:
            return self
        return replace(self, fail_on=_parse_fail_on(value))


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    candidate = PurePosixPath(path)
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        variants = {normalized}
        # Relative policy patterns apply at any directory depth, matching the
        # behavior users expect from ignore files and pathlib.Path.match().
        if normalized and not normalized.startswith(("/", "**/")):
            variants.add(f"**/{normalized}")
        pending = list(variants)
        # ``pathlib`` treats ``**/`` as one-or-more directories. Configuration
        # globs follow the more familiar Git/pre-commit convention where it
        # also matches zero directories (for example tests/**/*.py matches
        # tests/conftest.py).
        while pending:
            variant = pending.pop()
            start = 0
            while (index := variant.find("**/", start)) != -1:
                collapsed = variant[:index] + variant[index + 3 :]
                if collapsed not in variants:
                    variants.add(collapsed)
                    pending.append(collapsed)
                start = index + 3
        if any(
            variant and (candidate.match(variant) or fnmatchcase(path, variant))
            for variant in variants
        ):
            return True
    return False


def matches_path(path: str, patterns: tuple[str, ...]) -> bool:
    """Match a repository path using TestSeal's shared glob semantics."""

    return _matches_any(_normalize_path(path), patterns)


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _parse_fail_on(value: object) -> Severity | None:
    if not isinstance(value, str):
        raise ConfigError("fail_on must be a string")
    if value.lower() == "never":
        return None
    try:
        return Severity.parse(value)
    except ValueError as exc:
        raise ConfigError(f"invalid fail_on value: {value!r}") from exc


def _string_tuple(
    data: Mapping[str, Any], key: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    value = data.get(key, default)
    if not isinstance(value, list | tuple) or not all(
        isinstance(item, str) for item in value
    ):
        raise ConfigError(f"{key} must be an array of strings")
    return tuple(value)


def config_from_mapping(data: Mapping[str, Any]) -> Config:
    """Validate a mapping from TOML and return an immutable configuration."""

    if not isinstance(data, Mapping):
        raise ConfigError("configuration must be a table")
    unknown_keys = [key for key in data if key not in _CONFIG_KEYS]
    if unknown_keys:
        raise ConfigError(f"unknown configuration key: {unknown_keys[0]!r}")

    fail_on = _parse_fail_on(data.get("fail_on", "never"))
    disabled = _string_tuple(data, "disabled_rules", ())
    invalid_ids = [item for item in disabled if item not in KNOWN_RULE_IDS]
    if invalid_ids:
        raise ConfigError(f"unknown rule id in disabled_rules: {invalid_ids[0]!r}")

    raw_fingerprints = _string_tuple(data, "ignore_fingerprints", ())
    invalid_fingerprints = [
        item
        for item in raw_fingerprints
        if re.fullmatch(r"[0-9a-fA-F]{24}", item) is None
    ]
    if invalid_fingerprints:
        raise ConfigError(
            "ignore_fingerprints entries must be exactly 24 hexadecimal characters; "
            f"got {invalid_fingerprints[0]!r}"
        )

    raw_guards = data.get("guarding_tests", {})
    if not isinstance(raw_guards, Mapping):
        raise ConfigError(
            "guarding_tests must be a table of source globs to test globs"
        )
    guards: dict[str, tuple[str, ...]] = {}
    for source_pattern, test_patterns in raw_guards.items():
        if isinstance(test_patterns, str):
            guards[str(source_pattern)] = (test_patterns,)
        elif isinstance(test_patterns, list) and all(
            isinstance(item, str) for item in test_patterns
        ):
            guards[str(source_pattern)] = tuple(test_patterns)
        else:
            raise ConfigError(
                f"guarding_tests.{source_pattern} must be a string or array of strings"
            )

    raw_rules = data.get("rules", {})
    if not isinstance(raw_rules, Mapping):
        raise ConfigError("rules must be a table")
    rules: dict[str, RuleConfig] = {}
    for rule_id, raw in raw_rules.items():
        if rule_id not in KNOWN_RULE_IDS:
            raise ConfigError(f"unknown rule id in rules: {rule_id!r}")
        if not isinstance(raw, Mapping):
            raise ConfigError(f"rules.{rule_id} must be a table")
        unknown_rule_keys = [key for key in raw if key not in _RULE_KEYS]
        if unknown_rule_keys:
            raise ConfigError(
                f"unknown key in rules.{rule_id}: {unknown_rule_keys[0]!r}"
            )
        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"rules.{rule_id}.enabled must be a boolean")
        severity = raw.get("severity")
        try:
            parsed_severity = Severity.parse(severity) if severity is not None else None
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"invalid severity for rules.{rule_id}") from exc
        rules[rule_id] = RuleConfig(enabled=enabled, severity=parsed_severity)

    return Config(
        fail_on=fail_on,
        include=_string_tuple(data, "include", DEFAULT_INCLUDE),
        exclude=_string_tuple(data, "exclude", DEFAULT_EXCLUDE),
        test_patterns=_string_tuple(data, "test_patterns", DEFAULT_TEST_PATTERNS),
        source_roots=_string_tuple(data, "source_roots", ("src", "lib", "app")),
        guarding_tests=guards,
        disabled_rules=frozenset(disabled),
        ignore_fingerprints=frozenset(
            fingerprint.lower() for fingerprint in raw_fingerprints
        ),
        rules=rules,
    )


def load_config(path: str | Path | None = None, *, cwd: str | Path = ".") -> Config:
    """Load explicit TOML or discover project configuration in ``cwd``.

    Explicit files may place keys at the top level or below ``[tool.testseal]``.
    ``testseal.toml`` takes precedence over ``pyproject.toml``. An auto-discovered
    pyproject without a TestSeal table is treated as defaults.
    """

    explicit = path is not None
    if explicit:
        config_path = Path(path)
    else:
        config_root = Path(cwd)
        standalone_path = config_root / "testseal.toml"
        config_path = (
            standalone_path
            if standalone_path.exists()
            else config_root / "pyproject.toml"
        )
    if not config_path.exists():
        if explicit:
            raise ConfigError(f"configuration file not found: {config_path}")
        return Config()
    try:
        with config_path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc

    tool = document.get("tool")
    nested = tool.get("testseal") if isinstance(tool, Mapping) else None
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise ConfigError("[tool.testseal] must be a table")
        return config_from_mapping(nested)
    standalone = document.get("testseal")
    if standalone is not None:
        if not isinstance(standalone, Mapping):
            raise ConfigError("[testseal] must be a table")
        return config_from_mapping(standalone)
    if explicit:
        return config_from_mapping(document)
    return Config()
