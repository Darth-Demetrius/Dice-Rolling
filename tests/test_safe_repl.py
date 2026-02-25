import math
import pytest

from safe_repl import (
    safe_exec,
    set_active_permissions,
    set_memory_limit_bytes,
    set_timeout_seconds,
    Permissions,
    PermissionLevel,
)


def activate(level: PermissionLevel, imports: dict[str, object] | None = None) -> Permissions:
    perms = Permissions(
        base_perms=level,
        allow_symbols=set(),
        block_symbols=set(),
        allow_nodes=set(),
        block_nodes=set(),
        imports=imports or {},
    )
    set_active_permissions(perms)
    return perms


def safe_exec_limited(line: str, variables: dict[str, object]) -> object | None:
    """Helper to call safe_exec with LIMITED permission level (used for most tests)."""
    # Build globals with math module available (note: tests use math.sqrt() syntax)
    activate(PermissionLevel.LIMITED, {"math": math})
    return safe_exec(line, variables)


def test_safe_exec_basic_operators() -> None:
    variables: dict[str, object] = {}
    result = safe_exec_limited("2 + 3 * 4", variables)
    assert result == 14
    assert safe_exec_limited("(2 < 3) and (4 != 5)", variables) is True


def test_safe_exec_assignment_persists_between_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_limited("x = 5", variables) is None
    assert safe_exec_limited("x += 2", variables) is None
    assert safe_exec_limited("x", variables) == 7


def test_safe_exec_allows_whitelisted_builtin_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_limited("abs(-3)", variables) == 3
    assert safe_exec_limited("max(1, 5, 2)", variables) == 5
    assert safe_exec_limited("round(3.14159, 2)", variables) == 3.14


def test_safe_exec_allows_math_module_calls() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_limited("math.sqrt(16)", variables) == 4.0
    assert safe_exec_limited("math.floor(3.7)", variables) == 3


def test_safe_exec_blocks_other_builtin_calls() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="is not allowed"):
        safe_exec_limited("open('x.txt')", variables)


def test_safe_exec_blocks_unsafe_math_calls() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="Private methods are not allowed"):
        safe_exec_limited("math._floor(3.7)", variables)


def test_safe_exec_blocks_unsafe_attribute_access() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(ValueError, match="Private attributes are not allowed"):
        safe_exec_limited("'abc'.__class__", variables)


def test_safe_exec_allows_unpacking_targets() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_limited("a, b = (1, 2)", variables) is None
    assert safe_exec_limited("a", variables) == 1
    assert safe_exec_limited("b", variables) == 2


def test_safe_exec_allows_subscript_and_slice_for_existing_variables() -> None:
    variables: dict[str, object] = {}
    assert safe_exec_limited("arr = [1, 2, 3]", variables) is None
    assert safe_exec_limited("arr[0] = 9", variables) is None
    assert safe_exec_limited("arr[1:3] = [7, 8]", variables) is None
    assert safe_exec_limited("arr", variables) == [9, 7, 8]


def test_safe_exec_blocks_subscript_assignment_for_unknown_root_variable() -> None:
    variables: dict[str, object] = {}
    with pytest.raises(
        ValueError,
        match="Subscript/slice assignment is only allowed on existing user variables",
    ):
        safe_exec_limited("arr[0] = 1", variables)


def test_minimum_blocks_all_attribute_access() -> None:
    """MINIMUM mode should block all attribute access (even on literals)."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.MINIMUM)
    # String literals with method calls should be blocked
    with pytest.raises(ValueError, match="Attribute access not allowed"):
        safe_exec("'hello'.upper()", variables)


def test_minimum_blocks_unpacking_assignments() -> None:
    """MINIMUM mode should block unpacking assignments for extra safety."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.MINIMUM)
    # Unpacking should be blocked in MINIMUM
    with pytest.raises(ValueError, match="Unpacking assignment is not allowed"):
        safe_exec("a, b = 1, 2", variables)

    # Simple assignment should still work
    result = safe_exec("x = 5", variables)
    assert result is None
    assert variables["x"] == 5


def test_limited_enforces_timeout() -> None:
    variables: dict[str, object] = {}
    original_timeouts = Permissions.TIMEOUT_SECONDS_BY_LEVEL
    try:
        set_timeout_seconds(PermissionLevel.LIMITED, 0.01)
        activate(PermissionLevel.LIMITED)
        with pytest.raises(TimeoutError, match="Execution timed out"):
            safe_exec("while True:\n    pass", variables)
    finally:
        Permissions.TIMEOUT_SECONDS_BY_LEVEL = original_timeouts


