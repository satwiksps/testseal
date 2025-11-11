from __future__ import annotations

import ast
from dataclasses import replace

import pytest
from testseal import Auditor, Config
from testseal.config import RuleConfig
from testseal.diff import changes_from_sources
from testseal.models import Severity

PATH = "tests/test_service.py"


def audit(old: str, new: str, *, path: str = PATH, config: Config | None = None):
    change = changes_from_sources(path, old, new)
    return Auditor(config).audit([change])


def ids(result) -> list[str]:
    return [finding.rule_id for finding in result.findings]


def test_ts001_detects_removed_plain_assertion() -> None:
    result = audit(
        "def test_total():\n    assert total == 3\n    assert valid\n",
        "def test_total():\n    assert total == 3\n",
    )
    assert ids(result) == ["TS001"]
    assert result.findings[0].evidence == "assert valid"


def test_ts001_detects_removed_unittest_assertion_and_pytest_raises() -> None:
    old = """def test_total(self):
    self.assertEqual(total, 3)
    with pytest.raises(ValueError):
        calculate()
"""
    new = "def test_total(self):\n    self.assertEqual(total, 3)\n"
    result = audit(old, new)
    assert ids(result).count("TS001") == 1


@pytest.mark.parametrize(
    "assertion",
    [
        "mock.assert_not_called()",
        "mock.assert_any_call(1)",
        "mock.assert_has_calls([call(1)])",
    ],
)
def test_ts001_detects_removed_mock_assertion_variants(assertion: str) -> None:
    result = audit(
        f"def test_call():\n    {assertion}\n",
        "def test_call():\n    pass\n",
    )
    assert ids(result) == ["TS001"]


def test_ts001_detects_removed_pytest_warns_with_module_alias() -> None:
    result = audit(
        (
            "import pytest as pt\n\n"
            "def test_call():\n"
            "    with pt.warns(UserWarning):\n"
            "        call()\n"
        ),
        "import pytest as pt\n\ndef test_call():\n    call()\n",
    )
    assert ids(result) == ["TS001"]


def test_changed_expected_value_is_not_a_removed_assertion() -> None:
    result = audit(
        "def test_total():\n    assert total == 3\n",
        "def test_total():\n    assert total == 4\n",
    )
    assert "TS001" not in ids(result)


def test_unrelated_new_assertion_cannot_hide_a_removed_assertion() -> None:
    result = audit(
        "def test_total():\n    assert total == expected\n",
        "def test_total():\n    assert logger.called\n",
    )
    assert ids(result) == ["TS001"]
    assert result.findings[0].evidence == "assert total == expected"


def test_changed_mock_call_expectation_is_not_a_removed_assertion() -> None:
    result = audit(
        "def test_call():\n    client.send.assert_called_once_with('old')\n",
        "def test_call():\n    client.send.assert_called_once_with('new')\n",
    )
    assert "TS001" not in ids(result)


def test_reordered_identical_assertions_are_not_reported_as_removed() -> None:
    result = audit(
        "def test_total():\n    assert total == 3\n    assert valid\n",
        "def test_total():\n    assert valid\n    assert total == 3\n",
    )
    assert "TS001" not in ids(result)


def test_common_unittest_type_assertion_is_inventoried() -> None:
    result = audit(
        "def test_result(self):\n    self.assertIsInstance(result, Widget)\n",
        "def test_result(self):\n    pass\n",
    )
    assert ids(result) == ["TS001"]


@pytest.mark.parametrize(
    "marker",
    [
        "@pytest.mark.skip(reason='broken')",
        "@pytest.mark.skipif(True, reason='broken')",
        "@pytest.mark.xfail(reason='broken')",
        "@unittest.skip('broken')",
        "@unittest.skipIf(True, 'broken')",
        "@unittest.expectedFailure",
    ],
)
def test_ts002_detects_added_skip_decorators(marker: str) -> None:
    old = "def test_total():\n    assert total == 3\n"
    new = f"{marker}\ndef test_total():\n    assert total == 3\n"
    result = audit(old, new)
    assert ids(result).count("TS002") == 1


