import random

import pytest

from parser import parse_dice
from parser_test_cases import (
    ARITHMETIC_CASES,
    INVALID_DICE_CASES,
    PRECEDENCE_DIFFERENT_CASES,
    PRECEDENCE_EQUAL_CASES,
    RANDOMNESS_CASES,
    RANGE_CASES,
    SEED,
)


def parse_dice_seeded(expression: str, seed: int = SEED) -> int:
    # Seeded checks are deterministic and non-flaky; unlike cross-seed comparisons,
    # they do not assume two arbitrary seeds must produce different totals.
    random.seed(seed)
    return parse_dice(expression)


@pytest.mark.parametrize(
    ("expression", "expected"),
    ARITHMETIC_CASES,
)
def test_parse_dice_arithmetic_deterministic(expression: str, expected: object) -> None:
    assert parse_dice(expression) == expected


@pytest.mark.parametrize(
    ("expression", "minimum", "maximum"),
    RANGE_CASES,
)
def test_parse_dice_random_results_in_range(
    expression: str,
    minimum: int,
    maximum: int,
) -> None:
    result = parse_dice(expression)
    assert minimum <= result <= maximum


@pytest.mark.parametrize(
    "expression",
    INVALID_DICE_CASES,
)
def test_parse_dice_invalid(expression: str) -> None:
    with pytest.raises(ValueError):
        parse_dice(expression)


@pytest.mark.parametrize(("left", "right"), PRECEDENCE_EQUAL_CASES)
def test_seeded_precedence_equal(left: str, right: str) -> None:
    assert parse_dice_seeded(left) == parse_dice_seeded(right)


@pytest.mark.parametrize(("left", "right"), PRECEDENCE_DIFFERENT_CASES)
def test_seeded_precedence_different(left: str, right: str) -> None:
    assert parse_dice_seeded(left) != parse_dice_seeded(right)


@pytest.mark.parametrize("expression", RANDOMNESS_CASES)
def test_seeded_rolls_repeat_for_same_seed(expression: str) -> None:
    assert parse_dice_seeded(expression, seed=7) == parse_dice_seeded(expression, seed=7)
