"""Safe REPL with tiered permission levels for restricted code execution.

Features:
- Four permission levels: MINIMUM, LIMITED, PERMISSIVE, UNSUPERVISED
- Safe operators: arithmetic, boolean, comparison, bitwise
- Assignments: names, unpacking, subscript/slice on existing variables
- Control flow: if/elif/else, for/while loops, break/continue, comprehensions
- Math functions: auto-imported via 'from math import *' (disable with --import "")
- String/list/dict/set methods on literals and imported modules
- Runtime limits: per-input wall-clock timeouts by permission level
- Memory limits: per-input soft caps by permission level
- Security: blocks dunder/private attributes, eval, exec, and unsafe builtins
"""

import argparse
import ast
import builtins
from enum import IntEnum
import importlib
import signal
import sys
import tracemalloc
from typing import cast
import warnings


_ACTIVE_PERMS: "Permissions | None" = None


# Core functions available at all levels
_CORE_FUNCTIONS = {
    "abs", "round", "min", "max", "sum", "pow", "divmod",  # Math
    "int", "float", "str", "bool",  # Type conversion
    "chr", "ord", "hex", "oct", "bin",  # Character/numeric conversions
}

# Collection and iteration functions (added at LIMITED and above)
_COLLECTION_FUNCTIONS = {
    "list", "tuple", "dict", "set", "bytes", "bytearray", "frozenset",
    "len", "range", "enumerate", "zip", "reversed", "sorted", "iter", "next",
}

# Predicate and introspection functions (added at LIMITED and above)
_UTILITY_FUNCTIONS = {"all", "any", "isinstance", "type", "repr", "ascii", "format", "slice"}

# Functional programming (added at LIMITED and above)
_FUNCTIONAL_FUNCTIONS = {"map", "filter"}

# Core nodes available at all levels
_CORE_NODES = {
    # Module structure
    ast.Module, ast.Expression, ast.Expr,
    # Data structures and literals
    ast.Constant, ast.Tuple, ast.List, ast.Set, ast.Dict,
    # Names, references, and scoping
    ast.Name, ast.Load, ast.Store,
    # Access and containment
    ast.Subscript, ast.Slice, ast.Attribute,
    # Assignment operations
    ast.Assign, ast.AugAssign,
    # Function calls and arguments
    ast.Call, ast.keyword,
    # Unpacking and starred expressions
    ast.Starred,
    # Operators: binary, unary, boolean, comparison
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    # Operator base classes
    ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
    # Expressions: conditional and walrus
    ast.IfExp, ast.NamedExpr,
    # Control flow: conditionals and assertions
    ast.If, ast.Assert,
}

# Loop and comprehension nodes (added at LIMITED and above)
_ITERATION_NODES = {
    ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension, ast.Lambda, ast.arguments, ast.arg,
}

# Function definition nodes (added at LIMITED and above)
_FUNCTION_DEF_NODES = {ast.FunctionDef, ast.Return}

# Class definition nodes (added at PERMISSIVE and above)
_CLASS_NODES = {ast.ClassDef}

# Scope control nodes (added at PERMISSIVE and above)
_SCOPE_NODES = {ast.Global, ast.Nonlocal}

# Exception handling nodes (added at PERMISSIVE only)
_EXCEPTION_NODES = {ast.Try, ast.Raise, ast.With, ast.ExceptHandler}

# Import nodes (added at UNSUPERVISED only)
_IMPORT_NODES = {ast.Import, ast.ImportFrom, ast.alias}


# Builtin allow/deny sets by level
_ALLOWED_SYMBOLS_MINIMUM = _CORE_FUNCTIONS
_ALLOWED_SYMBOLS_LIMITED = _ALLOWED_SYMBOLS_MINIMUM | _COLLECTION_FUNCTIONS | _UTILITY_FUNCTIONS | _FUNCTIONAL_FUNCTIONS
_ALLOWED_SYMBOLS_PERMISSIVE = _ALLOWED_SYMBOLS_LIMITED
_ALLOWED_SYMBOLS_UNSUPERVISED = set(dir(builtins))
_MEMORY_LIMIT_INFINITY = 2**63 - 1

