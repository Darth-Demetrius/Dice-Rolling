"""Safe REPL with tiered permission levels for restricted code execution.

Features:
- Three permission levels: EXTENDED (exception handling), STANDARD (loops,
  comprehensions, lambda, map/filter), RESTRICTED (arithmetic and basic control flow only)
- Safe operators: arithmetic, boolean, comparison, bitwise
- Assignments: names, unpacking, subscript/slice on existing variables
- Control flow: if/elif/else, for/while loops, break/continue, comprehensions
- Math functions: auto-imported via 'from math import *' (disable with --import "")
- String/list/dict/set methods on literals and user variables
- Security: blocks dunder/private attributes, eval, exec, and unsafe builtins
"""

import argparse
import ast
import builtins
from enum import IntEnum
import importlib
import sys
import warnings


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

# Functional programming (added at STANDARD and above)
_FUNCTIONAL_FUNCTIONS = {"map", "filter"}

# Blocked across all levels
_BLOCKED_FUNCTIONS = {
    "eval", "exec", "compile", "open", "globals", "locals", "breakpoint",
    "memoryview", "setattr", "delattr",
}

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

class PermissionLevel(IntEnum):
    """Permission levels ordered from most restrictive to most permissive.
    
    Design invariants (DO NOT BREAK):
    - Level 0 must always be the MOST RESTRICTIVE level (used as fallback for invalid input)
    - Level[-1] (last enum member) must always be the LEAST RESTRICTIVE level
    - STANDARD should remain the default for constructor/CLI when no level specified
    - Ordering allows numeric comparisons: level >= STANDARD means "at least standard permissions"
    
    These invariants allow adding new permission levels without refactoring fallback/default logic.
    """
    RESTRICTED = 0  # Arithmetic and basic control flow only
    STANDARD = 1    # Adds loops, comprehensions, lambda, collections, map/filter
    EXTENDED = 2    # Adds exception handling

    @classmethod
    def coerce(cls, value: "PermissionLevel | str | int") -> "PermissionLevel":
        """Convert enum, string, or integer to PermissionLevel. Warns and defaults to RESTRICTED on invalid input."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls[value.strip().upper()]
            except KeyError:
                pass
        try:
            return cls(int(value))
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
    - Default level is STANDARD
    
    Usage:
        perms = Permissions(base=STANDARD)
        perms = Permissions(base=STANDARD, allow_functions={'map'})
    """

    # Indexed by PermissionLevel (0=RESTRICTED, 1=STANDARD, 2=EXTENDED)
    ALLOWED_FUNCTIONS_BY_LEVEL = (
        _CORE_FUNCTIONS,
        _CORE_FUNCTIONS | _COLLECTION_FUNCTIONS | _UTILITY_FUNCTIONS | _FUNCTIONAL_FUNCTIONS,
        _CORE_FUNCTIONS | _COLLECTION_FUNCTIONS | _UTILITY_FUNCTIONS | _FUNCTIONAL_FUNCTIONS,
    )

    ALLOWED_NODES_BY_LEVEL = (
        _CORE_NODES,
        _CORE_NODES | _ITERATION_NODES,
        _CORE_NODES | _ITERATION_NODES | _EXCEPTION_NODES,
    )

    BLOCKED_NODES_BY_LEVEL = (
        {ast.Attribute},
        set(),
        set(),
    )

    def __init__(
        self,
        base: PermissionLevel | str | int = PermissionLevel.STANDARD,
        allow_functions: set[str] | None = None,
        block_functions: set[str] | None = None,
        allow_nodes: set[str] | None = None,
        block_nodes: set[str] | None = None,
    ):
        self.level = PermissionLevel.coerce(base)
        self.modified = bool(allow_functions or block_functions or allow_nodes or block_nodes)

        self.allowed_functions = self.ALLOWED_FUNCTIONS_BY_LEVEL[self.level] | (allow_functions or set())
        self.allowed_functions -= _BLOCKED_FUNCTIONS | (block_functions or set())
        self.allowed_nodes = self.ALLOWED_NODES_BY_LEVEL[self.level] | {_NODE_NAME_MAP[n] for n in (allow_nodes or set())}
        self.allowed_nodes -= self.BLOCKED_NODES_BY_LEVEL[self.level] | {_NODE_NAME_MAP[n] for n in (block_nodes or set())}
        self.allowed_node_types = tuple(self.allowed_nodes)

    def __str__(self) -> str:
        return self.level.name.lower() + (" (custom)" if self.modified else "")

    def build_custom_globals(self) -> dict[str, object]:
        """Build globals dict with allowed builtins."""
        return {
            "__builtins__": {name: getattr(builtins, name) for name in self.allowed_functions},
        }

