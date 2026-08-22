"""Deterministic AST and diff rules for test-integrity changes."""

from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import partial

from .config import Config, matches_path
from .diff import ChangedFile, DiffLine
from .models import Confidence, Finding, Severity


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    rule_id: str
    title: str
    severity: Severity
    confidence: Confidence
    remediation: str


RULES: dict[str, RuleMetadata] = {
    "TS001": RuleMetadata(
        "TS001",
        "Assertion removed",
        Severity.HIGH,
        Confidence.HIGH,
        "Restore the assertion or explain why the tested behavior is no longer required.",
    ),
    "TS002": RuleMetadata(
        "TS002",
        "Test disabled",
        Severity.HIGH,
        Confidence.HIGH,
        "Keep the test active, or document and narrowly scope a temporary skip.",
    ),
    "TS003": RuleMetadata(
        "TS003",
        "Assertion weakened",
        Severity.HIGH,
        Confidence.HIGH,
        "Assert the specific expected value, type, relationship, or exception.",
    ),
    "TS004": RuleMetadata(
        "TS004",
        "Numeric tolerance widened",
        Severity.HIGH,
        Confidence.HIGH,
        "Retain the tighter tolerance unless the precision contract intentionally changed.",
    ),
    "TS005": RuleMetadata(
        "TS005",
        "Broad exception swallowed",
        Severity.HIGH,
        Confidence.HIGH,
        "Catch the expected exception type and assert its behavior, or re-raise it.",
    ),
    "TS006": RuleMetadata(
        "TS006",
        "Snapshot regeneration enabled",
        Severity.LOW,
        Confidence.LOW,
        "Review snapshot changes independently and avoid blanket acceptance in test code.",
    ),
    "TS007": RuleMetadata(
        "TS007",
        "Subject under test mocked",
        Severity.MEDIUM,
        Confidence.MEDIUM,
        "Mock external boundaries, not the behavior named by the test itself.",
    ),
    "TS008": RuleMetadata(
        "TS008",
        "Source and guarding test co-edited",
        Severity.LOW,
        Confidence.LOW,
        "Confirm the test still enforces the pre-existing behavioral contract.",
    ),
}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _stable_dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _render(node: ast.AST) -> str:
    return ast.unparse(node)


def _literal_number(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub | ast.UAdd)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int | float)
    ):
        value = float(node.operand.value)
        return -value if isinstance(node.op, ast.USub) else value
    return None


def _is_obviously_true(node: ast.AST) -> bool:
    """Return true only for small, syntactically evident tautologies.

    This intentionally does not evaluate calls or names.  A rule that protects a
    test suite should not guess about runtime truthiness.
    """

    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return isinstance(node.operand, ast.Constant) and not bool(node.operand.value)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.Or):
            return any(_is_obviously_true(value) for value in node.values)
        return bool(node.values) and all(
            _is_obviously_true(value) for value in node.values
        )
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        left = _stable_dump(node.left)
        right = _stable_dump(node.comparators[0])
        if left == right and isinstance(
            node.ops[0], (ast.Eq, ast.Is, ast.LtE, ast.GtE)
        ):
            return True
        if isinstance(node.left, ast.Constant) and isinstance(
            node.comparators[0], ast.Constant
        ):
            try:
                return bool(ast.literal_eval(node))
            except (ValueError, TypeError):
                return False
    return False


def _is_validation_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = _call_name(node.func)
    tail = name.rsplit(".", 1)[-1]
    if name in {"pytest.fail", "self.fail"}:
        return True
    if tail in _ASSERT_METHOD_RANKS:
        return not _method_assertion_info(node, tail).tautology
    return _is_mock_assertion(tail)


def _handler_has_unconditional_validation(body: Sequence[ast.stmt]) -> bool:
    """Whether a handler unconditionally validates or re-raises at top level.

    Descending into an ``if`` here is unsafe: ``if debug: raise`` still swallows
    the exception whenever the condition is false.  Simple logging/assignment
    statements before a direct assertion or re-raise are harmless.
    """

    for statement in body:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Assert):
            return not _is_obviously_true(statement.test)
        if isinstance(statement, ast.Expr) and _is_validation_call(statement.value):
            return True
        if isinstance(
            statement,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.Match,
                ast.Return,
                ast.Break,
                ast.Continue,
            ),
        ):
            return False
    return False


def _scope_name(stack: Sequence[str]) -> str:
    return ".".join(stack) if stack else "<module>"


@dataclass(frozen=True, slots=True)
class AssertionRecord:
    scope: str
    fingerprint: str
    kind: str
    strength: int
    line: int
    column: int
    end_line: int
    evidence: str
    subject: str | None = None
    predicate: str = ""
    tautology: bool = False


def _assertion_pair_score(
    after: AssertionRecord,
    *,
    before: AssertionRecord,
    mapped_line: int,
) -> tuple[int, int, int, int]:
    return (
        int(bool(before.predicate) and before.predicate == after.predicate),
        int(before.subject is not None and before.subject == after.subject),
        int(before.kind == after.kind),
        -abs(mapped_line - after.line),
    )


def _plausible_assertion_replacement(
    before: AssertionRecord, after: AssertionRecord
) -> bool:
    """Whether two changed assertions can represent the same test obligation.

    Pairing every removed assertion with any newly added assertion lets an
    unrelated check hide a deleted contract while keeping the assertion count
    unchanged.  Keep pairing deliberately conservative: equivalent predicates,
    the same semantic subject, and obvious tautologies are the transformations
    the weakening rule can reason about deterministically.
    """

    return (
        (bool(before.predicate) and before.predicate == after.predicate)
        or (before.subject is not None and before.subject == after.subject)
        or after.tautology
    )


@dataclass(frozen=True, slots=True)
class SyntaxRecord:
    scope: str
    fingerprint: str
    kind: str
    line: int
    column: int
    end_line: int
    evidence: str
    semantic: str = ""
    placement: str = "body"


@dataclass(frozen=True, slots=True)
class ToleranceRecord:
    scope: str
    call: str
    parameter: str
    value: float
    line: int
    column: int
    evidence: str
    anchor: str = ""


@dataclass(slots=True)
class Inventory:
    assertions: list[AssertionRecord]
    skips: list[SyntaxRecord]
    catches: list[SyntaxRecord]
    tolerances: list[ToleranceRecord]
    mocks: list[SyntaxRecord]