_BLOCKED_SYMBOLS_UNSUPERVISED = {"breakpoint", "compile", "eval", "exec"}
_BLOCKED_SYMBOLS_PERMISSIVE = _BLOCKED_SYMBOLS_UNSUPERVISED | {
    "__import__", "delattr", "getattr", "globals", "input", "locals",
    "memoryview", "open", "setattr", "vars",
}
_BLOCKED_SYMBOLS_LIMITED = _BLOCKED_SYMBOLS_PERMISSIVE
_BLOCKED_SYMBOLS_MINIMUM = _BLOCKED_SYMBOLS_PERMISSIVE

_ALLOWED_NODES_MINIMUM = _CORE_NODES
_ALLOWED_NODES_LIMITED = _ALLOWED_NODES_MINIMUM | _ITERATION_NODES | _FUNCTION_DEF_NODES
_ALLOWED_NODES_PERMISSIVE = _ALLOWED_NODES_LIMITED | _EXCEPTION_NODES | _CLASS_NODES | _SCOPE_NODES
_ALLOWED_NODES_UNSUPERVISED = _ALLOWED_NODES_PERMISSIVE | _IMPORT_NODES

class PermissionLevel(IntEnum):
    """Permission levels ordered from most restrictive to most permissive.
    
    Design invariants (DO NOT BREAK):
    - Level 0 must always be the MOST RESTRICTIVE level (used as fallback for invalid input)
    - Level[-1] (last enum member) must always be the LEAST RESTRICTIVE level
    - LIMITED should remain the default for constructor/CLI when no level specified
    - Ordering allows numeric comparisons: level >= LIMITED means "at least limited permissions"
    
    These invariants allow adding new permission levels without refactoring fallback/default logic.
    """
    MINIMUM = 0      # Arithmetic and basic control flow only
    LIMITED = 1      # Adds loops, comprehensions, lambda, def, collections, map/filter
    PERMISSIVE = 2   # Adds exception handling and classes
    UNSUPERVISED = 3 # Allows imports and most builtins

    @classmethod
    def coerce(cls, value: "PermissionLevel | str | int | None") -> "PermissionLevel":
        """Convert enum, string, or integer to PermissionLevel. Warns and defaults to MINIMUM on invalid input."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls[value.strip().upper()]
            except KeyError:
                pass
        try:
            return cls(int(value))  # type: ignore
        except (TypeError, ValueError):
            pass

        valid = ", ".join(f"{level.value} ({level.name})" for level in cls)
        warnings.warn(
            f"Invalid permission level {value}. Use one of: {valid}. Defaulting to {cls(0).name}.",
            stacklevel=2,
        )
        return cls(0)


class Permissions:
    """Permission levels with optional customization.
    
    Invariants:
    - Tuples indexed by PermissionLevel: 0 (most restrictive) to -1 (least restrictive)
    - Default level is LIMITED
    
    Usage:
        perms = Permissions(base=LIMITED)
        perms = Permissions(base=LIMITED, allow_functions={'map'})
    """

    # Indexed by PermissionLevel (0=MINIMUM, 1=LIMITED, 2=PERMISSIVE, 3=UNSUPERVISED)
    ALLOWED_SYMBOLS_BY_LEVEL = (
        _ALLOWED_SYMBOLS_MINIMUM,
        _ALLOWED_SYMBOLS_LIMITED,
        _ALLOWED_SYMBOLS_PERMISSIVE,
        _ALLOWED_SYMBOLS_UNSUPERVISED,
    )

    ALLOWED_NODES_BY_LEVEL = (
        _ALLOWED_NODES_MINIMUM,
        _ALLOWED_NODES_LIMITED,
        _ALLOWED_NODES_PERMISSIVE,
        _ALLOWED_NODES_UNSUPERVISED,
    )

    # Nodes blocked at each level
    BLOCKED_NODES_BY_LEVEL = (
        {ast.Attribute},  # MINIMUM: no attribute access at all
        set(),            # LIMITED: allow attributes on literals only
        set(),            # PERMISSIVE: allow attributes on literals only
        set(),            # UNSUPERVISED: allow attributes on any non-private receiver
    )

    BLOCKED_SYMBOLS_BY_LEVEL = (
        _BLOCKED_SYMBOLS_MINIMUM,
        _BLOCKED_SYMBOLS_LIMITED,
        _BLOCKED_SYMBOLS_PERMISSIVE,
        _BLOCKED_SYMBOLS_UNSUPERVISED,
    )

    TIMEOUT_SECONDS_BY_LEVEL: tuple[float, float, float, float] = (
        0.1,
        0.5,
        10.0,
        float("inf"),
    )

    MEMORY_LIMIT_BYTES_BY_LEVEL: tuple[int, int, int, int] = (
        64 * 1024 * 1024,
        256 * 1024 * 1024,
        _MEMORY_LIMIT_INFINITY,
        _MEMORY_LIMIT_INFINITY,
    )

    def __init__(
        self,
        base_perms: PermissionLevel,
        allow_symbols: set[str],
        block_symbols: set[str],
        allow_nodes: set[type[ast.AST]],
        block_nodes: set[type[ast.AST]],
        imports: dict[str, object],
    ):
        self.level = base_perms
        self.modified = bool(allow_symbols or block_symbols or allow_nodes or block_nodes)

        blocked_symbols = self.BLOCKED_SYMBOLS_BY_LEVEL[self.level] | block_symbols
        self.allowed_symbols = (self.ALLOWED_SYMBOLS_BY_LEVEL[self.level] | allow_symbols) - blocked_symbols
        if self.level >= PermissionLevel.PERMISSIVE:
            self.allowed_symbols.add("__build_class__")  # Required for class definitions
        self.imported_symbols = set(imports.keys()) - blocked_symbols
        self.allowed_symbols |= self.imported_symbols

        self.globals_dict: dict[str, object] = {
            "__builtins__": {
                name: getattr(builtins, name)
                for name in self.allowed_symbols
                if hasattr(builtins, name)
            }
        }
        self.globals_dict["__name__"] = "__safe_repl__"
        self.globals_dict.update({name: obj for name, obj in imports.items() if name not in blocked_symbols})

        self.allowed_nodes = ((self.ALLOWED_NODES_BY_LEVEL[self.level] | allow_nodes)
                             -(self.BLOCKED_NODES_BY_LEVEL[self.level] | block_nodes))
        self.allowed_node_tuple = tuple(self.allowed_nodes)

    def __str__(self) -> str:
        name = self.level.name.lower() + (" (custom)" if self.modified else "")
        if not self.imported_symbols:
            return name
        if len(self.imported_symbols) <= 3:
            return f"{name} with imports: {', '.join(self.imported_symbols)}"
        return f"{name} with {len(self.imported_symbols)} imports"


def set_active_permissions(perms: Permissions) -> None:
    """Set the module-level permissions used by safe_exec/repl defaults."""
    global _ACTIVE_PERMS
    _ACTIVE_PERMS = perms


def set_timeout_seconds(level: PermissionLevel, seconds: float) -> None:
    """Override timeout seconds for a permission level."""
    timeouts = list(Permissions.TIMEOUT_SECONDS_BY_LEVEL)
    timeouts[level] = seconds
    Permissions.TIMEOUT_SECONDS_BY_LEVEL = cast(tuple[float, float, float, float], tuple(timeouts))


def set_memory_limit_bytes(level: PermissionLevel, bytes_limit: int) -> None:
    """Override memory limit in bytes for a permission level."""
    limits = list(Permissions.MEMORY_LIMIT_BYTES_BY_LEVEL)
    limits[level] = bytes_limit
    Permissions.MEMORY_LIMIT_BYTES_BY_LEVEL = cast(tuple[int, int, int, int], tuple(limits))


def _get_active_permissions() -> Permissions:
    if _ACTIVE_PERMS is None:
        raise RuntimeError("Active permissions are not set. Call set_active_permissions().")
    return _ACTIVE_PERMS


def _extract_root_name(node: ast.expr) -> str | None:
    """Extract root variable name from subscript chain (e.g., arr[0][1] -> 'arr')."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_literal_value(node: ast.expr) -> bool:
    """Check if node is a literal value (constant, list, dict, etc.)."""
    return isinstance(node, (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set))


