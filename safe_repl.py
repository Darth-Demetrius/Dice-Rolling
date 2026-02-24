"""Safe REPL with tiered permission levels for restricted code execution.

Features:
- Three permission levels: EXTENDED (lambda, exception handling), STANDARD (loops,
  comprehensions), RESTRICTED (arithmetic and basic control flow only)
- Safe operators: arithmetic, boolean, comparison, bitwise
- Assignments: names, unpacking, subscript/slice on existing variables
- Control flow: if/elif/else, for/while loops, break/continue, comprehensions
- Math module: full access to math.* functions
- String/list/dict/set methods on literals and user variables
- Security: blocks dunder/private attributes, eval, exec, and unsafe builtins
"""

import argparse
import ast
import builtins
from enum import Enum
import math
import sys


# ============================================================================
# Configuration: Allowed builtin functions
# ============================================================================

# Core functions available at all levels
_CORE_FUNCTIONS = {
    "abs", "round", "min", "max", "sum", "pow", "divmod",  # Math
    "int", "float", "str", "bool",  # Type conversion
    "chr", "ord", "hex", "oct", "bin",  # Character/numeric conversions
}

# Collection and iteration functions (added at STANDARD and above)
_COLLECTION_FUNCTIONS = {
    "list", "tuple", "dict", "set", "bytes", "bytearray", "frozenset",
    "len", "range", "enumerate", "zip", "reversed", "sorted", "iter", "next",
}

# Predicate and introspection functions (added at STANDARD and above)
_UTILITY_FUNCTIONS = {"all", "any", "isinstance", "type", "repr", "ascii", "format", "slice"}

# Functional programming (added at EXTENDED only)
_FUNCTIONAL_FUNCTIONS = {"map", "filter"}

# Blocked across all levels
_BLOCKED_FUNCTIONS = {
    "eval", "exec", "compile", "open", "globals", "locals", "breakpoint",
    "memoryview", "setattr", "delattr",
}


# ============================================================================
# Configuration: Allowed AST nodes
# ============================================================================

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

# Loop and comprehension nodes (added at STANDARD and above)
_ITERATION_NODES = {
    ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension, ast.Lambda, ast.arguments, ast.arg,
}

# Exception handling nodes (added at EXTENDED only)
_EXCEPTION_NODES = {ast.Try, ast.Raise, ast.With, ast.ExceptHandler}

class PermissionLevel(Enum):
    """Permission levels ordered from most restrictive to most permissive."""
    RESTRICTED = 0  # Arithmetic and basic control flow only
    STANDARD = 1    # Adds loops, comprehensions, collections
    EXTENDED = 2    # Adds lambda, exception handling, functional programming


# Explicit aliases for static analyzers (decorator-based global export is runtime-only).
RESTRICTED = PermissionLevel.RESTRICTED
STANDARD = PermissionLevel.STANDARD
EXTENDED = PermissionLevel.EXTENDED


# Permission level configuration
ALLOWED_FUNCTIONS = {
    RESTRICTED: _CORE_FUNCTIONS,
    STANDARD:   _CORE_FUNCTIONS | _COLLECTION_FUNCTIONS | _UTILITY_FUNCTIONS,
    EXTENDED:   _CORE_FUNCTIONS | _COLLECTION_FUNCTIONS | _UTILITY_FUNCTIONS | _FUNCTIONAL_FUNCTIONS,
}

ALLOWED_NODES = {
    RESTRICTED: _CORE_NODES,
    STANDARD:   _CORE_NODES | _ITERATION_NODES,
    EXTENDED:   _CORE_NODES | _ITERATION_NODES | _EXCEPTION_NODES,
}

BLOCKED_NODES = {
    RESTRICTED: {ast.Attribute},
    STANDARD:   set(),
    EXTENDED:   set(),
}

