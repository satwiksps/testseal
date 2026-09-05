from __future__ import annotations

import pytest
from testseal import Auditor
from testseal.diff import changes_from_sources


def audit(old: str, new: str):
    result = Auditor().audit([changes_from_sources("tests/test_value.py", old, new)])
    assert result.parse_warnings == []
    return result


@pytest.mark.parametrize(
    "before,after",
    [(2**53, 2**53 + 1), (10**399, 10**400), (-10**400, -10**399)],
)
def test_integer_tolerances_keep_exact_values_without_overflow(before: int, after: int) -> None:
    result = audit(
        f"def test_value():\n    assert value == pytest.approx(1, abs={before})\n",
        f"def test_value():\n    assert value == pytest.approx(1, abs={after})\n",
    )
    findings = [item for item in result.findings if item.rule_id == "TS004"]
    assert len(findings) == 1
    assert f"from {before} to {after}" in findings[0].message


def test_large_integer_tolerance_tightening_is_not_reported() -> None:
    result = audit(
        f"def test_value():\n    assert value == pytest.approx(1, abs={10**400})\n",
        f"def test_value():\n    assert value == pytest.approx(1, abs={10**399})\n",
    )
    assert result.findings == []


@pytest.mark.parametrize("expression", ["self.assertFalse(False)", "self.assertFalse(0)"])
def test_falsy_literal_assertions_do_not_validate_broad_handlers(expression: str) -> None:
    result = audit(
        "def test_value(self):\n    call()\n",
        f"def test_value(self):\n    try:\n        call()\n    except Exception:\n        {expression}\n",
    )
    assert [item.rule_id for item in result.findings] == ["TS005"]


@pytest.mark.parametrize(
    "expression", ["self.assertFalse(False)", "self.assertFalse(0)", "assert not False"]
)
def test_falsy_literal_replacements_are_weakened_assertions(expression: str) -> None:
    result = audit(
        "def test_value(self):\n    assert value == 3\n",
        f"def test_value(self):\n    {expression}\n",
    )
    assert [item.rule_id for item in result.findings] == ["TS003"]


def test_tautology_before_unconditional_reraise_does_not_hide_validation() -> None:
    result = audit(
        "def test_value():\n    call()\n",
        "def test_value():\n    try:\n        call()\n    except Exception:\n        assert True\n        raise\n",
    )
    assert result.findings == []