_ASSERT_METHOD_RANKS: dict[str, int] = {
    "assertTrue": 2,
    "assertFalse": 2,
    "assertIsNotNone": 3,
    "assertIsNone": 3,
    "assertAlmostEqual": 3,
    "assertNotAlmostEqual": 3,
    "assertIn": 3,
    "assertNotIn": 3,
    "assertEqual": 4,
    "assertNotEqual": 4,
    "assertIs": 4,
    "assertIsNot": 4,
    "assertIsInstance": 4,
    "assertNotIsInstance": 4,
    "assertGreater": 4,
    "assertGreaterEqual": 4,
    "assertLess": 4,
    "assertLessEqual": 4,
    "assertRaises": 4,
    "assertRaisesRegex": 4,
    "assertWarns": 4,
    "assertWarnsRegex": 4,
    "assertLogs": 4,
    "assertNoLogs": 4,
    "assertRegex": 4,
    "assertNotRegex": 4,
    "assertCountEqual": 4,
    "assertSequenceEqual": 4,
    "assertListEqual": 4,
    "assertTupleEqual": 4,
    "assertSetEqual": 4,
    "assertDictEqual": 4,
    "assertMultiLineEqual": 4,
}
_SKIP_CALLS = {
    "pytest.importorskip",
    "pytest.skip",
    "pytest.xfail",
    "self.skipTest",
    "unittest.skip",
    "unittest.skipIf",
    "unittest.skipUnless",
    "unittest.expectedFailure",
}
_TOLERANCE_KEYS = {"rel", "abs", "rel_tol", "abs_tol", "rtol", "atol", "delta"}
_MOCK_CALL_SUFFIXES = (
    ".patch",
    ".patch.object",
    ".setattr",
)
_MOCK_ASSERTION_METHODS = {
    "assert_any_await",
    "assert_any_call",
    "assert_has_awaits",
    "assert_has_calls",
    "assert_not_awaited",
    "assert_not_called",
}


def _is_mock_assertion(tail: str) -> bool:
    return tail in _MOCK_ASSERTION_METHODS or tail.startswith(
        ("assert_called", "assert_awaited")
    )


@dataclass(frozen=True, slots=True)
class _AssertionInfo:
    kind: str
    strength: int
    subject: str | None
    predicate: str
    tautology: bool = False


_COMPARE_NAMES: dict[type[ast.cmpop], str] = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Is: "is",
    ast.IsNot: "isnot",
    ast.Lt: "lt",
    ast.LtE: "lte",
    ast.Gt: "gt",
    ast.GtE: "gte",
    ast.In: "in",
    ast.NotIn: "notin",
}
_NEGATED_COMPARE = {
    "eq": "ne",
    "ne": "eq",
    "is": "isnot",
    "isnot": "is",
    "lt": "gte",
    "lte": "gt",
    "gt": "lte",
    "gte": "lt",
    "in": "notin",
    "notin": "in",
}


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _primary_subject(left: ast.AST, right: ast.AST) -> str:
    candidate = (
        right
        if isinstance(left, ast.Constant) and not isinstance(right, ast.Constant)
        else left
    )
    return _stable_dump(candidate)


def _compare_info(left: ast.AST, operator: ast.cmpop, right: ast.AST) -> _AssertionInfo:
    operator_name = _COMPARE_NAMES.get(type(operator), type(operator).__name__.lower())
    subject = _primary_subject(left, right)
    left_key = _stable_dump(left)
    right_key = _stable_dump(right)
    if operator_name in {"eq", "ne", "is", "isnot"}:
        operands = sorted((left_key, right_key))
    else:
        operands = [left_key, right_key]

    category = operator_name
    if (_is_none(left) or _is_none(right)) and operator_name in {"ne", "isnot"}:
        category = "nonnull"
    elif (_is_none(left) or _is_none(right)) and operator_name in {"eq", "is"}:
        category = "none"
    strength = 3 if category in {"nonnull", "none", "in", "notin"} else 4
    return _AssertionInfo(
        kind=f"assert:{type(operator).__name__}",
        strength=strength,
        subject=subject,
        predicate=f"{category}|{'|'.join(operands)}",
        tautology=_is_obviously_true(
            ast.Compare(left=left, ops=[operator], comparators=[right])
        ),
    )


def _expression_info(node: ast.AST, *, negate: bool = False) -> _AssertionInfo:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _expression_info(node.operand, negate=not negate)
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        info = _compare_info(node.left, node.ops[0], node.comparators[0])
        if not negate:
            return info
        category, _, detail = info.predicate.partition("|")
        inverse = _NEGATED_COMPARE.get(category, f"not-{category}")
        return _AssertionInfo(
            kind=f"assert:not-{info.kind.removeprefix('assert:')}",
            strength=info.strength,
            subject=info.subject,
            predicate=f"{inverse}|{detail}",
            tautology=False,
        )
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        if name in {"isinstance", "issubclass"} and len(node.args) >= 2:
            category = f"not-{name}" if negate else name
            subject = _stable_dump(node.args[0])
            return _AssertionInfo(
                kind=f"assert:{category}",
                strength=4,
                subject=subject,
                predicate=f"{category}|{subject}|{_stable_dump(node.args[1])}",
            )
        if name == "bool" and len(node.args) == 1:
            return _expression_info(node.args[0], negate=negate)
        category = "falsy" if negate else "truthy"
        subject_node = (
            node.args[0] if name in {"len", "any", "all"} and node.args else node
        )
        subject = _stable_dump(subject_node)
        return _AssertionInfo(
            kind=f"assert:{category}",
            strength=2,
            subject=subject,
            predicate=f"{category}|{subject}",
        )

    category = "falsy" if negate else "truthy"
    subject = _stable_dump(node)
    tautology = _is_obviously_true(node) if not negate else False
    return _AssertionInfo(
        kind=f"assert:{category}",
        strength=2,
        subject=subject,
        predicate=f"{category}|{subject}",
        tautology=tautology,
    )