# Build lookup tables from most permissive level
_NODE_NAME_MAP = {node.__name__: node for node in Permissions.ALLOWED_NODES_BY_LEVEL[-1]}
_ALLOWED_FUNCTIONS_MAP = {name: getattr(builtins, name) for name in Permissions.ALLOWED_FUNCTIONS_BY_LEVEL[-1]}
SAFE_GLOBALS = {"__builtins__": _ALLOWED_FUNCTIONS_MAP}


def _root_name(node: ast.expr) -> str | None:
    """Extract root variable name from subscript (e.g., arr[0] -> 'arr')."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_unsafe_attribute(attr: str) -> bool:
    """Check if attribute is unsafe (private/dunder)."""
    return attr.startswith("_")


def _validate_assignment_target(target: ast.expr, variables: dict[str, object]) -> None:
    """Validate assignment target is safe (names, unpacking, or subscripts on existing variables)."""
    if isinstance(target, ast.Name):
        return

    if isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _validate_assignment_target(elt.value if isinstance(elt, ast.Starred) else elt, variables)
        return

    if isinstance(target, ast.Subscript):
        root = _root_name(target)
        if root and root in variables:
            return
        raise ValueError("Subscript/slice assignment is only allowed on existing user variables.")

    raise ValueError("Unsupported assignment target.")


def _is_safe_method_receiver(node: ast.expr, variables: dict[str, object], known_names: set[str]) -> bool:
    """Check if node is safe as method call receiver (literals, user variables, or imports)."""
    return (
        isinstance(node, (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set))
        or (isinstance(node, ast.Name) and node.id in known_names)
    )


def _validate_call_target(call: ast.Call, variables: dict[str, object], perms: Permissions, known_names: set[str]) -> None:
    """Validate function/method call target is safe."""
    func = call.func

    if isinstance(func, ast.Name):
        if func.id not in perms.allowed_functions and func.id not in variables and func.id not in known_names:
            raise ValueError(f"Function '{func.id}' is not allowed.")
    elif isinstance(func, ast.Lambda):
        pass  # Lambda calls are safe
    elif isinstance(func, ast.Attribute):
        if _is_unsafe_attribute(func.attr):
            raise ValueError("Private methods are not allowed.")
        if not _is_safe_method_receiver(func.value, variables, known_names):
            raise ValueError("Unsafe method call is not allowed.")
    else:
        raise ValueError("Unsupported call target.")


def _validate(tree: ast.AST, variables: dict[str, object], perms: Permissions, known_names: set[str]) -> None:
    """Walk AST and validate all nodes against security policy."""
    for node in ast.walk(tree):
        if not isinstance(node, perms.allowed_node_types):
            raise ValueError("Unsupported syntax.")

        if isinstance(node, ast.Name) and node.id == "__builtins__":
            raise ValueError("Unsupported identifier.")

        if isinstance(node, ast.Attribute) and _is_unsafe_attribute(node.attr):
            raise ValueError("Unsafe attribute access is not allowed.")

        if isinstance(node, ast.Assign):
            for target in node.targets:
                _validate_assignment_target(target, variables)
        elif isinstance(node, ast.AugAssign):
            _validate_assignment_target(node.target, variables)
        elif isinstance(node, ast.Call):
            _validate_call_target(node, variables, perms, known_names)


def safe_exec(
    line: str,
    variables: dict[str, object],
    perms: Permissions,
    globals_dict: dict[str, object],
) -> object | None:
    """Execute code safely. Returns expression value or None."""

    # Build set of known names from variables and globals (excluding builtins)
    known_names = set(variables.keys())
    for key in globals_dict:
        if key != "__builtins__":
            value = globals_dict[key]
            known_names.update(value.keys() if isinstance(value, dict) else {key})  # type: ignore[union-attr]

    tree = ast.parse(line, mode="exec")
    _validate(tree, variables, perms, known_names)

    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
        expr = ast.Expression(tree.body[0].value)
        ast.fix_missing_locations(expr)
        return eval(compile(expr, "<safe_repl>", "eval"), globals_dict, variables)

    exec(compile(tree, "<safe_repl>", "exec"), globals_dict, variables)


def repl(perms: Permissions, imports: dict[str, object]) -> None:
    """Run interactive REPL with safe evaluator."""
    custom_globals = perms.build_custom_globals()
    if imports:
        custom_globals.update(imports)
    print(f"Safe REPL ({perms})")
    print(f"  Builtins: {', '.join(sorted(perms.allowed_functions))}")
    print(f"  Nodes: {', '.join(sorted(n.__name__ for n in perms.allowed_nodes))}")
    if imports:
        print(f"  Imports: {', '.join(sorted(imports.keys()))}")
    print("Type 'quit' to exit.")

    variables: dict[str, object] = {}
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("", "Bye")
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
        except Exception as e:
            print(f"Error: {e}")


def _process_import(spec: str) -> dict[str, object]:
    """Parse and execute import specification, adding imported names to target dict.
    
    Supported formats:
    - "module" → import module
    - "module as alias" → import module as alias
    - "module.submodule" → import module.submodule (binds 'module')
    - "module:name" → from module import name
    - "module:name as alias" → from module import name as alias
    - "module:name1, name2" → from module import name1, name2
    - "module:*" → from module import *
    """
    spec = spec.strip()
    imported_symbols = {}  # Local dict to hold imported names before merging into target

    try:
        if ":" in spec:
            # from X import Y
            module_name, import_names = spec.split(":", 1)
            module_name = module_name.strip()
            import_names = import_names.strip()

            module = importlib.import_module(module_name)

            if import_names == "*":
                # from X import *
                imported_symbols.update({k: v for k, v in vars(module).items() if not k.startswith("_")})
            else:
                # from X import Y, Z
                for item in import_names.split(","):
                    item = item.strip()
                    if " as " in item:
                        orig_name, alias = item.split(" as ", 1)
                        imported_symbols[alias.strip()] = getattr(module, orig_name.strip())
                    else:
                        imported_symbols[item] = getattr(module, item)
        elif " as " in spec:
            # import X as Y
            module_name, alias = spec.split(" as ", 1)
            module = importlib.import_module(module_name.strip())
            imported_symbols[alias.strip()] = module
        else:
            # import X or import X.Y.Z
            module = importlib.import_module(spec)
            # Bind top-level module name
            name = spec.split(".")[0]
            imported_symbols[name] = sys.modules[name]
        return imported_symbols
    except Exception as e:
        print(f"Failed to import '{spec}': {e}", file=sys.stderr)
        sys.exit(1)


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
  %(prog)s --level EXTENDED             # Allow exception handling
  %(prog)s --allow-functions map filter # Add functions to default set
  %(prog)s --list-functions             # Show allowed functions and exit
        """,
    )

    parser.add_argument("--level", default="STANDARD",
                        help="Permission level: RESTRICTED/0, STANDARD/1 (default), EXTENDED/2")
    parser.add_argument("--import", dest="imports", action="append", metavar="SPEC",
                        help="Import library (bypasses AST validation) \n'module', 'module as alias', 'module:name', or 'module:*' are valid \nuse a comma-separated list for multiple imports \nany use of this argument will disable auto-import of math module, (use --import \"\" to disable auto-import without adding any imports)")
    parser.add_argument("--allow-functions", nargs="+", help="Add builtin functions")
    parser.add_argument("--block-functions", nargs="+", help="Remove builtin functions")
    parser.add_argument("--allow-nodes", nargs="+", help="Add AST nodes")
    parser.add_argument("--block-nodes", nargs="+", help="Remove AST nodes")
    parser.add_argument("--list-functions", action="store_true", help="Show allowed functions")
    parser.add_argument("--list-nodes", action="store_true", help="Show allowed AST nodes")

    args = parser.parse_args()
    _validate_args(args)

    perms = Permissions(
        base=PermissionLevel.coerce(args.level),
        allow_functions=set(args.allow_functions) if args.allow_functions else None,
        block_functions=set(args.block_functions) if args.block_functions else None,
        allow_nodes=set(args.allow_nodes) if args.allow_nodes else None,
        block_nodes=set(args.block_nodes) if args.block_nodes else None,
    )

    # Process imports (from math import * is auto-imported unless --import is used)
    imports = {}
    if args.imports:
        # Filter out empty strings (used to disable auto-import)
        import_specs = [spec for spec in args.imports if spec.strip()]
        if import_specs:
            print("Warning: Imported libraries bypass AST validation and have full access.", file=sys.stderr)
            for spec in import_specs:
                imports = _process_import(spec)
        # If args.imports exists but all are empty, don't auto-import math
    else:
        # Auto-import: from math import *
        imports = _process_import("math:*")

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

    repl(perms, imports)


if __name__ == "__main__":
    main()
