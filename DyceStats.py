from __future__ import annotations

from collections.abc import Callable, Iterator
from enum import StrEnum
from typing import TypeAlias
import warnings

import numpy as np
from dyce.h import H
from dyce.p import P


DiceSpec: TypeAlias = dict[int, int] | tuple[int, int] | list["DiceSpec"] | int
CheckSpec: TypeAlias = tuple["DyceStats | DiceSpec"] | tuple["DyceStats | DiceSpec", float]


class Mode(StrEnum):
    """How integer multiplication should behave for a distribution."""

    TIMES = "times"
    SCALE = "scale"


class DyceStats:
    """Dice distribution wrapper built on top of ``dyce.H``.

    Core state:
    - ``_h``: the actual distribution
    - ``_dice``: the dice-spec representation used for explainability
    - ``_mode``: multiplication mode (`times` vs `scale`)

    ``_dice`` can drift from ``_h`` after non-dice transforms (e.g. scalar scaling).
    Use ``is_dice_equivalent``/``is_modified`` to check whether they still match.
    """

    def __init__(
        self,
        *,
        h: H | None = None,
        dice: dict[int, int] | None = None,
        mode: str | Mode = Mode.TIMES,
    ) -> None:
        self._h = h if h is not None else H({})
        self._dice: dict[int, int] = dict(dice) if dice is not None else {}
        self._mode: Mode = Mode.TIMES
        self.set_mode(mode)

    @classmethod
    def from_dice(cls, *specs: DyceStats | DiceSpec, mode: str | Mode = Mode.TIMES) -> "DyceStats":
        """Build a distribution from dice-style inputs."""
        return cls(mode=mode).add_dice(*specs)

    @staticmethod
    def _to_int_outcome(outcome: object) -> int:
        if isinstance(outcome, int):
            return outcome
        if isinstance(outcome, float) and outcome.is_integer():
            return int(outcome)
        raise TypeError(f"Non-integer outcome {outcome!r} is not supported")

    @staticmethod
    def _normalize_die_map(die: dict[int, int]) -> dict[int, int]:
        (sides, count), = die.items()

        if sides == 0 or count == 0:
            warnings.warn(
                f"Rolling 0 dice or a die with 0 sides does nothing. Ignoring {count}d{sides}."
            )
            return {1: 0}

        if sides != 1 and (count < 0 or sides == -1):
            return {-sides: -count}

        return die

    @staticmethod
    def parse_dice(*specs: DyceStats | DiceSpec) -> Iterator[DyceStats | dict[int, int]]:
        """Yield normalized dice components.

        Outputs are either:
        - ``DyceStats`` instances
        - normalized one-entry ``{sides: count}`` maps
        """
        queue = list(specs)
        idx = 0

        while idx < len(queue):
            spec = queue[idx]
            idx += 1

            if isinstance(spec, DyceStats):
                yield spec
                continue

            if isinstance(spec, dict):
                for raw_sides, raw_count in spec.items():
                    if not isinstance(raw_sides, int) or not isinstance(raw_count, int):
                        warnings.warn(
                            f"{{{raw_sides}: {raw_count}}} of type "
                            f"{{{type(raw_sides).__name__}: {type(raw_count).__name__}}} "
                            f"is not valid (must be {{int: int}}). Ignoring this entry."
                        )
                        continue
                    sides: int = raw_sides
                    count: int = raw_count
                    yield DyceStats._normalize_die_map({sides: count})
                continue

            if isinstance(spec, tuple):
                if len(spec) != 2:
                    warnings.warn(
                        f"Tuple {spec} has length {len(spec)}, but must be (count, sides). Ignoring."
                    )
                    continue

                count, sides = spec
                if not isinstance(count, int) or not isinstance(sides, int):
                    warnings.warn(
                        f"Tuple {spec} of type ({type(count).__name__}, {type(sides).__name__}) "
                        f"is not valid (must be (int, int)). Ignoring."
                    )
                    continue

                yield DyceStats._normalize_die_map({sides: count})
                continue

            if isinstance(spec, list):
                queue[idx:idx] = list(spec)
                continue

            if isinstance(spec, int):
                if idx < len(queue):
                    next_spec = queue[idx]
                else:
                    next_spec = None

                if isinstance(next_spec, int):
                    count = int(spec)
                    sides = next_spec
                    idx += 1
                    yield DyceStats._normalize_die_map({sides: count})
                else:
                    yield {1: spec}
                continue

            warnings.warn(f"Argument of type {type(spec).__name__} is not valid die input. Ignoring.")

    @staticmethod
    def _die_histogram(sides: int, count: int) -> H:
        """Create a histogram for ``count`` rolls of one die type."""
        if count == 0:
            return H({})

        if sides == 1:
            return H({count: 1})  # pyright: ignore[reportArgumentType]

        if count < 0:
            sides = -sides
            count = -count

        single = H(abs(sides))
        if sides < 0:
            single = -single

        return (count @ P(single)).h()

    @staticmethod
    def _h_from_dice_dict(dice: dict[int, int]) -> H:
        total = H({})
        for sides, count in dice.items():
            total = total + DyceStats._die_histogram(sides, count)
        return total

    def _probability_where(self, predicate: Callable[[int], bool]) -> float:
        return sum(
            float(p)
            for outcome, p in self._h.distribution(lambda n, d: n / d)
            if predicate(self._to_int_outcome(outcome))
        )

    def is_dice_equivalent(self) -> bool:
        """Whether ``_h`` still matches the exact distribution implied by ``_dice``."""
        return self._h == self._h_from_dice_dict(self._dice)

    def is_modified(self) -> bool:
        """Inverse of ``is_dice_equivalent`` for readability."""
        return not self.is_dice_equivalent()

    def copy(self) -> "DyceStats":
        return DyceStats(h=self._h, dice=self._dice, mode=self._mode)

    def set_mode(self, mode: str | Mode) -> "DyceStats":
        try:
            self._mode = Mode(mode)
        except ValueError:
            warnings.warn(
                f"Invalid mode '{mode}' provided. Mode must be 'times' or 'scale'. "
                f"Keeping current mode '{self._mode}'."
            )
        return self

    def get_mode(self) -> Mode:
        return self._mode

    def get_dice(self) -> dict[int, int]:
        return self._dice.copy()

    def get_distribution(self) -> dict[int, float]:
        return {
            self._to_int_outcome(outcome): float(p)
            for outcome, p in self._h.distribution(lambda n, d: n / d)
        }

    def get_mass(self) -> int:
        return int(self._h.total)

    def get_min(self) -> int:
        return min(self._to_int_outcome(outcome) for outcome in self._h.outcomes())

    def get_max(self) -> int:
        return max(self._to_int_outcome(outcome) for outcome in self._h.outcomes())

    def get_avg(self) -> float:
        return float(self._h.mean())

    def get_var(self) -> float:
        return float(self._h.variance())

    def get_sigma(self) -> float:
        return float(self._h.stdev())

    def add_dice(self, *specs: DyceStats | DiceSpec) -> "DyceStats":
        for parsed in self.parse_dice(*specs):
            if isinstance(parsed, DyceStats):
                self._h = self._h + parsed._h
                for sides, count in parsed._dice.items():
                    self._dice[sides] = self._dice.get(sides, 0) + count
            else:
                (sides, count), = parsed.items()
                self._h = self._h + self._die_histogram(sides, count)
                self._dice[sides] = self._dice.get(sides, 0) + count
        return self

    @staticmethod
    def sum(*specs: DyceStats | DiceSpec) -> "DyceStats":
        return DyceStats.from_dice(*specs)

    def _reset_identity(self) -> None:
        self._h = H({})
        self._dice = {}

    def i_scalar_multiply(self, scalar: int) -> "DyceStats":
        if scalar == 0:
            self._reset_identity()
            return self

        self._h = self._h.umap(lambda outcome: outcome * scalar)
        return self

    @staticmethod
    def scalar_multiply(roll: "DyceStats", scalar: int) -> "DyceStats":
        return roll.copy().i_scalar_multiply(scalar)

    def i_times(self, count: int) -> "DyceStats":
        if count == 0:
            self._reset_identity()
            return self

        base_h = self._h if count > 0 else (-self)._h
        self._h = (abs(count) @ P(base_h)).h()
        return self

    @staticmethod
    def times(roll: "DyceStats", count: int) -> "DyceStats":
        return roll.copy().i_times(count)

    def _multiply_by_int(self, scalar: int, *, in_place: bool):
        if self._mode == Mode.TIMES:
            return self.i_times(scalar) if in_place else self.times(self, scalar)
        if self._mode == Mode.SCALE:
            return self.i_scalar_multiply(scalar) if in_place else self.scalar_multiply(self, scalar)
        return NotImplemented

    def roll(self, count: int = 1) -> np.ndarray:
        if not isinstance(count, int):
            return NotImplemented
        if count < 0:
            warnings.warn("Negative roll count requested; returning empty array.")
            return np.array([], dtype=np.int64)
        return np.asarray([self._h.roll() for _ in range(count)], dtype=np.int64)

    def conditional_roll(self, checks: list[CheckSpec]) -> "DyceStats":
        """Build a weighted mixture based on thresholded outcomes of this distribution."""
        outputs: list[DyceStats] = []
        thresholds: list[float] = []

        for output_spec, *threshold_spec in checks:
            out = output_spec if isinstance(output_spec, DyceStats) else DyceStats.from_dice(output_spec)
            threshold = float(threshold_spec[0]) if threshold_spec else -np.inf
            outputs.append(out)
            thresholds.append(threshold)

        threshold_arr = np.asarray(thresholds, dtype=float)
        if not np.all(threshold_arr[:-1] <= threshold_arr[1:]):
            warnings.warn("checks not in ascending threshold order; sorting.")
            order = np.argsort(threshold_arr)
            outputs = [outputs[i] for i in order]
            threshold_arr = threshold_arr[order]

        branch_weights = np.zeros(len(outputs), dtype=np.int64)
        for outcome, weight in self._h.items():
            outcome_int = self._to_int_outcome(outcome)
            idx = int(np.searchsorted(threshold_arr, outcome_int, side="right") - 1)
            if idx >= 0:
                branch_weights[idx] += int(weight)

        if not np.any(branch_weights):
            return DyceStats()

        result_weights: dict[int, int] = {}
        for idx in np.flatnonzero(branch_weights):
            branch_weight = int(branch_weights[idx])
            for outcome, weight in outputs[idx]._h.items():
                int_weight = int(weight)
                if int_weight == 0:
                    continue
                outcome_int = self._to_int_outcome(outcome)
                result_weights[outcome_int] = result_weights.get(outcome_int, 0) + int_weight * branch_weight

        return DyceStats(h=H(result_weights))  # pyright: ignore[reportArgumentType]

    def __add__(self, other):
        return self.sum(self, other)

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        return self.add_dice(other)

    def __sub__(self, other):
        return self.sum(self, -other)

    def __rsub__(self, other):
        return self.sum(other, -self)

    def __isub__(self, other):
        return self.add_dice(-other)

    def __mul__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return self._multiply_by_int(other, in_place=False)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __imul__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return self._multiply_by_int(other, in_place=True)

    def __matmul__(self, count):
        return self.roll(count)

    def __rmatmul__(self, count):
        return self.__matmul__(count)

    def __neg__(self):
        neg_dice: dict[int, int] = {}
        for sides, count in self._dice.items():
            if sides == 1:
                neg_dice[1] = neg_dice.get(1, 0) - count
            else:
                neg_dice[-sides] = neg_dice.get(-sides, 0) + count

        neg_dice = {sides: count for sides, count in neg_dice.items() if count != 0}
        if not neg_dice:
            neg_dice = {1: 0}

        return DyceStats(h=-self._h, dice=neg_dice, mode=self._mode)

    def __pos__(self):
        return self

    def __len__(self):
        return len(self._h)

    def __float__(self):
        return self.get_avg()

    def __int__(self):
        return int(np.ceil(float(self)))

    def __trunc__(self):
        return int(float(self))

    def __floor__(self):
        return self.get_min()

    def __ceil__(self):
        return self.get_max()

    def __round__(self, direction="down"):
        if isinstance(direction, str):
            lead = direction[:1].lower()
            if lead == "d":
                direction = -1
            elif lead == "u":
                direction = 1
            else:
                direction = 0

        if direction < 0:
            return self.__trunc__()
        if direction > 0:
            return self.__int__()
        return float(self)

    def __lt__(self, other):
        if isinstance(other, int):
            if self.get_max() < other:
                return 1
            if self.get_min() >= other:
                return 0
            return self._probability_where(lambda outcome: outcome < other)

        if isinstance(other, DyceStats):
            if self.get_max() < other.get_min():
                return 1
            if self.get_min() >= other.get_max():
                return 0
            return NotImplemented

        return NotImplemented

    def __le__(self, other):
        if isinstance(other, int):
            return self.__lt__(other + 1)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, int):
            lt_or_not = self.__lt__(other + 1)
            if lt_or_not is NotImplemented:
                return NotImplemented
            return 1 - lt_or_not
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, int):
            lt_or_not = self.__lt__(other)
            if lt_or_not is NotImplemented:
                return NotImplemented
            return 1 - lt_or_not
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, int):
            if other < self.get_min() or other > self.get_max():
                return 0
            return self._probability_where(lambda outcome: outcome == other)
        return NotImplemented

    def __ne__(self, other):  # type: ignore
        eq_or_not = self.__eq__(other)
        if eq_or_not is NotImplemented:
            return NotImplemented
        return 1 - eq_or_not

    def __str__(self):
        return self.text()

    def __repr__(self):
        return (
            f"DyceStats(avg={self.get_avg()}, dice={self._dice}, mass={self.get_mass()}, "
            f"min={self.get_min()}, max={self.get_max()}, var={self.get_var()})"
        )

    def min_txt(self):
        return f"Minimum: {self.get_min()}"

    def max_txt(self):
        return f"Maximum: {self.get_max()}"

    def mean_txt(self):
        return f"Average: {self.get_avg()}"

    def var_txt(self):
        return f"Variance: {self.get_var()}"

    def std_txt(self):
        return f"Standard deviation: {self.get_sigma()}"

    def dice_txt(self):
        return f"Dice: {self.get_dice()}"

    def dist_txt(self):
        return f"Distribution (outcome -> probability):\n{self.get_distribution()}"

    def mass_txt(self):
        return f"Number of possibilities: {self.get_mass()}"

    def text(self):
        return f"{self.min_txt()}\n> {self.max_txt()}\n> {self.mean_txt()}\n> {self.std_txt()}"

    def print(self, before: str = "", after: str = ""):
        print(before + self.text() + after)


DieStats = DyceStats