def _method_assertion_info(node: ast.Call, tail: str) -> _AssertionInfo:
    args = node.args
    if tail in {"assertTrue", "assertFalse"} and args:
        return _expression_info(args[0], negate=tail == "assertFalse")

    if _is_mock_assertion(tail):
        receiver = (
            _stable_dump(node.func.value)
            if isinstance(node.func, ast.Attribute)
            else _stable_dump(node.func)
        )
        semantic_args = "|".join(_stable_dump(argument) for argument in args)
        return _AssertionInfo(
            tail,
            4,
            receiver,
            f"{tail}|{receiver}|{semantic_args}",
        )

    comparison_methods: dict[str, type[ast.cmpop]] = {
        "assertEqual": ast.Eq,
        "assertNotEqual": ast.NotEq,
        "assertIs": ast.Is,
        "assertIsNot": ast.IsNot,
        "assertGreater": ast.Gt,
        "assertGreaterEqual": ast.GtE,
        "assertLess": ast.Lt,
        "assertLessEqual": ast.LtE,
        "assertIn": ast.In,
        "assertNotIn": ast.NotIn,
    }
    if tail in comparison_methods and len(args) >= 2:
        info = _compare_info(args[0], comparison_methods[tail](), args[1])
        return _AssertionInfo(
            tail, info.strength, info.subject, info.predicate, info.tautology
        )
    if tail in {"assertIsNone", "assertIsNotNone"} and args:
        operator: ast.cmpop = ast.Is() if tail == "assertIsNone" else ast.IsNot()
        info = _compare_info(args[0], operator, ast.Constant(value=None))
        return _AssertionInfo(
            tail, info.strength, info.subject, info.predicate, info.tautology
        )
    if tail in {"assertIsInstance", "assertNotIsInstance"} and len(args) >= 2:
        category = "isinstance" if tail == "assertIsInstance" else "not-isinstance"
        subject = _stable_dump(args[0])
        return _AssertionInfo(
            tail,
            4,
            subject,
            f"{category}|{subject}|{_stable_dump(args[1])}",
        )

    subject = _stable_dump(args[0]) if args else None
    semantic_args = "|".join(_stable_dump(argument) for argument in args)
    return _AssertionInfo(
        tail,
        _ASSERT_METHOD_RANKS.get(tail, 4),
        subject,
        f"{tail}|{semantic_args}",
    )


def _expected_exception_strength(node: ast.AST | None) -> int:
    """Rank expected exception breadth without importing target code."""

    if node is None:
        return 1
    if isinstance(node, ast.Tuple):
        strengths = [_expected_exception_strength(item) for item in node.elts]
        return min([3, *strengths]) if strengths else 1
    name = _call_name(node)
    if name in {"BaseException", "builtins.BaseException"}:
        return 1
    if name in {"Exception", "builtins.Exception"}:
        return 2
    return 4


def _pytest_context_assertion_info(node: ast.Call, name: str) -> _AssertionInfo:
    expected = node.args[0] if node.args else None
    match = next(
        (keyword.value for keyword in node.keywords if keyword.arg == "match"),
        None,
    )
    has_match = match is not None and not (
        isinstance(match, ast.Constant) and match.value is None
    )
    expected_rendered = _stable_dump(expected) if expected is not None else ""
    match_rendered = _stable_dump(match) if has_match and match is not None else ""
    return _AssertionInfo(
        name,
        _expected_exception_strength(expected) + int(has_match),
        name,
        f"{name}|{expected_rendered}|match={match_rendered}",
    )


def _tolerance_anchor(node: ast.Call, parameter: str) -> str:
    name = _call_name(node.func)
    arguments: list[str] = []
    for index, argument in enumerate(node.args):
        if (
            parameter == "places"
            and name.endswith(("assertAlmostEqual", "assertNotAlmostEqual"))
            and index == 2
        ):
            arguments.append("<tolerance>")
        else:
            arguments.append(_stable_dump(argument))
    keywords = [
        (
            f"{keyword.arg}="
            f"{'<tolerance>' if keyword.arg == parameter else _stable_dump(keyword.value)}"
        )
        for keyword in node.keywords
    ]
    return f"{name}|{'|'.join(arguments)}|{'|'.join(keywords)}"


def _mock_target(node: ast.Call) -> str | None:
    name = _call_name(node.func)
    if not (
        name
        in {
            "patch",
            "patch.object",
            "mock.patch",
            "mock.patch.object",
            "unittest.mock.patch",
            "unittest.mock.patch.object",
        }
        or name.endswith(_MOCK_CALL_SUFFIXES)
        or name in {"monkeypatch.setattr", "mocker.patch", "mocker.patch.object"}
    ):
        return None
    if not node.args:
        return None
    first = node.args[0]
    attribute: ast.AST | None = node.args[1] if len(node.args) > 1 else None
    if attribute is None:
        attribute = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg in {"attribute", "name"}
            ),
            None,
        )
    object_patch = name == "patch.object" or name.endswith(
        (".patch.object", ".setattr")
    )
    if (
        object_patch
        and isinstance(attribute, ast.Constant)
        and isinstance(attribute.value, str)
    ):
        base = (
            first.value
            if isinstance(first, ast.Constant) and isinstance(first.value, str)
            else _render(first)
        )
        return f"{base}.{attribute.value}"
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return _render(first)


def _name_tokens(value: str) -> set[str]:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    value = re.sub(r"^test_?", "", value.lower())
    return {
        token
        for token in re.split(r"[^a-z0-9]+", value)
        if len(token) > 2 and token not in {"test", "when", "with", "should"}
    }


def _neighboring_diff_context(change: ChangedFile, target: DiffLine) -> tuple[str, str]:
    """Return stable unchanged context around one changed diff line."""

    index = next(
        (position for position, line in enumerate(change.lines) if line is target),
        -1,
    )
    if index < 0:
        return "", ""
    before = next(
        (line.content for line in reversed(change.lines[:index]) if line.kind == " "),
        "",
    )
    after = next(
        (line.content for line in change.lines[index + 1 :] if line.kind == " "),
        "",
    )
    return before, after