class Permissions:
    """Permission levels with optional customization.
    
    Three base tiers: EXTENDED (most permissive) -> STANDARD (default) -> RESTRICTED (most restrictive)
    
    Usage:
        # Use predefined level
        perms = Permissions(base=STANDARD)
        safe_exec(code, vars, perms)
        
        # Customize a level
        perms = Permissions(base=STANDARD, allow_functions={'map', 'filter'})
        safe_exec(code, vars, perms)
    """

    def __init__(
        self,
        base: str = "STANDARD",
        allow_functions: set[str] | None = None,
        block_functions: set[str] | None = None,
        allow_nodes: set[str] | None = None,
        block_nodes: set[str] | None = None,
    ):
        """Create a Permissions instance."""
        self.level = PermissionLevel[base]
        self.modified = any([allow_functions, block_functions, allow_nodes, block_nodes])

        self.allowed_functions = ALLOWED_FUNCTIONS[self.level] | (allow_functions or set())
        self.allowed_functions -= _BLOCKED_FUNCTIONS | (block_functions or set())
        self.allowed_nodes = ALLOWED_NODES[self.level] | {_NODE_NAME_MAP[n] for n in (allow_nodes or set())}
        self.allowed_nodes -= BLOCKED_NODES[self.level] | {_NODE_NAME_MAP[n] for n in (block_nodes or set())}
        self.allowed_node_types = tuple(self.allowed_nodes)

    def __str__(self) -> str:
        return self.level.name.lower()  # TODO: add "(custom)" suffix if modified, get Enum working as int

    def build_custom_globals(self) -> dict[str, object]:
        """Build globals dict with allowed builtins and math module."""
        return {
            "__builtins__": {name: getattr(builtins, name) for name in self.allowed_functions},
            "math": math,
        }


# Build lookup tables from the most permissive level (EXTENDED)
_NODE_NAME_MAP = {node.__name__: node for node in ALLOWED_NODES[EXTENDED]}
_ALLOWED_FUNCTIONS_MAP = {name: getattr(builtins, name) for name in ALLOWED_FUNCTIONS[EXTENDED]}
SAFE_GLOBALS = {"__builtins__": _ALLOWED_FUNCTIONS_MAP, "math": math}


# ============================================================================
# Validation: Helper functions for checking AST safety
# ============================================================================