def _can_access_attribute(node: ast.expr) -> bool:
    """Check if attribute access is safe for this permission level.
    
    At MINIMUM: no attribute access allowed.
    At LIMITED/PERMISSIVE: allowed on literals and imported modules (e.g., "hello".upper(),
    math.sqrt(), [1,2,3].append()). Disallows on user variables to prevent probing.
    At UNSUPERVISED: allowed on any non-private receiver.
    """
    perms = _get_active_permissions()
    if perms.level >= PermissionLevel.UNSUPERVISED:
        return True
    if perms.level < PermissionLevel.LIMITED:
        return False  # MINIMUM: complete attribute access ban
    # LIMITED/PERMISSIVE: allow on literals and imported symbols
    return _is_literal_value(node) or (isinstance(node, ast.Name) and node.id in perms.imported_symbols)


def _is_unsafe_attribute(attr: str) -> bool:
    """Check if attribute is unsafe (private/dunder)."""
    return attr.startswith("_")


def _validate_assignment_target(target: ast.expr, user_vars: dict[str, object]) -> None:
    """Validate assignment target is safe (names, unpacking, or subscripts on existing variables).
    
    MINIMUM mode: Disallow unpacking assignments for extra safety.
    All levels: Subscript assignment only on existing variables.
    """
    perms = _get_active_permissions()
    if isinstance(target, ast.Name):
        return

    if isinstance(target, (ast.Tuple, ast.List)):
        if perms.level < PermissionLevel.LIMITED:
            raise ValueError("Unpacking assignment is not allowed in MINIMUM mode.")
        for element in target.elts:
            actual_target = element.value if isinstance(element, ast.Starred) else element
            _validate_assignment_target(actual_target, user_vars)
        return

    if isinstance(target, ast.Subscript):
        root = _extract_root_name(target)
        if root and root in user_vars:
            return
        raise ValueError("Subscript/slice assignment is only allowed on existing user variables.")

    raise ValueError("Unsupported assignment target.")


