import pyparsing as pp
from random import random
from typing import Any

from parser_test_cases import INVALID_DICE_CASES, VALID_DICE_CASES

pp.show_best_practices()
pp.ParserElement.enable_packrat()
ppc = pp.common

integer = ppc.integer
true_kw = pp.Keyword("True").set_parse_action(pp.replace_with(True))
false_kw = pp.Keyword("False").set_parse_action(pp.replace_with(False))
operand_atom = integer | true_kw | false_kw


def _unwrap_value(value: object) -> object:
	if isinstance(value, pp.ParseResults) and len(value) == 1:
		return _unwrap_value(value[0])
	return value


def _require_int(value: object, label: str) -> int:
	if not isinstance(value, int):
		raise TypeError(f"{label} must be an integer")
	return value


def _op_name(operator: object) -> str:
	if isinstance(operator, pp.ParseResults):
		return " ".join(str(part).lower() for part in operator)
	return str(operator).lower()


def _roll_die(sides: int) -> int:
	if sides < 0:
		raise ValueError("Dice sides must be a non-negative integer")
	return int(random() * sides) + 1

def _apply_unary(tokens: pp.ParseResults) -> int:
	items = tokens[0]
	operator = _op_name(items[0])
	operand_value: Any = _unwrap_value(items[1])
	match operator:
		case "+":
			return +operand_value
		case "-":
			return -operand_value
		case "~":
			return ~operand_value
		case "not":
			return not operand_value
		case "d":
			return _roll_die(_require_int(operand_value, "dice sides"))
		case _:
			raise ValueError(f"Unsupported unary operator: {operator!r}")


def _apply_binary(tokens: pp.ParseResults) -> Any:
	items = tokens[0]
	result: Any = _unwrap_value(items[0])

	comparison_ops = {"<", "<=", ">", ">=", "==", "!=", "in", "not in", "is", "is not"}
	item_operators = [_op_name(operator) for operator in items[1::2]]
	if item_operators and all(operator in comparison_ops for operator in item_operators):
		left: Any = _unwrap_value(items[0])
		for operator, operand in zip(items[1::2], items[2::2]):
			right: Any = _unwrap_value(operand)
			op = _op_name(operator)
			match op:
				case "<":
					is_true = left < right
				case "<=":
					is_true = left <= right
				case ">":
					is_true = left > right
				case ">=":
					is_true = left >= right
				case "==":
					is_true = left == right
				case "!=":
					is_true = left != right
				case "in":
					is_true = left in right
				case "not in":
					is_true = left not in right
				case "is":
					is_true = left is right
				case "is not":
					is_true = left is not right
				case _:
					raise ValueError(f"Unsupported comparison operator: {operator!r}")
			if not is_true:
				return False
			left = right
		return True

	for operator, operand in zip(items[1::2], items[2::2]):
		right: Any = _unwrap_value(operand)
		op = _op_name(operator)
		match op:
			case "**":
				result = result ** right
			case "d":
				count = _require_int(result, "dice count")
				sides = _require_int(right, "dice sides")
				if count == 0:
					result = 0
				elif count > 0:
					result = sum(_roll_die(sides) for _ in range(count))
				else:
					result = -sum(_roll_die(sides) for _ in range(-count))
			case "*":
				result = result * right
			case "/":
				result = result / right
			case "//":
				result = result // right
			case "%":
				result = result % right
			case "+":
				result = result + right
			case "-":
				result = result - right
			case "<<":
				result = result << right
			case ">>":
				result = result >> right
			case "&":
				result = result & right
			case "^":
				result = result ^ right
			case "|":
				result = result | right
			case "and":
				result = result and right
			case "or":
				result = result or right
			case _:
				raise ValueError(f"Unsupported binary operator: {operator!r}")
	return result


is_not_operator = pp.Keyword("is") + pp.Keyword("not")
not_in_operator = pp.Keyword("not") + pp.Keyword("in")
comparison_operator = (
	is_not_operator
	| not_in_operator
	| pp.one_of("< <= > >= == != in is", as_keyword=True)
)


expression_grammar = pp.infix_notation(
	operand_atom,
	[
		(pp.CaselessLiteral("d"), 1, pp.OpAssoc.RIGHT, _apply_unary),
		(pp.one_of("+ - ~"), 1, pp.OpAssoc.RIGHT, _apply_unary),
		(pp.Literal("**"), 2, pp.OpAssoc.RIGHT, _apply_binary),
		(pp.CaselessLiteral("d"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.one_of("// * / %"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.one_of("+ -"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.one_of("<< >>"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.Literal("&"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.Literal("^"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.Literal("|"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(comparison_operator, 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.Keyword("not"), 1, pp.OpAssoc.RIGHT, _apply_unary),
		(pp.Keyword("and"), 2, pp.OpAssoc.LEFT, _apply_binary),
		(pp.Keyword("or"), 2, pp.OpAssoc.LEFT, _apply_binary),
	],
).set_name("dice_arithmetic_expression")

def parse_dice(expression: str) -> object:
	"""Parse and evaluate dice arithmetic."""
	try:
		parsed = expression_grammar.parse_string(expression, parse_all=True)
		value = parsed[0]
	except (pp.ParseException, ValueError) as exc:
		raise ValueError(f"Invalid dice expression: {expression!r}") from exc
	return value


def run_parser_self_tests() -> bool:
	"""Run quick parser checks using pyparsing's run_tests helper."""
	valid_tests = "# valid dice expressions\n" + "\n".join(VALID_DICE_CASES)
	invalid_tests = "# invalid dice expressions\n" + "\n".join(INVALID_DICE_CASES)

	print("run_tests: valid inputs")
	valid_ok, _ = expression_grammar.run_tests(valid_tests, parse_all=True)

	print("\nrun_tests: invalid inputs (expected failures)")
	invalid_ok, _ = expression_grammar.run_tests(
		invalid_tests,
		parse_all=True,
		failure_tests=True,
	)

	return bool(valid_ok and invalid_ok)


if __name__ == "__main__":
	print("== pyparsing run_tests ==")
	all_ok = run_parser_self_tests()
	print(f"run_tests passed: {all_ok}\n")

	print("== parse_dice sample calls ==")
	test_inputs = VALID_DICE_CASES + INVALID_DICE_CASES

	for text in test_inputs:
		try:
			result = parse_dice(text)
			print(f"{text!r} -> {result}")
		except ValueError as exc:
			print(f"{text!r} -> error: {exc}")