class _InventoryVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.assertions: list[AssertionRecord] = []
        self.skips: list[SyntaxRecord] = []
        self.catches: list[SyntaxRecord] = []
        self.tolerances: list[ToleranceRecord] = []
        self.mocks: list[SyntaxRecord] = []
        self.pytest_aliases: set[str] = {"pytest"}
        self.pytest_mark_aliases: set[str] = set()
        self.pytest_call_aliases: dict[str, str] = {}
        self.pytest_assertion_aliases: dict[str, str] = {}
        self.contextlib_aliases: set[str] = {"contextlib"}
        self.suppress_aliases: set[str] = set()
        self._in_decorator = False

    @property
    def scope(self) -> str:
        return _scope_name(self.stack)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pytest":
                self.pytest_aliases.add(alias.asname or "pytest")
            elif alias.name == "contextlib":
                self.contextlib_aliases.add(alias.asname or "contextlib")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "contextlib":
            for alias in node.names:
                if alias.name == "suppress":
                    self.suppress_aliases.add(alias.asname or alias.name)
            return
        if node.module != "pytest":
            return
        for alias in node.names:
            local_name = alias.asname or alias.name
            if alias.name == "mark":
                self.pytest_mark_aliases.add(local_name)
            elif alias.name in {"importorskip", "skip", "xfail"}:
                self.pytest_call_aliases[local_name] = f"pytest.{alias.name}"
            elif alias.name in {"raises", "warns"}:
                self.pytest_assertion_aliases[local_name] = f"pytest.{alias.name}"

    def _canonical_pytest_assertion(self, name: str) -> str | None:
        if name in self.pytest_assertion_aliases:
            return self.pytest_assertion_aliases[name]
        for alias in self.pytest_aliases:
            for assertion in ("raises", "warns"):
                if name == f"{alias}.{assertion}":
                    return f"pytest.{assertion}"
        return None

    def _canonical_suppress(self, name: str) -> str | None:
        if name in self.suppress_aliases:
            return "contextlib.suppress"
        if any(name == f"{alias}.suppress" for alias in self.contextlib_aliases):
            return "contextlib.suppress"
        return None

    def _canonical_skip_name(self, name: str) -> str | None:
        if name in self.pytest_call_aliases:
            return self.pytest_call_aliases[name]
        for alias in self.pytest_aliases:
            if name in {
                f"{alias}.importorskip",
                f"{alias}.skip",
                f"{alias}.xfail",
            }:
                return f"pytest.{name.rsplit('.', 1)[-1]}"
            for marker in ("skip", "skipif", "xfail"):
                if name == f"{alias}.mark.{marker}":
                    return f"pytest.mark.{marker}"
        for alias in self.pytest_mark_aliases:
            for marker in ("skip", "skipif", "xfail"):
                if name == f"{alias}.{marker}":
                    return f"pytest.mark.{marker}"
        if name in _SKIP_CALLS or name == "self.skipTest":
            return name
        return None

    @staticmethod
    def _skip_semantic(node: ast.AST, name: str) -> str:
        if not isinstance(node, ast.Call):
            return name
        relevant: list[str] = []
        if name in {"pytest.mark.skipif", "unittest.skipIf", "unittest.skipUnless"}:
            if node.args:
                relevant.append(_stable_dump(node.args[0]))
            relevant.extend(
                f"{keyword.arg}={_stable_dump(keyword.value)}"
                for keyword in node.keywords
                if keyword.arg not in {"reason"}
            )
        elif name == "pytest.mark.xfail":
            relevant.extend(_stable_dump(argument) for argument in node.args)
            relevant.extend(
                f"{keyword.arg}={_stable_dump(keyword.value)}"
                for keyword in node.keywords
                if keyword.arg != "reason"
            )
        elif name == "pytest.mark.skip":
            relevant.extend(
                f"{keyword.arg}={_stable_dump(keyword.value)}"
                for keyword in node.keywords
                if keyword.arg != "reason"
            )
        elif name == "pytest.importorskip":
            relevant.extend(_stable_dump(argument) for argument in node.args)
            relevant.extend(
                f"{keyword.arg}={_stable_dump(keyword.value)}"
                for keyword in node.keywords
                if keyword.arg != "reason"
            )
        return f"{name}|{'|'.join(relevant)}"

    def _visit_scope(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self.stack.append(node.name)
        for decorator in node.decorator_list:
            self._in_decorator = True
            name = self._canonical_skip_name(_call_name(decorator))
            if name is not None:
                self._record_skip(decorator, name)
            self.visit(decorator)
            self._in_decorator = False
        for child in node.body:
            self.visit(child)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        info = _expression_info(node.test)
        self.assertions.append(
            AssertionRecord(
                self.scope,
                _stable_dump(node),
                info.kind,
                info.strength,
                node.lineno,
                node.col_offset + 1,
                getattr(node, "end_lineno", node.lineno),
                _render(node),
                info.subject,
                info.predicate,
                info.tautology,
            )
        )
        self.generic_visit(node)

    def _record_skip(self, node: ast.AST, name: str) -> None:
        key = (getattr(node, "lineno", 1), name)
        if any((record.line, record.kind) == key for record in self.skips):
            return
        self.skips.append(
            SyntaxRecord(
                self.scope,
                _stable_dump(node),
                name,
                getattr(node, "lineno", 1),
                getattr(node, "col_offset", 0) + 1,
                getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                _render(node),
                self._skip_semantic(node, name),
                "decorator" if self._in_decorator else "body",
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        tail = name.rsplit(".", 1)[-1]
        pytest_assertion = self._canonical_pytest_assertion(name)
        if tail in _ASSERT_METHOD_RANKS or _is_mock_assertion(tail):
            info = _method_assertion_info(node, tail)
            self.assertions.append(
                AssertionRecord(
                    self.scope,
                    _stable_dump(node),
                    info.kind,
                    info.strength,
                    node.lineno,
                    node.col_offset + 1,
                    getattr(node, "end_lineno", node.lineno),
                    _render(node),
                    info.subject,
                    info.predicate,
                    info.tautology,
                )
            )
        elif pytest_assertion is not None:
            info = _pytest_context_assertion_info(node, pytest_assertion)
            self.assertions.append(
                AssertionRecord(
                    self.scope,
                    _stable_dump(node),
                    info.kind,
                    info.strength,
                    node.lineno,
                    node.col_offset + 1,
                    getattr(node, "end_lineno", node.lineno),
                    _render(node),
                    info.subject,
                    info.predicate,
                )
            )

        skip_name = self._canonical_skip_name(name)
        if skip_name is not None:
            self._record_skip(node, skip_name)

        for keyword in node.keywords:
            if keyword.arg in _TOLERANCE_KEYS:
                value = _literal_number(keyword.value)
                if value is not None:
                    self.tolerances.append(
                        ToleranceRecord(
                            self.scope,
                            name,
                            keyword.arg,
                            value,
                            node.lineno,
                            node.col_offset + 1,
                            _render(node),
                            _tolerance_anchor(node, keyword.arg),
                        )
                    )
            elif keyword.arg == "places" and name.endswith(
                ("assertAlmostEqual", "assertNotAlmostEqual")
            ):
                value = _literal_number(keyword.value)
                if value is not None:
                    self.tolerances.append(
                        ToleranceRecord(
                            self.scope,
                            name,
                            "places",
                            value,
                            node.lineno,
                            node.col_offset + 1,
                            _render(node),
                            _tolerance_anchor(node, "places"),
                        )
                    )
        if (
            name.endswith(("assertAlmostEqual", "assertNotAlmostEqual"))
            and len(node.args) >= 3
        ):
            value = _literal_number(node.args[2])
            if value is not None and not any(
                item.arg == "places" for item in node.keywords
            ):
                self.tolerances.append(
                    ToleranceRecord(
                        self.scope,
                        name,
                        "places",
                        value,
                        node.lineno,
                        node.col_offset + 1,
                        _render(node),
                        _tolerance_anchor(node, "places"),
                    )
                )

        target = _mock_target(node)
        if (
            target is not None
            and self.stack
            and self.stack[-1].lower().startswith("test")
        ):
            test_tokens = _name_tokens(self.stack[-1])
            target_tokens = _name_tokens(target.rsplit(".", 1)[-1])
            if test_tokens & target_tokens:
                self.mocks.append(
                    SyntaxRecord(
                        self.scope,
                        _stable_dump(node),
                        target,
                        node.lineno,
                        node.col_offset + 1,
                        getattr(node, "end_lineno", node.lineno),
                        _render(node),
                    )
                )
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            expression = item.context_expr
            if not isinstance(expression, ast.Call):
                continue
            name = self._canonical_suppress(_call_name(expression.func))
            if name is None:
                continue
            broad = {_call_name(argument) for argument in expression.args} & {
                "BaseException",
                "Exception",
                "builtins.BaseException",
                "builtins.Exception",
            }
            if not broad:
                continue
            self.catches.append(
                SyntaxRecord(
                    self.scope,
                    _stable_dump(expression),
                    f"{name}:{','.join(sorted(broad))}",
                    expression.lineno,
                    expression.col_offset + 1,
                    getattr(expression, "end_lineno", expression.lineno),
                    _render(expression),
                )
            )
        self.generic_visit(node)

    def _visit_try_handlers(self, node: ast.Try | ast.TryStar) -> None:
        for handler in node.handlers:
            type_names: set[str] = set()
            if handler.type is None:
                type_names.add("bare except")
            elif isinstance(handler.type, ast.Tuple):
                type_names.update(_call_name(item) for item in handler.type.elts)
            else:
                type_names.add(_call_name(handler.type))
            broad = type_names & {
                "BaseException",
                "Exception",
                "builtins.BaseException",
                "builtins.Exception",
            }
            if (
                handler.type is None or broad
            ) and not _handler_has_unconditional_validation(handler.body):
                evidence = f"except {', '.join(sorted(type_names))}: ..."
                self.catches.append(
                    SyntaxRecord(
                        self.scope,
                        _stable_dump(handler),
                        ",".join(sorted(type_names)),
                        handler.lineno,
                        handler.col_offset + 1,
                        getattr(handler, "end_lineno", handler.lineno),
                        evidence,
                    )
                )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_try_handlers(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._visit_try_handlers(node)


def inventory(source: str) -> Inventory:
    tree = ast.parse(source, type_comments=True)
    visitor = _InventoryVisitor()
    visitor.visit(tree)
    return Inventory(
        visitor.assertions,
        visitor.skips,
        visitor.catches,
        visitor.tolerances,
        visitor.mocks,
    )


class RuleEngine:
    """Compare old and new syntax for one change set."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def _finding(
        self,
        rule_id: str,
        change: ChangedFile,
        *,
        line: int,
        column: int = 1,
        end_line: int | None = None,
        message: str,
        evidence: str | None = None,
        fingerprint_context: str | None = None,
    ) -> Finding | None:
        if not self.config.rule_enabled(rule_id):
            return None
        metadata = RULES[rule_id]
        return Finding(
            rule_id=rule_id,
            title=metadata.title,
            message=message,
            severity=self.config.severity_for(rule_id, metadata.severity),
            confidence=metadata.confidence,
            path=change.path,
            line=line,
            column=column,
            end_line=end_line,
            evidence=evidence,
            remediation=metadata.remediation,
            fingerprint_context=fingerprint_context,
        )

    def analyze_test_file(
        self, change: ChangedFile
    ) -> tuple[list[Finding], str | None]:
        findings: list[Finding] = []
        parse_warning: str | None = None
        if change.old_source is None and change.new_source is None:
            findings.extend(self._fallback_line_rules(change))
            findings.extend(self._snapshot_rules(change))
            return findings, None
        old_inventory: Inventory | None = None
        new_inventory: Inventory | None = None
        if change.old_source is not None:
            try:
                old_inventory = inventory(change.old_source)
            except (SyntaxError, ValueError) as exc:
                parse_warning = f"{change.path}: old source could not be parsed ({exc})"
        else:
            old_inventory = Inventory([], [], [], [], [])
        if change.new_source is not None:
            try:
                new_inventory = inventory(change.new_source)
            except (SyntaxError, ValueError) as exc:
                parse_warning = f"{change.path}: new source could not be parsed ({exc})"
        else:
            new_inventory = Inventory([], [], [], [], [])

        if old_inventory is not None and new_inventory is not None:
            findings.extend(
                self._assertion_changes(change, old_inventory, new_inventory)
            )
            findings.extend(self._skip_changes(change, old_inventory, new_inventory))
            findings.extend(
                self._tolerance_changes(change, old_inventory, new_inventory)
            )
            findings.extend(
                self._new_records(
                    "TS005",
                    change,
                    old_inventory.catches,
                    new_inventory.catches,
                    "Broad exception suppression was added without an assertion or re-raise",
                    group_by_kind=True,
                )
            )
            findings.extend(
                self._new_records(
                    "TS007",
                    change,
                    old_inventory.mocks,
                    new_inventory.mocks,
                    "A newly added mock targets behavior named by the enclosing test",
                    group_by_kind=True,
                )
            )
        else:
            findings.extend(self._fallback_line_rules(change))

        findings.extend(self._snapshot_rules(change))
        return findings, parse_warning

    def analyze_artifact(self, change: ChangedFile) -> list[Finding]:
        """Analyze non-test artifacts for low-confidence snapshot signals."""

        return self._snapshot_rules(change)

    def _new_records(
        self,
        rule_id: str,
        change: ChangedFile,
        old: Sequence[SyntaxRecord],
        new: Sequence[SyntaxRecord],
        message: str,
        *,
        group_by_kind: bool = False,
    ) -> list[Finding]:
        def key(record: SyntaxRecord) -> tuple[str, str]:
            value = record.kind if group_by_kind else record.fingerprint
            return record.scope, value

        old_counts = Counter(key(record) for record in old)
        findings: list[Finding] = []
        # Preserve unchanged records first.  Otherwise a prepended duplicate can
        # consume the old count and make the genuinely new record disappear.
        ordered = sorted(
            new,
            key=lambda record: (change.is_new_line_changed(record.line), record.line),
        )
        for record in ordered:
            record_key = key(record)
            if old_counts[record_key]:
                old_counts[record_key] -= 1
                continue
            if not change.is_new_line_changed(record.line) and change.lines:
                continue
            finding = self._finding(
                rule_id,
                change,
                line=record.line,
                column=record.column,
                end_line=record.end_line,
                message=f"{message} in {record.scope}",
                evidence=record.evidence,
            )
            if finding:
                findings.append(finding)
        return findings

    def _skip_changes(
        self, change: ChangedFile, old: Inventory, new: Inventory
    ) -> list[Finding]:
        remaining_old = list(old.skips)

        def compatible(before: SyntaxRecord, after: SyntaxRecord) -> bool:
            return (
                before.scope == after.scope
                and before.semantic == after.semantic
                and before.placement == after.placement
            )

        # Match syntax that survived the diff before considering added lines.
        # This is essential when an identical marker is prepended to a test.
        for record in sorted(new.skips, key=lambda item: item.line):
            if change.lines and change.is_new_line_changed(record.line):
                continue
            match = next(
                (item for item in remaining_old if compatible(item, record)),
                None,
            )
            if match is not None:
                remaining_old.remove(match)

        findings: list[Finding] = []
        for record in sorted(new.skips, key=lambda item: item.line):
            if change.lines and not change.is_new_line_changed(record.line):
                continue
            candidates = [item for item in remaining_old if compatible(item, record)]
            match = min(
                candidates,
                key=lambda item: abs(change.new_line_for_old(item.line) - record.line),
                default=None,
            )
            if match is not None:
                remaining_old.remove(match)
                # A reason-only edit has the same semantic signature.  Exact
                # syntax at a new location, however, is a moved disabling marker.
                if match.fingerprint != record.fingerprint or match.line == record.line:
                    continue

            finding = self._finding(
                "TS002",
                change,
                line=record.line,
                column=record.column,
                end_line=record.end_line,
                message=(
                    "A test-disabling skip or expected-failure mechanism was "
                    f"added or moved in {record.scope}"
                ),
                evidence=record.evidence,
            )
            if finding:
                findings.append(finding)
        return findings

    @staticmethod
    def _assertion_weakened(before: AssertionRecord, after: AssertionRecord) -> bool:
        if before.predicate and before.predicate == after.predicate:
            return False
        if after.tautology and not before.tautology:
            return True
        before_category = before.predicate.partition("|")[0]
        after_category = after.predicate.partition("|")[0]
        weak_categories = {"truthy", "falsy", "nonnull", "none"}
        precise_categories = {
            "eq",
            "ne",
            "is",
            "isnot",
            "isinstance",
            "not-isinstance",
            "lt",
            "lte",
            "gt",
            "gte",
            "in",
            "notin",
        }
        same_subject = before.subject is not None and before.subject == after.subject
        if (
            same_subject
            and before_category in precise_categories
            and after_category in weak_categories
        ):
            return True
        return same_subject and before.strength > after.strength

    @staticmethod
    def _cancel_exact_assertions(
        old: Sequence[AssertionRecord], new: Sequence[AssertionRecord]
    ) -> tuple[list[AssertionRecord], list[AssertionRecord]]:
        counts = Counter(record.fingerprint for record in new)
        remaining_old: list[AssertionRecord] = []
        for record in old:
            if counts[record.fingerprint]:
                counts[record.fingerprint] -= 1
            else:
                remaining_old.append(record)
        remaining_new: list[AssertionRecord] = []
        old_counts = Counter(record.fingerprint for record in old)
        for record in new:
            if old_counts[record.fingerprint]:
                old_counts[record.fingerprint] -= 1
            else:
                remaining_new.append(record)
        return remaining_old, remaining_new

    @staticmethod
    def _pair_assertions(
        change: ChangedFile,
        old: Sequence[AssertionRecord],
        new: Sequence[AssertionRecord],
    ) -> tuple[list[tuple[AssertionRecord, AssertionRecord]], list[AssertionRecord]]:
        available = list(new)
        pairs: list[tuple[AssertionRecord, AssertionRecord]] = []
        unpaired_old: list[AssertionRecord] = []
        for before in old:
            candidates = [
                after
                for after in available
                if _plausible_assertion_replacement(before, after)
            ]
            if not candidates:
                unpaired_old.append(before)
                continue
            mapped_line = change.new_line_for_old(before.line)

            score = partial(
                _assertion_pair_score,
                before=before,
                mapped_line=mapped_line,
            )
            after = max(candidates, key=score)
            available.remove(after)
            pairs.append((before, after))
        return pairs, unpaired_old

    def _assertion_changes(
        self, change: ChangedFile, old: Inventory, new: Inventory
    ) -> list[Finding]:
        by_old: dict[str, list[AssertionRecord]] = defaultdict(list)
        by_new: dict[str, list[AssertionRecord]] = defaultdict(list)
        for record in old.assertions:
            by_old[record.scope].append(record)
        for record in new.assertions:
            by_new[record.scope].append(record)
        findings: list[Finding] = []

        for scope in sorted(set(by_old) | set(by_new)):
            old_records = sorted(
                by_old[scope], key=lambda item: (item.line, item.column)
            )
            new_records = sorted(
                by_new[scope], key=lambda item: (item.line, item.column)
            )
            old_records, new_records = self._cancel_exact_assertions(
                old_records, new_records
            )
            pairs, removed_records = self._pair_assertions(
                change, old_records, new_records
            )
            for before, after in pairs:
                if change.lines and not change.is_new_line_changed(after.line):
                    continue
                if not self._assertion_weakened(before, after):
                    continue
                detail = (
                    "an obvious tautology"
                    if after.tautology
                    else f"less-specific {after.kind}"
                )
                finding = self._finding(
                    "TS003",
                    change,
                    line=after.line,
                    column=after.column,
                    end_line=after.end_line,
                    message=f"Assertion in {scope} changed from {before.kind} to {detail}",
                    evidence=f"{before.evidence}  ->  {after.evidence}",
                )
                if finding:
                    findings.append(finding)

            for removed in removed_records:
                if not change.is_old_line_changed(removed.line) and change.lines:
                    continue
                finding = self._finding(
                    "TS001",
                    change,
                    line=change.new_line_for_old(removed.line),
                    column=removed.column,
                    message=f"An assertion was removed from {scope}",
                    evidence=removed.evidence,
                )
                if finding:
                    findings.append(finding)
        return findings

    def _tolerance_changes(
        self, change: ChangedFile, old: Inventory, new: Inventory
    ) -> list[Finding]:
        old_groups: dict[tuple[str, str, str], list[ToleranceRecord]] = defaultdict(
            list
        )
        new_groups: dict[tuple[str, str, str], list[ToleranceRecord]] = defaultdict(
            list
        )
        for record in old.tolerances:
            old_groups[(record.scope, record.call, record.parameter)].append(record)
        for record in new.tolerances:
            new_groups[(record.scope, record.call, record.parameter)].append(record)

        findings: list[Finding] = []
        for key in sorted(set(old_groups) & set(new_groups)):
            before_records = sorted(old_groups[key], key=lambda item: item.line)
            after_records = sorted(new_groups[key], key=lambda item: item.line)

            # First remove tolerances that survived on context lines.  Pairing by
            # ordinal position alone lets an inserted assertion shift every
            # subsequent comparison and can both invent and hide widenings.
            remaining_before = list(before_records)
            remaining_after: list[ToleranceRecord] = []
            for after in after_records:
                if change.lines and change.is_new_line_changed(after.line):
                    remaining_after.append(after)
                    continue
                match = next(
                    (
                        before
                        for before in remaining_before
                        if before.anchor == after.anchor and before.value == after.value
                    ),
                    None,
                )
                if match is not None:
                    remaining_before.remove(match)
                else:
                    remaining_after.append(after)

            available_after = list(remaining_after)
            for before in remaining_before:
                if not available_after:
                    break
                mapped_line = change.new_line_for_old(before.line)
                same_anchor = [
                    after for after in available_after if after.anchor == before.anchor
                ]
                candidates = same_anchor or available_after
                after = min(
                    candidates,
                    key=lambda item: abs(item.line - mapped_line),
                )
                available_after.remove(after)
                widened = (
                    after.value < before.value
                    if after.parameter == "places"
                    else after.value > before.value
                )
                if not widened or not change.is_new_line_changed(after.line):
                    continue
                finding = self._finding(
                    "TS004",
                    change,
                    line=after.line,
                    column=after.column,
                    message=(
                        f"{after.parameter} tolerance widened from "
                        f"{before.value:g} to {after.value:g} in {after.scope}"
                    ),
                    evidence=f"{before.evidence}  ->  {after.evidence}",
                )
                if finding:
                    findings.append(finding)
        return findings

    def _snapshot_rules(self, change: ChangedFile) -> list[Finding]:
        path = change.path.lower()
        snapshot_file = (
            path.endswith((".snap", ".snapshot")) or "/__snapshots__/" in f"/{path}"
        )
        pattern = re.compile(
            r"(?:--snapshot-update\b|"
            r"\b(?:snapshot_update|update_snapshots)\s*"
            r"(?:\(|=\s*(?:True|1|['\"]?(?:yes|on|all)['\"]?))|"
            r"\bsnapshot\.update\s*\(|\baccept_snapshot\s*\(|"
            r"\bsnapshot[^\n]{0,120}\bupdate\s*=\s*True\b)",
            re.IGNORECASE,
        )
        findings: list[Finding] = []
        occurrences: Counter[tuple[str, str, str, str]] = Counter()
        candidates = change.added_lines
        if snapshot_file and candidates:
            candidates = candidates[:1]
        else:
            candidates = [line for line in candidates if pattern.search(line.content)]
        for line in candidates:
            evidence = line.content.strip()
            before_context, after_context = _neighboring_diff_context(change, line)
            occurrence_key = (
                "TS006",
                evidence,
                before_context,
                after_context,
            )
            occurrence = occurrences[occurrence_key]
            occurrences[occurrence_key] += 1
            finding = self._finding(
                "TS006",
                change,
                line=line.new_line or 1,
                message=(
                    "A snapshot artifact was regenerated"
                    if snapshot_file
                    else "Snapshot update/acceptance behavior was enabled"
                ),
                evidence=evidence,
                fingerprint_context=(
                    f"snapshot\0{before_context}\0{after_context}\0{occurrence}"
                ),
            )
            if finding:
                findings.append(finding)
        return findings

    def _fallback_line_rules(self, change: ChangedFile) -> list[Finding]:
        """Conservative checks for patch input when full blobs are unavailable."""

        findings: list[Finding] = []
        occurrences: Counter[tuple[str, str, str, str]] = Counter()

        def fingerprint_context(rule_id: str, evidence: str, line: DiffLine) -> str:
            before_context, after_context = _neighboring_diff_context(change, line)
            key = (rule_id, evidence, before_context, after_context)
            occurrence = occurrences[key]
            occurrences[key] += 1
            return f"fallback\0{before_context}\0{after_context}\0{occurrence}"

        assertion = re.compile(r"^\s*(?:assert\b|[\w.]+\.assert[A-Z]\w*\s*\()")
        old_assertions = [
            line for line in change.deleted_lines if assertion.search(line.content)
        ]
        new_assertions = [
            line for line in change.added_lines if assertion.search(line.content)
        ]

        old_plain_equal = re.compile(
            r"^\s*assert\s+(?P<subject>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*==(?!=)"
        )
        new_plain_weak = re.compile(
            r"^\s*assert\s+(?:bool\()?"
            r"(?P<subject>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\)?"
            r"(?:\s+is\s+not\s+None)?\s*(?:#.*)?$"
        )
        old_unittest_equal = re.compile(
            r"^\s*[\w.]+\.assertEqual\(\s*"
            r"(?P<subject>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*,"
        )
        new_unittest_weak = re.compile(
            r"^\s*[\w.]+\.(?:assertTrue|assertIsNotNone)\(\s*"
            r"(?P<subject>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*[,)]"
        )
        for before, after in zip(old_assertions, new_assertions, strict=False):
            old_match = old_plain_equal.search(before.content)
            new_match = new_plain_weak.search(after.content)
            if old_match is None or new_match is None:
                old_match = old_unittest_equal.search(before.content)
                new_match = new_unittest_weak.search(after.content)
            if (
                old_match is not None
                and new_match is not None
                and old_match.group("subject") == new_match.group("subject")
            ):
                evidence = f"{before.content.strip()}  ->  {after.content.strip()}"
                finding = self._finding(
                    "TS003",
                    change,
                    line=after.new_line or 1,
                    message="A specific equality assertion was replaced by a truthy/non-null check",
                    evidence=evidence,
                    fingerprint_context=fingerprint_context("TS003", evidence, after),
                )
                if finding:
                    findings.append(finding)

        number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
        tolerance = re.compile(
            rf"\b(?P<parameter>rel|abs|rel_tol|abs_tol|rtol|atol|delta|places)"
            rf"\s*=\s*(?P<value>{number})"
        )
        old_tolerances: dict[str, list[tuple[DiffLine, float]]] = defaultdict(list)
        new_tolerances: dict[str, list[tuple[DiffLine, float]]] = defaultdict(list)
        for line in change.deleted_lines:
            for match in tolerance.finditer(line.content):
                old_tolerances[match.group("parameter")].append(
                    (line, float(match.group("value")))
                )
        for line in change.added_lines:
            for match in tolerance.finditer(line.content):
                new_tolerances[match.group("parameter")].append(
                    (line, float(match.group("value")))
                )
        for parameter in sorted(set(old_tolerances) & set(new_tolerances)):
            for (before_line, before_value), (after_line, after_value) in zip(
                old_tolerances[parameter], new_tolerances[parameter], strict=False
            ):
                widened = (
                    after_value < before_value
                    if parameter == "places"
                    else after_value > before_value
                )
                if not widened:
                    continue
                evidence = (
                    f"{before_line.content.strip()}  ->  {after_line.content.strip()}"
                )
                finding = self._finding(
                    "TS004",
                    change,
                    line=after_line.new_line or 1,
                    message=(
                        f"{parameter} tolerance widened from "
                        f"{before_value:g} to {after_value:g}"
                    ),
                    evidence=evidence,
                    fingerprint_context=fingerprint_context(
                        "TS004", evidence, after_line
                    ),
                )
                if finding:
                    findings.append(finding)

        for line in old_assertions[len(new_assertions) :]:
            evidence = line.content.strip()
            finding = self._finding(
                "TS001",
                change,
                line=change.new_line_for_old(line.old_line or 1),
                message="An assertion line was removed",
                evidence=evidence,
                fingerprint_context=fingerprint_context("TS001", evidence, line),
            )
            if finding:
                findings.append(finding)

        skip = re.compile(
            r"(?:pytest\.(?:skip|xfail)|pytest\.mark\.(?:skip|skipif|xfail)|"
            r"unittest\.(?:skip|skipIf|skipUnless|expectedFailure)|\.skipTest\s*\()"
        )
        old_skip_count = sum(
            bool(skip.search(line.content)) for line in change.deleted_lines
        )
        for line in [item for item in change.added_lines if skip.search(item.content)][
            old_skip_count:
        ]:
            evidence = line.content.strip()
            finding = self._finding(
                "TS002",
                change,
                line=line.new_line or 1,
                message="A pytest/unittest skip or expected-failure marker was added",
                evidence=evidence,
                fingerprint_context=fingerprint_context("TS002", evidence, line),
            )
            if finding:
                findings.append(finding)

        broad = re.compile(
            r"^\s*except(?:\s+(?:BaseException|Exception))?\s*(?:as\s+\w+)?\s*:"
        )
        old_broad_count = sum(
            bool(broad.search(line.content)) for line in change.deleted_lines
        )
        for line in [item for item in change.added_lines if broad.search(item.content)][
            old_broad_count:
        ]:
            evidence = line.content.strip()
            finding = self._finding(
                "TS005",
                change,
                line=line.new_line or 1,
                message="A broad exception handler was added; verify it does not swallow failures",
                evidence=evidence,
                fingerprint_context=fingerprint_context("TS005", evidence, line),
            )
            if finding:
                findings.append(finding)
        return findings


def coedit_findings(files: Sequence[ChangedFile], config: Config) -> list[Finding]:
    """Emit low-confidence signals for a source and its likely guarding test."""

    if not config.rule_enabled("TS008"):
        return []
    tests = [item for item in files if config.is_test_path(item.path)]
    sources = [
        item
        for item in files
        if item.path.endswith(".py") and not config.is_test_path(item.path)
    ]
    findings: list[Finding] = []
    metadata = RULES["TS008"]
    seen: set[tuple[str, str]] = set()
    for source in sources:
        source_path = source.path.replace("\\", "/")
        source_stem = source_path.rsplit("/", 1)[-1].removesuffix(".py")
        configured_patterns: list[str] = []
        for source_pattern, test_patterns in config.guarding_tests.items():
            if matches_path(source_path, (source_pattern,)):
                configured_patterns.extend(test_patterns)
        in_source_root = any(
            source_path == root.strip("/")
            or source_path.startswith(root.strip("/") + "/")
            for root in config.source_roots
        )
        if not configured_patterns and not in_source_root:
            continue
        for test in tests:
            test_path = test.path.replace("\\", "/")
            test_stem = test_path.rsplit("/", 1)[-1].removesuffix(".py")
            if test_stem.startswith("test_"):
                test_stem = test_stem[5:]
            elif test_stem.endswith("_test"):
                test_stem = test_stem[:-5]
            configured_match = (
                matches_path(test_path, tuple(configured_patterns))
                if configured_patterns
                else False
            )
            heuristic_match = source_stem != "__init__" and source_stem == test_stem
            if not (configured_match or heuristic_match):
                continue
            pair = (source.path, test.path)
            if pair in seen:
                continue
            seen.add(pair)
            first_added = next(
                (line.new_line for line in test.added_lines if line.new_line), 1
            )
            findings.append(
                Finding(
                    rule_id="TS008",
                    title=metadata.title,
                    message=f"{test.path} and its likely guarded source {source.path} changed together",
                    severity=config.severity_for("TS008", metadata.severity),
                    confidence=metadata.confidence,
                    path=test.path,
                    line=first_added or 1,
                    evidence=f"{source.path} + {test.path}",
                    remediation=metadata.remediation,
                )
            )
    return findings


def deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    unique: dict[tuple[str, str, int, str | None], Finding] = {}
    for finding in findings:
        key = (finding.rule_id, finding.path, finding.line, finding.evidence)
        unique.setdefault(key, finding)
    return sorted(
        unique.values(),
        key=lambda item: (
            -item.severity.rank,
            item.path,
            item.line,
            item.column,
            item.rule_id,
        ),
    )