def _validate_call(call: ast.Call, allowed_names: set[str]) -> None:
    """Validate function/method call is safe."""
    perms = _get_active_permissions()
    func = call.func

    if isinstance(func, ast.Name):
        if func.id not in perms.allowed_symbols and func.id not in allowed_names:
            raise ValueError(f"Function '{func.id}' is not allowed.")
    elif isinstance(func, ast.Lambda):
        pass  # Lambda calls are safe
    elif isinstance(func, ast.Attribute):
        if _is_unsafe_attribute(func.attr):
            raise ValueError("Private methods are not allowed.")
        if not _can_access_attribute(func.value):
            raise ValueError("Attribute access not allowed at this permission level.")
    else:
        raise ValueError("Unsupported call target.")


def _validate_ast(tree: ast.AST, user_vars: dict[str, object], allowed_names: set[str]) -> None:
    """Walk AST and validate all nodes against security policy."""
    perms = _get_active_permissions()
    defined_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    allowed_names |= defined_names

    for node in ast.walk(tree):
        if not isinstance(node, perms.allowed_node_tuple):
            raise ValueError("Unsupported syntax.")

        if isinstance(node, ast.Name) and node.id == "__builtins__":
            raise ValueError("Unsupported identifier.")

        if isinstance(node, ast.Attribute):
            if _is_unsafe_attribute(node.attr):
                raise ValueError("Private attributes are not allowed.")
            if not _can_access_attribute(node.value):
                raise ValueError("Attribute access not allowed at this permission level.")

        if isinstance(node, ast.Assign):
            for target in node.targets:
                _validate_assignment_target(target, user_vars)
        elif isinstance(node, ast.AugAssign):
            _validate_assignment_target(node.target, user_vars)
        elif isinstance(node, ast.Call):
            _validate_call(node, allowed_names)


