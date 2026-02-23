import pyparsing as pp
pp.show_best_practices()
ppc = pp.common


integer = ppc.integer
signed_integer = ppc.signed_integer
d_symbol = pp.CaselessLiteral("d").suppress()
dice_expr = (
	pp.StringStart()
	- pp.Optional(signed_integer, default=1)("count")
	- d_symbol
	- integer("sides")
	- pp.StringEnd()
).set_name("dice_expression")


VALID_DICE_CASES: list[tuple[str, tuple[int, int]]] = [
	("1d20", (1, 20)),
	("2d6", (2, 6)),
	(" 3D8 ", (3, 8)),
	("d20", (1, 20)),
	("0d0", (0, 0)),
	("-1d6", (-1, 6)),
	("10d100", (10, 100)),
]

INVALID_DICE_CASES: list[str] = [
	"2d",
	"2d6x",
	"2d-1",
	"d-1",
	"abc",
]


def parse_dice(expression: str) -> tuple[int, int]:
	"""Parse basic dice notation like '1d20' or '2d6'."""
	try:
		parsed = dice_expr.parse_string(expression, parse_all=True)
	except pp.ParseException as exc:
		raise ValueError(f"Invalid dice expression: {expression!r}") from exc

	count = parsed.get("count")
	sides = parsed.get("sides")
	if not isinstance(count, int) or not isinstance(sides, int):
		raise ValueError(f"Invalid dice expression: {expression!r}")

	if sides < 0:
		raise ValueError("Dice sides must be a non-negative integer")

	return count, sides


def run_parser_self_tests() -> bool:
	"""Run quick parser checks using pyparsing's run_tests helper."""
	valid_tests = "# valid dice expressions\n" + "\n".join(expression for expression, _ in VALID_DICE_CASES)
	invalid_tests = "# invalid dice expressions\n" + "\n".join(INVALID_DICE_CASES)

	print("run_tests: valid inputs")
	valid_ok, _ = dice_expr.run_tests(valid_tests, parse_all=True)

	print("\nrun_tests: invalid inputs (expected failures)")
	invalid_ok, _ = dice_expr.run_tests(
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
	test_inputs = [expression for expression, _ in VALID_DICE_CASES] + INVALID_DICE_CASES

	for text in test_inputs:
		try:
			result = parse_dice(text)
			print(f"{text!r} -> {result}")
		except ValueError as exc:
			print(f"{text!r} -> error: {exc}")