def test_limited_enforces_memory_limit() -> None:
    variables: dict[str, object] = {}
    original_limits = Permissions.MEMORY_LIMIT_BYTES_BY_LEVEL
    try:
        set_memory_limit_bytes(PermissionLevel.LIMITED, 64 * 1024)
        activate(PermissionLevel.LIMITED)
        with pytest.raises((MemoryError, RuntimeError)):
            safe_exec("x = list(range(200000))", variables)
    finally:
        Permissions.MEMORY_LIMIT_BYTES_BY_LEVEL = original_limits


def test_limited_allows_attributes_on_literals() -> None:
    """LIMITED+ mode should allow attribute access on literals but not variables."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.LIMITED)
    # String literal methods should work
    result = safe_exec("'hello'.upper()", variables)
    assert result == "HELLO"

    # List literal methods should work
    result = safe_exec("[1, 2, 3].count(2)", variables)
    assert result == 1


def test_limited_blocks_attributes_on_user_variables() -> None:
    """LIMITED+ mode should block attribute access on user variables to prevent probing."""
    variables: dict[str, object] = {"msg": "hello"}
    activate(PermissionLevel.LIMITED)
    # Accessing methods on user variables should be blocked
    with pytest.raises(ValueError, match="Attribute access not allowed"):
        safe_exec("msg.upper()", variables)


def test_limited_allows_function_definition() -> None:
    """LIMITED mode should allow def and return."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.LIMITED)

    safe_exec("""
def add(a, b):
    return a + b
""".strip(), variables)
    result = safe_exec("add(2, 3)", variables)
    assert result == 5


def test_limited_blocks_class_definition() -> None:
    """LIMITED mode should block class definitions."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.LIMITED)

    with pytest.raises(ValueError, match="Unsupported syntax"):
        safe_exec("""
class A:
    pass
""".strip(), variables)


def test_limited_blocks_try_except() -> None:
    """LIMITED mode should block exception handling."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.LIMITED)

    with pytest.raises(ValueError, match="Unsupported syntax"):
        safe_exec("""
try:
    x = 1
except Exception:
    x = 2
""".strip(), variables)


def test_permissive_allows_class_and_try() -> None:
    """PERMISSIVE mode should allow class definitions and exception handling."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.PERMISSIVE)

    safe_exec("""
class A:
    pass

try:
    y = 1
except Exception:
    y = 2
""".strip(), variables)
    result = safe_exec("y", variables)
    assert result == 1
    assert "A" in variables


def test_permissive_blocks_imports() -> None:
    """PERMISSIVE mode should block import statements."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.PERMISSIVE)

    with pytest.raises(ValueError, match="Unsupported syntax"):
        safe_exec("import math", variables)


def test_unsupervised_allows_imports() -> None:
    """UNSUPERVISED mode should allow import statements."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.UNSUPERVISED)

    safe_exec("import math", variables)
    result = safe_exec("math.sqrt(9)", variables)
    assert result == 3.0


def test_unsupervised_blocks_eval() -> None:
    """UNSUPERVISED mode should still block eval/exec."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.UNSUPERVISED)

    with pytest.raises(ValueError, match="is not allowed"):
        safe_exec("eval('2 + 2')", variables)


def test_permissive_allows_global_and_nonlocal() -> None:
    """PERMISSIVE mode should allow global and nonlocal statements."""
    variables: dict[str, object] = {}
    perms = activate(PermissionLevel.PERMISSIVE)

    safe_exec("""
x = 0
def outer():
    y = 1
    def inner():
        nonlocal y
        global x
        y = 2
        x = 3
    inner()
    return y
""".strip(), variables)
    result = safe_exec("outer()", variables)
    assert result == 2
    assert perms.globals_dict["x"] == 3


def test_unsupervised_allows_from_import() -> None:
    """UNSUPERVISED mode should allow from-import statements."""
    variables: dict[str, object] = {}
    activate(PermissionLevel.UNSUPERVISED)

    safe_exec("from math import sqrt", variables)
    result = safe_exec("sqrt(16)", variables)
    assert result == 4