def safe_exec(
    code: str,
    user_vars: dict[str, object],
) -> object | None:
    """Execute code safely. Returns expression value or None."""
    perms = _get_active_permissions()
    global_scope = perms.globals_dict
    timeout_seconds = Permissions.TIMEOUT_SECONDS_BY_LEVEL[perms.level]
    memory_limit = Permissions.MEMORY_LIMIT_BYTES_BY_LEVEL[perms.level]
    memory_limit_active = memory_limit < _MEMORY_LIMIT_INFINITY
    trace_started = False
    # Build set of allowed names from user variables and global scope
    allowed_names = set(user_vars.keys())
    for name, value in global_scope.items():
        if name != "__builtins__":
            allowed_names.update(value.keys() if isinstance(value, dict) else {name})  # type: ignore[union-attr]

    if memory_limit_active:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            trace_started = True
        tracemalloc.reset_peak()

    previous_handler = None
    previous_timer = None
    if timeout_seconds < float("inf"):
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)

        def _handle_timeout(signum, frame):  # type: ignore[unused-argument]
            raise TimeoutError("Execution timed out.")

        signal.signal(signal.SIGALRM, _handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)

    try:
        tree = ast.parse(code, mode="exec")
        _validate_ast(tree, user_vars, allowed_names)

        # Single expression: evaluate and return result
        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
            expr = ast.Expression(tree.body[0].value)
            ast.fix_missing_locations(expr)
            result = eval(compile(expr, "<safe_repl>", "eval"), global_scope, user_vars)
        else:
            # Statement(s): execute without return
            exec(compile(tree, "<safe_repl>", "exec"), global_scope, user_vars)
            result = None

        if memory_limit_active:
            _, peak = tracemalloc.get_traced_memory()
            if peak > memory_limit:
                raise RuntimeError("Memory limit exceeded.")
        return result
    finally:
        if previous_timer is not None:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        if previous_handler is not None:
            signal.signal(signal.SIGALRM, previous_handler)
        if trace_started:
            tracemalloc.stop()


def repl() -> None:
    """Run interactive REPL with safe evaluator."""
    perms = _get_active_permissions()
    print(f"Safe REPL ({perms})")
    print(f"  Builtins: {', '.join(sorted(perms.globals_dict['__builtins__'].keys()))}")  # type: ignore
    print(f"  Nodes: {', '.join(sorted(n.__name__ for n in perms.allowed_nodes))}")
    if perms.imported_symbols:
        print(f"  Imports: {', '.join(sorted(perms.imported_symbols))}")
    print("Type 'quit' to exit.")

    user_vars: dict[str, object] = {}
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("", "Bye")
            break

        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            print("Bye")
            break

        try:
            result = safe_exec(line, user_vars)
            if result is not None:
                print(result)
        except Exception as e:
            print(f"Error: {e}")


def _parse_import_spec(spec: str) -> dict[str, object]:
    """Parse and execute import specification.
    
    Formats: 'module', 'module as alias', 'module:name', 'module:name as alias', 'module:*'
    """
    spec = spec.strip()
    try:
        if ":" in spec:
            module_name, import_names = spec.split(":", 1)
            module = importlib.import_module(module_name.strip())
            import_names = import_names.strip()

            if import_names == "*":
                return {name: obj for name, obj in vars(module).items() if not name.startswith("_")}

            result = {}
            for item in import_names.split(","):
                item = item.strip()
                if " as " in item:
                    original_name, alias = item.split(" as ", 1)
                    result[alias.strip()] = getattr(module, original_name.strip())
                else:
                    result[item] = getattr(module, item)
            return result

        if " as " in spec:
            module_name, alias = spec.split(" as ", 1)
            return {alias.strip(): importlib.import_module(module_name.strip())}

        module = importlib.import_module(spec)
        top_level_name = spec.split(".")[0]
        return {top_level_name: sys.modules[top_level_name]}
    except Exception as e:
        print(f"Failed to import '{spec}': {e}", file=sys.stderr)
        sys.exit(1)


