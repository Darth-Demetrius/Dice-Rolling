import pytest

from parser import INVALID_DICE_CASES, VALID_DICE_CASES, parse_dice


@pytest.mark.parametrize(
    ("expression", "expected"),
    VALID_DICE_CASES,
)
def test_parse_dice_valid(expression: str, expected: tuple[int, int]) -> None:
    assert parse_dice(expression) == expected


@pytest.mark.parametrize(
    "expression",
    INVALID_DICE_CASES,
)
def test_parse_dice_invalid(expression: str) -> None:
    with pytest.raises(ValueError):
        parse_dice(expression)