@pytest.mark.parametrize(
    "statement",
    ["pytest.skip('later')", "pytest.xfail('later')", "self.skipTest('later')"],
)
def test_ts002_detects_imperative_skip_calls(statement: str) -> None:
    result = audit(
        "def test_total(self):\n    assert total == 3\n",
        f"def test_total(self):\n    {statement}\n    assert total == 3\n",
    )
    assert "TS002" in ids(result)


def test_existing_skip_with_changed_reason_is_not_reported_as_new() -> None:
    result = audit(
        "@pytest.mark.skip(reason='one')\ndef test_total():\n    assert total == 3\n",
        "@pytest.mark.skip(reason='two')\ndef test_total():\n    assert total == 3\n",
    )
    assert "TS002" not in ids(result)


def test_ts002_detects_changed_skip_condition() -> None:
    result = audit(
        "@pytest.mark.skipif(os.name == 'nt', reason='platform')\ndef test_total():\n    assert total == 3\n",
        "@pytest.mark.skipif(sys.platform == 'win32', reason='platform')\ndef test_total():\n    assert total == 3\n",
    )
    assert ids(result).count("TS002") == 1


def test_ts002_detects_marker_moved_to_another_test() -> None:
    old = """@pytest.mark.skip(reason='broken')
def test_one():
    assert one

def test_two():
    assert two
"""
    new = """def test_one():
    assert one

@pytest.mark.skip(reason='broken')
def test_two():
    assert two
"""
    assert ids(audit(old, new)).count("TS002") == 1


def test_ts002_detects_prepended_duplicate_marker() -> None:
    old = """@pytest.mark.skip(reason='broken')
def test_total():
    assert total == 3
"""
    new = """@pytest.mark.skip(reason='broken')
@pytest.mark.skip(reason='broken')
def test_total():
    assert total == 3
"""
    assert ids(audit(old, new)).count("TS002") == 1


def test_ts002_recognizes_imported_pytest_mark() -> None:
    result = audit(
        "from pytest import mark\n\ndef test_total():\n    assert total == 3\n",
        "from pytest import mark\n\n@mark.skip(reason='broken')\ndef test_total():\n    assert total == 3\n",
    )
    assert ids(result).count("TS002") == 1


@pytest.mark.parametrize(
    "import_line,call",
    [
        ("import pytest", "pytest.importorskip('package')"),
        ("import pytest as pt", "pt.importorskip('package')"),
        ("from pytest import importorskip as need", "need('package')"),
    ],
)
def test_ts002_detects_added_importorskip(import_line: str, call: str) -> None:
    result = audit(
        f"{import_line}\n\ndef test_load():\n    import package\n",
        f"{import_line}\n\ndef test_load():\n    package = {call}\n",
    )
    assert ids(result).count("TS002") == 1


def test_importorskip_reason_only_edit_is_not_reported_as_new() -> None:
    result = audit(
        (
            "import pytest\n\n"
            "package = pytest.importorskip('package', reason='old')\n"
            "def test_load():\n    assert package\n"
        ),
        (
            "import pytest\n\n"
            "package = pytest.importorskip('package', reason='new')\n"
            "def test_load():\n    assert package\n"
        ),
    )
    assert "TS002" not in ids(result)


@pytest.mark.parametrize(
    "old_assertion,new_assertion",
    [
        ("assert result == expected", "assert result"),
        ("self.assertEqual(result, expected)", "self.assertTrue(result)"),
        ("self.assertIs(result, expected)", "self.assertIsNotNone(result)"),
        ("assert isinstance(result, Widget)", "assert bool(result)"),
    ],
)
def test_ts003_detects_assertion_strength_downgrades(
    old_assertion: str, new_assertion: str
) -> None:
    result = audit(
        f"def test_result(self):\n    {old_assertion}\n",
        f"def test_result(self):\n    {new_assertion}\n",
    )
    assert ids(result) == ["TS003"]


def test_assertion_strengthening_is_not_flagged() -> None:
    result = audit(
        "def test_result():\n    assert result\n",
        "def test_result():\n    assert result == expected\n",
    )
    assert "TS003" not in ids(result)


def test_semantically_equivalent_unittest_conversion_is_not_weakened() -> None:
    result = audit(
        "def test_result(self):\n    self.assertEqual(result, expected)\n",
        "def test_result(self):\n    self.assertTrue(result == expected)\n",
    )
    assert "TS003" not in ids(result)