def _validate_cli_args(args) -> None:
    """Validate CLI arguments and convert node names to types. Exit on error."""
    for node_list in (args.allow_nodes, args.block_nodes):
        if node_list:
            for i, node_name in enumerate(node_list):
                if not hasattr(ast, node_name):
                    print(f"Unknown node type: {node_name}", file=sys.stderr)
                    sys.exit(1)
                node_list[i] = getattr(ast, node_name)


def main() -> None:
    """Parse CLI arguments and launch REPL."""
    parser = argparse.ArgumentParser(
        description="Safe REPL with restricted execution context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                               # Limited permission level (default)
  %(prog)s --level MINIMUM               # Restrict to arithmetic only
  %(prog)s --level PERMISSIVE            # Allow classes and exception handling
  %(prog)s --level UNSUPERVISED          # Allow imports and most builtins
  %(prog)s --allow-functions map filter  # Add functions to default set
  %(prog)s --list-functions              # Show allowed functions and exit
        """,
    )

    parser.add_argument("--level", default="LIMITED",
                        help="Permission level: MINIMUM/0, LIMITED/1 (default), PERMISSIVE/2, UNSUPERVISED/3")
    parser.add_argument("--import", dest="imports", action="append", metavar="SPEC",
                        help="Import library (bypasses AST validation) \n'module', 'module as alias', 'module:name', or 'module:*' are valid \nuse a comma-separated list for multiple imports \nany use of this argument will disable auto-import of math module, (use --import \"\" to disable auto-import without adding any imports)")
    parser.add_argument("--allow-functions", nargs="+", help="Add builtin functions")
    parser.add_argument("--block-functions", nargs="+", help="Remove builtin functions")
    parser.add_argument("--allow-nodes", nargs="+", help="Add AST nodes")
    parser.add_argument("--block-nodes", nargs="+", help="Remove AST nodes")
    parser.add_argument("--list-functions", action="store_true", help="Show allowed functions")
    parser.add_argument("--list-nodes", action="store_true", help="Show allowed AST nodes")

    args = parser.parse_args()
    _validate_cli_args(args)

    # Process imports (math:* auto-imported unless --import used)
    imports = {}
    if args.imports:
        import_specs = [spec for spec in args.imports if spec.strip()]
        if import_specs:
            print("Warning: Imported libraries bypass AST validation and have full access.", file=sys.stderr)
            for spec in import_specs:
                imports.update(_parse_import_spec(spec))
    else:
        imports = _parse_import_spec("math:*")

    perms = Permissions(
        base_perms=PermissionLevel.coerce(args.level),
        allow_symbols=set(args.allow_functions) if args.allow_functions else set(),
        block_symbols=set(args.block_functions) if args.block_functions else set(),
        allow_nodes=set(args.allow_nodes) if args.allow_nodes else set(),
        block_nodes=set(args.block_nodes) if args.block_nodes else set(),
        imports=imports,
    )
    set_active_permissions(perms)

    if args.list_functions:
        print("Allowed functions:")
        for name in sorted(perms.globals_dict["__builtins__"].keys()): # type: ignore
            print(f"  {name}")
        return

    if args.list_nodes:
        print("Allowed AST nodes:")
        for node in sorted(perms.allowed_nodes, key=lambda n: n.__name__):
            print(f"  {node.__name__}")
        return

    repl()


if __name__ == "__main__":
    main()
