from __future__ import annotations

from typing import Any

from .h import H
from .p import P


class R:
    def __init__(self, sources: tuple[R, ...] = (), annotation: Any = "", **kw: Any) -> None: ...

    @property
    def annotation(self) -> Any: ...

    @property
    def sources(self) -> tuple[R, ...]: ...

    @classmethod
    def from_sources(cls, *sources: R, annotation: Any = "") -> R: ...

    @classmethod
    def from_value(cls, value: int | H | P, annotation: Any = "") -> R: ...

    def annotate(self, annotation: Any = "") -> R: ...
    def roll(self) -> Any: ...
