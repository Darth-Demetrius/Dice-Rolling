SEED = 20260223

INVALID_DICE_CASES: list[str] = [
	"2d",
	"2d6x",
	"2d-1",
	"d-1",
	"abc",
	"2d()",
	"2^^3",
]

ARITHMETIC_CASES: list[tuple[str, object]] = [
	("2+3*4", 14),
	("2^3", 1),
	("2**3", 8),
	("7//3", 2),
	("7%3", 1),
	("1<<3", 8),
	("8>>2", 2),
	("5&3", 1),
	("5|2", 7),
	("~1", -2),
	("1<2", True),
	("2<=2", True),
	("3>4", False),
	("1==1", True),
	("1!=2", True),
	("1 and 0", 0),
	("0 or 5", 5),
	("not 0", True),
]

RANGE_CASES: list[tuple[str, int, int]] = [
	("d20", 1, 20),
	("2d6", 2, 12),
	("-1d6", -6, -1),
	("2d6+3", 5, 15),
	("2**3d2", 8, 16),
	("2d3**2", 2, 18),
]

PRECEDENCE_EQUAL_CASES: list[tuple[str, str]] = [
	("8/2d4", "8/(2d4)"),
	("2d3**2", "2d(3**2)"),
]

PRECEDENCE_DIFFERENT_CASES: list[tuple[str, str]] = [
	("8/2d4", "(8/2)d4"),
	("2d3**2", "(2d3)**2"),
]

RANDOMNESS_CASES: list[str] = ["d6", "2d6", "2d6+3"]

# Extra valid expressions not otherwise covered by the test case tables.
ADDITIONAL_VALID_CASES: list[str] = [
	"1d20",
	" 3D8 ",
	"d20",
	"0d0",
	"10d(10*10)",
	"2*3d4",
	"(2+1)d4",
	"d6+2",
]

VALID_DICE_CASES: list[str] = list(
	dict.fromkeys(
		ADDITIONAL_VALID_CASES
		+ [expression for expression, _ in ARITHMETIC_CASES]
		+ [expression for expression, _, _ in RANGE_CASES]
		+ [left for left, _ in PRECEDENCE_EQUAL_CASES]
		+ [right for _, right in PRECEDENCE_EQUAL_CASES]
		+ [left for left, _ in PRECEDENCE_DIFFERENT_CASES]
		+ [right for _, right in PRECEDENCE_DIFFERENT_CASES]
		+ RANDOMNESS_CASES
	)
)