@pytest.mark.parametrize(
    "old_context,new_context",
    [
        ("pytest.raises(ValueError)", "pytest.raises(Exception)"),
        (
            "pytest.raises(ValueError, match='invalid')",
            "pytest.raises(ValueError)",
        ),
        (
            "expect_error(ValueError, match='invalid')",
            "expect_error(ValueError)",
        ),
    ],
)
def test_ts003_detects_weakened_pytest_exception_expectation(
    old_context: str, new_context: str
) -> None:
    imported = (
        "from pytest import raises as expect_error\n" if "expect" in old_context else ""
    )
    result = audit(
        f"{imported}def test_call():\n    with {old_context}:\n        call()\n",
        f"{imported}def test_call():\n    with {new_context}:\n        call()\n",
    )
    assert ids(result) == ["TS003"]


@pytest.mark.parametrize(
    "old_context,new_context",
    [
        ("pytest.raises(ValueError)", "pytest.raises(TypeError)"),
        (
            "pytest.raises(ValueError)",
            "pytest.raises(ValueError, match='invalid')",
        ),
    ],
)
def test_changed_or_strengthened_pytest_exception_expectation_is_not_weakened(
    old_context: str, new_context: str
) -> None:
    result = audit(
        f"def test_call():\n    with {old_context}:\n        call()\n",
        f"def test_call():\n    with {new_context}:\n        call()\n",
    )
    assert "TS001" not in ids(result)
    assert "TS003" not in ids(result)


@pytest.mark.parametrize(
    "old_assertion,new_assertion",
    [
        ("self.assertEqual(result, expected)", "self.assertIsNotNone(result)"),
        ("self.assertIsInstance(result, Widget)", "self.assertTrue(result)"),
        ("self.assertEqual(result, expected)", "self.assertEqual(result, result)"),
        ("assert result == expected", "assert True"),
    ],
)
def test_ts003_detects_nonnull_truthy_and_tautological_replacements(
    old_assertion: str, new_assertion: str
) -> None:
    result = audit(
        f"def test_result(self):\n    {old_assertion}\n",
        f"def test_result(self):\n    {new_assertion}\n",
    )
    assert ids(result) == ["TS003"]


@pytest.mark.parametrize(
    "old_assertion,new_assertion",
    [
        (
            "assert value == pytest.approx(1.0, rel=1e-6)",
            "assert value == pytest.approx(1.0, rel=1e-2)",
        ),
        (
            "assert math.isclose(value, 1, abs_tol=0.001)",
            "assert math.isclose(value, 1, abs_tol=0.1)",
        ),
        (
            "self.assertAlmostEqual(value, 1, places=6)",
            "self.assertAlmostEqual(value, 1, places=2)",
        ),
        (
            "self.assertAlmostEqual(value, 1, delta=0.001)",
            "self.assertAlmostEqual(value, 1, delta=0.5)",
        ),
    ],
)
def test_ts004_detects_widened_tolerances(
    old_assertion: str, new_assertion: str
) -> None:
    result = audit(
        f"def test_value(self):\n    {old_assertion}\n",
        f"def test_value(self):\n    {new_assertion}\n",
    )
    assert "TS004" in ids(result)


def test_tighter_tolerance_is_not_flagged() -> None:
    result = audit(
        "def test_value():\n    assert value == pytest.approx(1, abs=0.1)\n",
        "def test_value():\n    assert value == pytest.approx(1, abs=0.001)\n",
    )
    assert "TS004" not in ids(result)


def test_ts004_ignores_inserted_tolerance_and_still_finds_widening() -> None:
    old = """def test_values():
    assert first == pytest.approx(1, abs=0.01)
    assert second == pytest.approx(2, abs=0.01)
"""
    new = """def test_values():
    assert inserted == pytest.approx(0, abs=0.0001)
    assert first == pytest.approx(1, abs=0.01)
    assert second == pytest.approx(2, abs=0.1)
"""
    assert ids(audit(old, new)).count("TS004") == 1