def _root_name(node: ast.expr) -> str | None:
    """Extract root variable name from subscript (arr[0] -> "arr") or None if not simple name."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_unsafe_attribute(attr: str) -> bool:
    """Check if attribute access is unsafe (dunder or private)."""
    return attr.startswith("_")


def _validate_assignment_target(target: ast.expr, variables: dict[str, object]) -> None:
    """Validate assignment target is safe (names, unpacking, safe subscripts only)."""
    if isinstance(target, ast.Name):
        return

    if isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _validate_assignment_target(
                elt.value if isinstance(elt, ast.Starred) else elt,
                variables,
            )
        return

    if isinstance(target, ast.Subscript):
        root = _root_name(target)
        if root is None or root not in variables:
            raise ValueError(
                "Subscript/slice assignment is only allowed on existing user variables."
            )
        return

    raise ValueError("Unsupported assignment target.")


def _is_safe_method_receiver(node: ast.expr, variables: dict[str, object]) -> bool:
    """Check if a node is safe as a method call receiver."""
    # Math module is always safe
    if isinstance(node, ast.Name) and node.id == "math":
        return True
    # Literals are safe
    if isinstance(node, (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set)):
        return True
    # User variables are safe
    if isinstance(node, ast.Name) and node.id in variables:
        return True
    return False


def _validate_call_target(
    call: ast.Call,
    variables: dict[str, object],
    perms: Permissions,
) -> None:
    """Validate function/method call target is safe."""
    func = call.func

    # Direct function/variable call: func(...) or var(...)
    if isinstance(func, ast.Name):
        if func.id not in perms.allowed_functions and func.id not in variables:
            raise ValueError(f"Function '{func.id}' is not allowed.")
        return

    # Direct lambda call
    if isinstance(func, ast.Lambda):
        return

    # Method/attribute call: obj.method(...)
    if isinstance(func, ast.Attribute):
        if _is_unsafe_attribute(func.attr):
            raise ValueError("Private methods are not allowed.")
        if not _is_safe_method_receiver(func.value, variables):
            raise ValueError("Unsafe method call is not allowed.")
        return

    raise ValueError("Unsupported call target.")


# ============================================================================
# Validation: Main AST validation pass
# ============================================================================

def _validate(
    tree: ast.AST,
    variables: dict[str, object],
    perms: Permissions,
) -> None:
    """Walk AST and validate all nodes against security policy."""
    allowed_node_types = perms.allowed_node_types

    for node in ast.walk(tree):
        # Check node type is whitelisted
        if not isinstance(node, allowed_node_types):
            raise ValueError("Unsupported syntax.")

        # Block __builtins__ identifier
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            raise ValueError("Unsupported identifier.")

        # Block unsafe attributes
        if isinstance(node, ast.Attribute) and _is_unsafe_attribute(node.attr):
            raise ValueError("Unsafe attribute access is not allowed.")

        # Validate assignment targets
        if isinstance(node, ast.Assign):
            for target in node.targets:
                _validate_assignment_target(target, variables)
        elif isinstance(node, ast.AugAssign):
            _validate_assignment_target(node.target, variables)

        # Validate function calls
        if isinstance(node, ast.Call):
            _validate_call_target(node, variables, perms)


# Main API: safe_exec
# ============================================================================

def safe_exec(
    line: str,
    variables: dict[str, object],
    perms: Permissions,
    globals_dict: dict[str, object] | None = None,
) -> object | None:
    """Execute code safely with restricted context.
    
    Returns: Value of expression if single expression, None otherwise.
    Raises: ValueError if code is unsafe, SyntaxError if invalid, or runtime errors.
    """
    if globals_dict is None:
        globals_dict = SAFE_GLOBALS

    # Parse and validate
    tree = ast.parse(line, mode="exec")
    _validate(tree, variables, perms)

    # Single expression: evaluate and return value
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
        expr = ast.Expression(tree.body[0].value)
        ast.fix_missing_locations(expr)
        return eval(compile(expr, "<safe_repl>", "eval"), globals_dict, variables)

    # Multiple statements: execute without return
    exec(compile(tree, "<safe_repl>", "exec"), globals_dict, variables)


# ============================================================================
# REPL: Interactive loop
# ============================================================================

def repl(perms: Permissions) -> None:
    """Run interactive REPL with safe evaluator."""
    custom_globals = perms.build_custom_globals()

    # Display configuration
    print(f"Safe REPL ({perms})")
    print(f"  Builtins: {', '.join(sorted(perms.allowed_functions))}")
    print(f"  Nodes: {', '.join(sorted(n.__name__ for n in perms.allowed_nodes))}")
    print("Type 'quit' to exit.")

    # Interactive loop
    variables: dict[str, object] = {}
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye")
            break

        if not text:
            continue

        if text.lower() in {"quit", "exit"}:
            print("Bye")
            break

        try:
            result = safe_exec(text, variables, perms, custom_globals)
            if result is not None:
                print(result)
        except Exception as exc:
            print(f"Error: {exc}")


def _validate_args(args) -> None:
    """Validate CLI arguments and exit with error if invalid."""
    for builtin_name in (args.allow_functions or []) + (args.block_functions or []):
        if not hasattr(builtins, builtin_name):
            print(f"Unknown builtin: {builtin_name}", file=sys.stderr)
            sys.exit(1)

    for node_name in (args.allow_nodes or []) + (args.block_nodes or []):
        if node_name not in _NODE_NAME_MAP:
            print(f"Unknown node type: {node_name}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """Parse CLI arguments and launch REPL."""
    parser = argparse.ArgumentParser(
        description="Safe REPL with restricted execution context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                              # Standard permission level (default)
  %(prog)s --level RESTRICTED           # Restrict to arithmetic only
  %(prog)s --level EXTENDED             # Allow lambda and exception handling
  %(prog)s --allow-functions abs round  # Add functions to default set
  %(prog)s --block-functions open eval  # Remove functions from default set
  %(prog)s --list-functions             # Show allowed functions and exit
  %(prog)s --list-nodes                 # Show allowed AST nodes and exit
        """,
    )

    parser.add_argument("--level", type=str, default="STANDARD",
                        help="Permission level: RESTRICTED: 0, STANDARD: 1 (default), EXTENDED: 2")
    parser.add_argument("--allow-functions", nargs="+", help="Add builtin functions to default set")
    parser.add_argument("--block-functions", nargs="+", help="Remove builtin functions from default set")
    parser.add_argument("--allow-nodes", nargs="+", help="Add AST nodes to default set")
    parser.add_argument("--block-nodes", nargs="+", help="Remove AST nodes from default set")
    parser.add_argument("--list-functions", action="store_true", help="Show allowed functions and exit")
    parser.add_argument("--list-nodes", action="store_true", help="Show allowed nodes and exit")

    args = parser.parse_args()
    _validate_args(args)

    # Create permission set
    perms = Permissions(
        base=args.level.upper(),
        allow_functions=set(args.allow_functions) if args.allow_functions else None,
        block_functions=set(args.block_functions) if args.block_functions else None,
        allow_nodes=set(args.allow_nodes) if args.allow_nodes else None,
        block_nodes=set(args.block_nodes) if args.block_nodes else None,
    )

    # Handle info-only options
    if args.list_functions:
        print("Allowed functions:")
        for name in sorted(perms.allowed_functions):
            print(f"  {name}")
        return

    if args.list_nodes:
        print("Allowed AST nodes:")
        for node in sorted(perms.allowed_nodes, key=lambda n: n.__name__):
            print(f"  {node.__name__}")
        return

    # Launch REPL with permission set
    repl(perms)


if __name__ == "__main__":
    main()
