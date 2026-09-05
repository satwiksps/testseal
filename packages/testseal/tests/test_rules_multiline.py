from __future__ import annotations

import pytest
from testseal import Auditor
from testseal.diff import changes_from_sources


def rule_ids(old: str, new: str) -> list[str]:
    result = Auditor().audit([changes_from_sources("tests/test_payment.py", old, new)])
    assert result.parse_warnings == []
    return [finding.rule_id for finding in result.findings]


@pytest.mark.parametrize(
    "old,new",
    [
        ("    assert (\n        total == 3\n    )\n", "    assert (\n        total\n    )\n"),
        (
            "    self.assertTrue(\n        total == 3\n    )\n",
            "    self.assertTrue(\n        total\n    )\n",
        ),
        (
            "    with pytest.raises(\n        ValueError,\n        match='invalid',\n    ):\n        call()\n",
            "    with pytest.raises(\n        ValueError,\n    ):\n        call()\n",
        ),
    ],
)
def test_weakening_inside_unchanged_assertion_start_is_reported(old: str, new: str) -> None:
    assert rule_ids("def test_total(self):\n" + old, "def test_total(self):\n" + new) == [
        "TS003"
    ]


def test_multiline_skip_condition_change_is_reported() -> None:
    old = "@pytest.mark.skipif(\n    condition=False,\n    reason='platform',\n)\ndef test_total():\n    assert total == 3\n"
    assert rule_ids(old, old.replace("condition=False", "condition=True")) == ["TS002"]


def test_removed_xfail_condition_is_reported() -> None:
    old = "@pytest.mark.xfail(\n    condition=False,\n    reason='platform',\n)\ndef test_total():\n    assert total == 3\n"
    assert rule_ids(old, old.replace("    condition=False,\n", "")) == ["TS002"]


def test_multiline_skip_reason_edit_is_not_reported() -> None:
    old = "@pytest.mark.skipif(\n    condition=True,\n    reason='old reason',\n)\ndef test_total():\n    assert total == 3\n"
    assert rule_ids(old, old.replace("old reason", "new reason")) == []


def test_multiline_tolerance_change_is_reported() -> None:
    old = "def test_total():\n    assert total == pytest.approx(\n        3,\n        abs=0.001,\n    )\n"
    assert rule_ids(old, old.replace("abs=0.001", "abs=0.1")) == ["TS004"]


@pytest.mark.parametrize("validation", ["raise", "assert exc.args"])
def test_removing_validation_from_existing_handler_is_reported(validation: str) -> None:
    old = f"def test_call():\n    try:\n        call()\n    except Exception as exc:\n        log(exc)\n        {validation}\n"
    expected = ["TS005"] if validation == "raise" else ["TS005", "TS001"]
    assert rule_ids(old, old.replace(f"        {validation}\n", "")) == expected


def test_multiline_mock_target_change_is_reported() -> None:
    old = "def test_payment(mocker):\n    mocker.patch(\n        'service.request',\n    )\n    assert payment() == 3\n"
    assert rule_ids(old, old.replace("service.request", "service.payment")) == ["TS007"]
