import math
import pytest

from safe_repl import safe_exec, Permissions


def safe_exec_standard(line: str, variables: dict[str, object]) -> object | None:
    """Helper to call safe_exec with STANDARD permission level (used for most tests)."""
    # Build globals with math module available (note: tests use math.sqrt() syntax)
    perms = Permissions(base="STANDARD")
    globals_dict = perms.build_custom_globals()
    globals_dict["math"] = math  # Provide math module for tests
    return safe_exec(line, variables, perms, globals_dict)


def test_safe_exec_returns_expression_value() -> None:
    variables: dict[str, object] = {}
    result = safe_exec_standard("2 + 3 * 4", variables)
    assert result == 14


def test_safe_exec_assignment_persists_between_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("x = 5", variables) is None
    assert safe_exec_standard("x += 2", variables) is None
    assert safe_exec_standard("x", variables) == 7


def test_safe_exec_allows_boolean_and_comparison_operators() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("(2 < 3) and (4 != 5)", variables) is True


def test_safe_exec_allows_whitelisted_builtin_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("abs(-3)", variables) == 3
    assert safe_exec_standard("max(1, 5, 2)", variables) == 5
    assert safe_exec_standard("round(3.14159, 2)", variables) == 3.14


def test_safe_exec_allows_math_module_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("math.sqrt(16)", variables) == 4.0
    assert safe_exec_standard("math.floor(3.7)", variables) == 3


def test_safe_exec_blocks_other_builtin_calls() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="is not allowed"):
        safe_exec_standard("open('x.txt')", variables)


def test_safe_exec_blocks_unsafe_math_calls() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="Private methods are not allowed"):
        safe_exec_standard("math._floor(3.7)", variables)


def test_safe_exec_allows_simple_string_parsing_methods() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("'a,b,c'.split(',')", variables) == ["a", "b", "c"]


def test_safe_exec_blocks_unsafe_attribute_access() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="Unsafe attribute access is not allowed"):
        safe_exec_standard("'abc'.__class__", variables)


def test_safe_exec_allows_unpacking_targets() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("a, b = (1, 2)", variables) is None
    assert safe_exec_standard("a", variables) == 1
    assert safe_exec_standard("b", variables) == 2


def test_safe_exec_allows_subscript_and_slice_for_existing_variables() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_standard("arr = [1, 2, 3]", variables) is None
    assert safe_exec_standard("arr[0] = 9", variables) is None
    assert safe_exec_standard("arr[1:3] = [7, 8]", variables) is None
    assert safe_exec_standard("arr", variables) == [9, 7, 8]


def test_safe_exec_blocks_subscript_assignment_for_unknown_root_variable() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(
        ValueError,
        match="Subscript/slice assignment is only allowed on existing user variables",
    ):
        safe_exec_standard("arr[0] = 1", variables)