def test_inserted_loose_tolerance_does_not_invent_a_widening() -> None:
    old = """def test_values():
    assert first == pytest.approx(1, abs=0.01)
    assert second == pytest.approx(2, abs=0.1)
"""
    new = """def test_values():
    assert inserted == pytest.approx(0, abs=0.5)
    assert first == pytest.approx(1, abs=0.01)
    assert second == pytest.approx(2, abs=0.001)
"""
    assert "TS004" not in ids(audit(old, new))


@pytest.mark.parametrize("exception", ["Exception", "BaseException", ""])
def test_ts005_detects_new_broad_exception_swallowing(exception: str) -> None:
    clause = f"except {exception}:" if exception else "except:"
    new = f"""def test_call():
    try:
        call()
    {clause}
        pass
"""
    result = audit("def test_call():\n    call()\n", new)
    assert "TS005" in ids(result)


def test_broad_handler_that_asserts_or_reraises_is_not_swallowing() -> None:
    for body in ("raise", "assert exc.args"):
        new = f"""def test_call():
    try:
        call()
    except Exception as exc:
        {body}
"""
        assert "TS005" not in ids(audit("def test_call():\n    call()\n", new))


def test_unittest_assertion_validates_a_broad_handler() -> None:
    new = """def test_call(self):
    try:
        call()
    except Exception as exc:
        self.assertEqual(exc.args, ('broken',))
"""
    assert "TS005" not in ids(audit("def test_call(self):\n    call()\n", new))


@pytest.mark.parametrize(
    "body",
    [
        "if debug:\n            raise",
        "if debug:\n            assert exc.args",
        "assert True",
        "self.assertTrue(True)",
        "self.assertEqual(exc, exc)",
    ],
)
def test_conditional_or_tautological_validation_does_not_hide_swallowing(
    body: str,
) -> None:
    new = f"""def test_call():
    try:
        call()
    except Exception as exc:
        {body}
"""
    assert "TS005" in ids(audit("def test_call():\n    call()\n", new))


def test_tuple_typed_handler_with_immediate_reraise_is_safe() -> None:
    new = """def test_call():
    try:
        call()
    except (Exception, BaseException):
        raise
"""
    assert "TS005" not in ids(audit("def test_call():\n    call()\n", new))


@pytest.mark.parametrize(
    "import_line,suppress_call",
    [
        ("import contextlib", "contextlib.suppress(Exception)"),
        ("import contextlib as ctx", "ctx.suppress(BaseException)"),
        ("from contextlib import suppress as ignore", "ignore(Exception)"),
    ],
)
def test_ts005_detects_broad_contextlib_suppress(
    import_line: str, suppress_call: str
) -> None:
    result = audit(
        f"{import_line}\n\ndef test_call():\n    call()\n",
        (
            f"{import_line}\n\ndef test_call():\n"
            f"    with {suppress_call}:\n        call()\n"
        ),
    )
    assert "TS005" in ids(result)


def test_narrow_contextlib_suppress_is_not_reported_as_broad() -> None:
    result = audit(
        "import contextlib\n\ndef test_call():\n    call()\n",
        (
            "import contextlib\n\ndef test_call():\n"
            "    with contextlib.suppress(FileNotFoundError):\n        call()\n"
        ),
    )
    assert "TS005" not in ids(result)


@pytest.mark.skipif(not hasattr(ast, "TryStar"), reason="requires Python 3.11 AST")
@pytest.mark.parametrize(
    "exception,body,expected",
    [
        ("Exception", "pass", True),
        ("builtins.BaseException", "pass", True),
        ("ValueError", "pass", False),
        ("Exception", "raise", False),
    ],
)
def test_ts005_handles_exception_groups(
    exception: str, body: str, expected: bool
) -> None:
    new = f"""def test_call():
    try:
        call()
    except* {exception}:
        {body}
"""
    assert ("TS005" in ids(audit("def test_call():\n    call()\n", new))) is expected


def test_ts006_detects_snapshot_update_flag_and_snapshot_artifact() -> None:
    result = audit(
        "def test_ui(snapshot):\n    snapshot.assert_match(view())\n",
        "def test_ui(snapshot):\n    snapshot.assert_match(view(), update=True)\n",
    )
    assert "TS006" in ids(result)

    artifact = changes_from_sources("tests/__snapshots__/ui.snap", "old\n", "new\n")
    result = Auditor().audit([artifact])
    assert ids(result) == ["TS006"]


