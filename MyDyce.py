
from enum import Enum, auto
from typing import Union
from itertools import groupby
import re

from numerary.types import RealLike
from numerary.bt import beartype
from dyce.h import (
    H as _H,
    _OperandT,
    _SourceT,
    SupportsInt,
)
from dyce.p import (
    P as _P,
)
import dyce.p as _dyce_p

__all__ = (
    "H",
    "P",
)

class H(_H):
    @beartype
    def __init__(self, items: _SourceT) -> None:
        r"Initializer."
        super().__init__(items)

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

_dyce_p.H = H


class P(_P):
    @beartype
    def __init__(self, *args: Union[SupportsInt, "P", H]) -> None:
        r"Initializer."
        super().__init__(*args)

    def __str__(self) -> str:
        group_counters: dict[H, int] = {}

        for h, hs in groupby(self):  # type: ignore
            n = sum(1 for _ in hs)
            group_counters[h] = n

        def _n_at(h: H, n: int) -> str:
            x, d, y = str(h).partition("d")
            try:
                if int(x) == 1:
                    return f"{n}d{y}"
            except:
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

    def __add__(self, other):
        return P(self, other)
    def __radd__(self, other):
        return P(self, other)

    def __sub__(self, other):
        return P(self, -other)
    def __rsub__(self, other):
        return P(-self, other)  # type: ignore


_dyce_p.P = P


class _PrintMode(Enum):
    """Mode of printing."""
    DEFAULT = auto()
    PRETTY  = auto()

_print_mode = _PrintMode.PRETTY
