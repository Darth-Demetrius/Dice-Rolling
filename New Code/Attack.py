from __future__ import annotations

from collections import defaultdict
from typing import Any

import MyDyce
d = MyDyce.H


class Attack(MyDyce.R):
    """Attack roller storing check and outcomes in annotated ``sources``."""

    CHECK_ANNOTATION = "check"
    EFFECT_ANNOTATIONS = ("crit_failure", "failure", "success", "crit_success")
    UNTYPED_DAMAGE = "untyped"
    OUTCOME_SLOT_PRIORITY = {
        "crit_failure": ("crit_failure", "failure"),
        "failure": ("failure",),
        "success": ("success",),
        "crit_success": ("crit_success", "success"),
    }
    EFFECT_SLOTS_BY_LENGTH = {
        0: (),
        1: ("success",),
        2: ("failure", "success"),
        3: ("failure", "success", "crit_success"),
        4: EFFECT_ANNOTATIONS,
    }

    # ----- Construction -----

    def __init__(
        self,
        name: str = "",
        check_expression: MyDyce._RollLike = d(20),
        effect_expressions: MyDyce._OrderedRollLikes = (d(6),),
    ) -> None:
        check = self._to_roller(check_expression).annotate(self.CHECK_ANNOTATION)
        annotated_effects = self._build_annotated_effect_sources(list(effect_expressions))

        super().__init__(sources=(check, *annotated_effects), annotation=name)

    # ----- Properties -----

    @property
    def name(self) -> str:
        return self.annotation

    @name.setter
    def name(self, value: str) -> None:
        self._annotation = value

    @property
    def check(self):
        for source in self.sources:
            if source.annotation == self.CHECK_ANNOTATION:
                return source
        raise ValueError("Attack has no check source")

    @check.setter
    def check(self, expression: MyDyce._RollLike | MyDyce._RollLikes) -> None:
        check = self._to_roller(expression).annotate(self.CHECK_ANNOTATION)
        slots = self.effects
        effect_sources = [
            slots[slot]
            for slot in self.EFFECT_ANNOTATIONS
            if slot in slots
        ]
        self._sources = (check, *effect_sources)

    @property
    def effects(self) -> dict[str, MyDyce._R]:
        return {
            source.annotation: source
            for source in self.sources
            if source.annotation in self.EFFECT_ANNOTATIONS
        }

    @effects.setter
    def effects(self, value: dict[str, MyDyce._R] | MyDyce._OrderedRollLikes) -> None:
        match value:
            case dict():
                effect_sources = [value[slot] for slot in self.EFFECT_ANNOTATIONS if slot in value]
                self._sources = (self.check, *effect_sources)
            case list() | tuple() as items:
                annotated_effects = self._build_annotated_effect_sources(list(items))
                self._sources = (self.check, *annotated_effects)

    def get_effect_for_outcome(self, outcome: str) -> MyDyce._R | None:
        effects = self.effects  # cache
        return effects.get(outcome, effects.get(outcome[5:]))  # fallback strips "crit_" prefix

    def get_effect_as_dict(self, outcome: str) -> dict[str, list[MyDyce._R]]:
        effect = self.get_effect_for_outcome(outcome)
        if isinstance(effect, MyDyce.R):
            return effect._to_dict(self.UNTYPED_DAMAGE)
        if effect is None:
            return {}
        return {self.UNTYPED_DAMAGE: [effect]}

    # ----- Normalization Helpers -----

    @staticmethod
    def _to_roller(expression: MyDyce._RollLike | MyDyce._RollLikes) -> MyDyce._R:
        match expression:
            case MyDyce.R():
                return expression
            case int() | MyDyce.H() | MyDyce.P():
                return MyDyce.R.from_value(expression)
            case dict() as mapping:
                if not mapping:
                    raise ValueError("Roll expression dict cannot be empty")
                return MyDyce.R.from_sources(*(Attack._to_roller(value) for value in mapping.values()))
            case list() | tuple() | set() as items:
                if not items:
                    raise ValueError("Roll expression iterable cannot be empty")
                return MyDyce.R.from_sources(*(Attack._to_roller(value) for value in items))
            case _:
                raise TypeError(f"Unsupported roll expression type: {type(expression).__name__}")

    @classmethod
    def _collection_to_typed_rollers(cls, expression: MyDyce._RollLike | MyDyce._RollLikes) -> list[MyDyce._R]:
        match expression:
            case dict() as mapping:
                return [
                    cls._to_roller(roll_expression).annotate(damage_type)
                    for damage_type, roll_expression in mapping.items()
                ]
            case list() | set() | tuple() as items:
                return [
                    cls._to_roller(roll_expression).annotate(cls.UNTYPED_DAMAGE)
                    for roll_expression in items
                ]
            case _:
                return [cls._to_roller(expression).annotate(cls.UNTYPED_DAMAGE)]

    @classmethod
    def _build_annotated_effect_sources(
        cls,
        effect_expressions: list[MyDyce._RollLike | MyDyce._RollLikes],
    ) -> list[MyDyce._R]:
        slot_names = cls.EFFECT_SLOTS_BY_LENGTH[len(effect_expressions)]
        sources: list[MyDyce._R] = []
        for slot, expression in zip(slot_names, effect_expressions):
            typed_children = cls._collection_to_typed_rollers(expression)
            combined = MyDyce.R.from_sources(*typed_children)
            sources.append(combined.annotate(slot))
        return sources

    # ----- Outcome Selection -----

    @staticmethod
    def _roll_total(roller: MyDyce._R) -> int:
        return int(float(roller.roll().total()))

    # ----- Public API -----

    def roll(self):
        """Return the attack check roll for this attack."""
        return self.check.roll()

    def roll_check_total(self) -> int:
        return self._roll_total(self.check)

    def roll_damage_total(self) -> int:
        return sum(self._roll_total(effect) for effect in self.effects.values())

    @staticmethod
    def _outcome_from_check(check_total: int, target: int, crit_margin: int) -> str:
        match check_total:
            case n if n >= target + crit_margin:
                return "crit_success"
            case n if n >= target:
                return "success"
            case n if n <= target - crit_margin:
                return "crit_failure"
            case _:
                return "failure"

    def roll_effect_total(self, outcome: str) -> int:
        return sum(self.roll_effect_breakdown(outcome).values())

    def roll_effect_breakdown(self, outcome: str) -> dict[str, int]:
        # TODO: Add effect_sources_by_type(outcome) helper to expose selected child rolls pre-roll.
        typed_effects = self.get_effect_as_dict(outcome)
        breakdown: dict[str, int] = {}
        for damage_type, rollers in typed_effects.items():
            breakdown[damage_type] = sum(self._roll_total(roller) for roller in rollers)
        return breakdown

    def resolve(
        self,
        target: int,
        *,
        crit_margin: int = 10,
    ) -> dict[str, Any]:
        """Resolve one attack roll against a target value."""
        check_total = self.roll_check_total()

        outcome = self._outcome_from_check(check_total, target, crit_margin)
        damage_by_type = self.roll_effect_breakdown(outcome)
        damage = sum(damage_by_type.values())

        return {
            "name": self.name,
            "check": check_total,
            "target": target,
            "outcome": outcome,
            "damage": damage,
            "damage_by_type": damage_by_type,
            "effect_count": len(self.effects),
        }

    def get_stats(
        self,
        target: int,
        *,
        crit_margin: int = 10,
        samples: int = 10_000,
    ) -> dict[str, float | int | str]:
        """Estimate resolved damage stats with Monte Carlo sampling."""
        if samples <= 0:
            raise ValueError("samples must be > 0")

        values = [
            self.roll_effect_total(
                self._outcome_from_check(self.roll_check_total(), target, crit_margin)
            )
            for _ in range(samples)
        ]

        return {
            "name": self.name,
            "min": min(values),
            "max": max(values),
            "average": sum(values) / len(values),
            "samples": samples,
        }

    def __str__(self) -> str:
        check_repr = str(self.check)
        parts: list[str] = []
        for outcome in self.EFFECT_ANNOTATIONS:
            typed = self.get_effect_as_dict(outcome)
            if not typed:
                continue
            type_parts = []
            for damage_type, rollers in typed.items():
                type_total = MyDyce.R.from_sources(*rollers)
                type_parts.append(f"{damage_type}={type_total}")
            parts.append(f"{outcome}: " + ", ".join(type_parts))
        damage_repr = " | ".join(parts)
        if self.name:
            return f"{self.name}: [{check_repr}] -> {damage_repr}"
        return f"[{check_repr}] -> {damage_repr}"