def test_regular_snapshot_assertion_is_not_regeneration() -> None:
    result = audit(
        "def test_ui(snapshot):\n    snapshot.assert_match(old_view())\n",
        "def test_ui(snapshot):\n    snapshot.assert_match(new_view())\n",
    )
    assert "TS006" not in ids(result)

    unrelated = audit(
        "def test_record():\n    save(record)\n",
        "def test_record():\n    save(record, update=True)\n",
    )
    assert "TS006" not in ids(unrelated)


def test_disabled_snapshot_update_flag_is_not_reported_as_enabled() -> None:
    result = audit(
        "def test_ui():\n    snapshot_update = None\n",
        "def test_ui():\n    snapshot_update = False\n",
    )
    assert "TS006" not in ids(result)


def test_ts007_detects_mock_of_behavior_named_by_test() -> None:
    result = audit(
        "def test_process_payment(mocker):\n    assert process_payment()\n",
        "def test_process_payment(mocker):\n    mocker.patch('billing.process_payment')\n    assert process_payment()\n",
    )
    assert "TS007" in ids(result)


@pytest.mark.parametrize(
    "statement",
    [
        "mocker.patch.object(billing, 'process_payment')",
        "patch.object(Billing, 'process_payment')",
    ],
)
def test_ts007_detects_patch_object_target_attribute(statement: str) -> None:
    result = audit(
        "def test_process_payment(mocker):\n    assert process_payment()\n",
        f"def test_process_payment(mocker):\n    {statement}\n    assert process_payment()\n",
    )
    assert "TS007" in ids(result)


def test_unrelated_boundary_mock_is_not_flagged_as_subject() -> None:
    result = audit(
        "def test_process_payment(mocker):\n    assert process_payment()\n",
        "def test_process_payment(mocker):\n    mocker.patch('http.request')\n    assert process_payment()\n",
    )
    assert "TS007" not in ids(result)


def test_ts008_detects_source_and_conventional_guarding_test_coedit() -> None:
    source = changes_from_sources("src/payments.py", "RATE = 1\n", "RATE = 2\n")
    test = changes_from_sources(
        "tests/test_payments.py",
        "def test_rate():\n    assert RATE == 1\n",
        "def test_rate():\n    assert RATE == 2\n",
    )
    result = Auditor().audit([source, test])
    assert "TS008" in ids(result)


def test_ts008_honors_configured_guarding_test_globs() -> None:
    config = Config(guarding_tests={"src/**/*.py": ("checks/**/*_spec.py",)})
    source = changes_from_sources("src/domain/payment/service.py", "X = 1\n", "X = 2\n")
    test = changes_from_sources(
        "checks/domain/payment_spec.py",
        "def test_x():\n    assert X == 1\n",
        "def test_x():\n    assert X == 2\n",
    )
    # Explicit patterns must also classify the custom test location.
    config = replace(
        config, test_patterns=config.test_patterns + ("checks/**/*_spec.py",)
    )
    result = Auditor(config).audit([source, test])
    assert "TS008" in ids(result)


def test_ts008_guarding_double_star_matches_zero_directory_levels() -> None:
    config = Config(guarding_tests={"src/**/*.py": ("tests/**/*.py",)})
    source = changes_from_sources("src/service.py", "X = 1\n", "X = 2\n")
    test = changes_from_sources(
        "tests/test_contract.py",
        "def test_x():\n    assert X == 1\n",
        "def test_x():\n    assert X == 2\n",
    )

    result = Auditor(config).audit([source, test])

    assert "TS008" in ids(result)


def test_disabled_rule_and_severity_override_are_applied() -> None:
    old = "def test_x():\n    assert value\n"
    new = "def test_x():\n    pass\n"
    assert not audit(
        old, new, config=Config(disabled_rules=frozenset({"TS001"}))
    ).findings

    config = Config(rules={"TS001": RuleConfig(severity=Severity.MEDIUM)})
    result = audit(old, new, config=config)
    assert result.findings[0].severity is Severity.MEDIUM
