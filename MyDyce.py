
from enum import Enum, auto
from typing import Any, Iterable, Literal, TypeAlias, Union, cast
from itertools import groupby
from collections import defaultdict

from numerary.bt import beartype
import dyce
from dyce.h import SupportsInt

__all__ = (
    "H",
    "P",
    "R",
    "_H",
    "_P",
    "_R",
    "_RollLike",
    "_RollLikes",
    "_OrderedRollLikes",
    "set_print_mode",
)

_H: TypeAlias = dyce.h.H
_P: TypeAlias = dyce.p.P
_R: TypeAlias = dyce.r.R

_RollLike: TypeAlias = SupportsInt | _H | _P | _R
_RollLikes: TypeAlias = dict[str, _RollLike] | list[_RollLike] | set[_RollLike] | tuple[_RollLike, ...]

_OrderedRollLikes: TypeAlias = list[_RollLike | _RollLikes] | tuple[_RollLike | _RollLikes, ...]

class H(dyce.h.H):
    def __str__(self) -> str:
        # Check if the histogram is of the form [count]d[sides]
        if count := next(iter(self._h), None):
            sides = (len(self._h)+count-1)/count
            if sides.is_integer() and self == count@H(sides):
                return f"{int(count)}d{int(sides)}"

        return dict.__repr__(self._h)

    def __repr__(self) -> str:
        global _print_mode
        if _print_mode != _PrintMode.PRETTY:
            return super().__repr__()
        return f"{type(self).__name__}({str(self)})"


class P(dyce.p.P):
    def __str__(self) -> str:
        group_counters: dict[H, int] = {}

        for h, hs in groupby(cast(Iterable[H], self)):
            n = sum(1 for _ in hs)
            group_counters[h] = n

        def _n_at(h: H, n: int) -> str:
            x, d, y = str(h).partition("d")
            try:
                if int(x) == 1:
                    return f"{n}d{y}"
            except ValueError:
                pass

            return f"{n}@{str(h)}"

        if len(group_counters) == 1:
            h = next(iter(group_counters))
            return _n_at(h, group_counters[h])
        else:
            args = ", ".join(_n_at(h, n) for h, n in group_counters.items())
            return f"{args}"


    def __repr__(self) -> str:
        global _print_mode
        if _print_mode != _PrintMode.PRETTY:
            return super().__repr__()
        return f"{type(self).__name__}({str(self)})"

    def __add__(self, other: SupportsInt | "P" | H) -> "P":
        return P(self, other)
    def __radd__(self, other: SupportsInt | "P" | H) -> "P":
        return P(self, other)

    def __sub__(self, other: SupportsInt | "P" | H) -> "P":
        return P(self, -other)  # type: ignore
    def __rsub__(self, other: SupportsInt | "P" | H) -> "P":
        return P(-self, other)  # type: ignore


class R(dyce.r.R):
    def _to_dict(self, default_annotation: str = "") -> dict[str, list[_R]]:
        grouped: dict[str, list[_R]] = defaultdict(list)
        for source in self.sources:
            grouped[source.annotation or default_annotation].append(source)
            # This may fail if source.annotation does not exist
            # TODO: require annotations on all nodes, or confirm that this fallback method won't error
        return dict(grouped)

    def deep_to_dict(self, default_annotation: str = "") -> dict[str, Any]:
        dictionary: dict[str, Any] = {}
        for source in self.sources:
            annotation = source.annotation or default_annotation
            if isinstance(source, R):
                source = source.deep_to_dict(default_annotation)
            if annotation in dictionary:
                if isinstance(dictionary[annotation], list):
                    dictionary[annotation].append(source)
                else:
                    dictionary[annotation] = [dictionary[annotation], source]
            else:
                dictionary[annotation] = source
        return dictionary


def _apply_monkeypatches() -> None:
    # Keep dyce module symbols aligned with local subclasses.
    setattr(dyce.h, "H", H)
    setattr(dyce.p, "H", H)
    setattr(dyce.p, "P", P)
    setattr(dyce.r, "H", H)
    setattr(dyce.r, "P", P)
    setattr(dyce.r, "R", R)
    setattr(dyce, "H", H)
    setattr(dyce, "P", P)
    setattr(dyce, "R", R)


_apply_monkeypatches()


class _PrintMode(Enum):
    """Mode of printing."""
    DEFAULT = auto()
    PRETTY  = auto()

_print_mode = _PrintMode.PRETTY

PrintModeName: TypeAlias = Literal["default", "pretty"]

def set_print_mode(mode: PrintModeName | _PrintMode) -> None:
    r"Set the print mode."
    global _print_mode
    if isinstance(mode, _PrintMode):
        _print_mode = mode
        return

    _print_mode = _PrintMode[mode.upper()]
