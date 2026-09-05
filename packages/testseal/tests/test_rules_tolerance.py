from __future__ import annotations

import difflib
import unittest

import pytest
from testseal import Auditor, audit_diff
from testseal.diff import changes_from_sources


@pytest.mark.parametrize("patch_only", [False, True])
@pytest.mark.parametrize(
    "parameter,before,after,left,right",
    [("delta", 0.1, 0.001, 1, 1.01), ("places", 2, 6, 1, 1.00001)],
)
def test_not_almost_equal_reports_only_relaxed_comparisons(
    parameter: str,
    before: float,
    after: float,
    left: float,
    right: float,
    patch_only: bool,
) -> None:
    case = unittest.TestCase()
    with pytest.raises(AssertionError):
        case.assertNotAlmostEqual(left, right, **{parameter: before})
    case.assertNotAlmostEqual(left, right, **{parameter: after})

    old = f"def test_value(self):\n    self.assertNotAlmostEqual({left}, {right}, {parameter}={before})\n"
    new = f"def test_value(self):\n    self.assertNotAlmostEqual({left}, {right}, {parameter}={after})\n"

    def scan(old_source: str, new_source: str):
        if patch_only:
            return audit_diff(
                "".join(
                    difflib.unified_diff(
                        old_source.splitlines(keepends=True),
                        new_source.splitlines(keepends=True),
                        fromfile="a/tests/test_value.py",
                        tofile="b/tests/test_value.py",
                    )
                )
            )
        return Auditor().audit(
            [changes_from_sources("tests/test_value.py", old_source, new_source)]
        )

    result = scan(old, new)
    assert result.parse_warnings == []
    assert [finding.rule_id for finding in result.findings] == ["TS004"]
    assert "inequality tolerance relaxed" in result.findings[0].message
    assert scan(new, old).findings == []


def test_not_almost_equal_positional_places_can_be_weakened() -> None:
    result = Auditor().audit(
        [
            changes_from_sources(
                "tests/test_value.py",
                "def test_value(self):\n    self.assertNotAlmostEqual(a, b, 2)\n",
                "def test_value(self):\n    self.assertNotAlmostEqual(a, b, 6)\n",
            )
        ]
    )
    assert [finding.rule_id for finding in result.findings] == ["TS004"]
