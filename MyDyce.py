
from enum import Enum, auto

from numerary.types import RealLike
from numerary.bt import beartype
from dyce.h import (
    H,
    _OperandT,
    SupportsInt
)

class MyH(H):
    def __init__(self, items) -> None:
        super().__init__(items)

    @beartype
    def __mul__(self, other: _OperandT | SupportsInt) -> "H":
        if is_mode_times():
            return super(MyH, self).__matmul__(other)
        return super(MyH, self).__mul__(other)

    @beartype
    def __rmul__(self, other: RealLike | SupportsInt) -> "H":
        if is_mode_times():
            return super(MyH, self).__matmul__(other)
        return super(MyH, self).__rmul__(other)

    @beartype
    def __matmul__(self, other: _OperandT | SupportsInt) -> "H":
        if is_mode_times():
            return super(MyH, self).__mul__(other)
        return super(MyH, self).__matmul__(other)

    @beartype
    def __rmatmul__(self, other: RealLike | SupportsInt) -> "H":
        if is_mode_times():
            return super(MyH, self).__rmul__(other)
        return super(MyH, self).__matmul__(other)



class _Mode(Enum):
    """How multiplication should behave for a distribution.
    SCALE: Use dyce's default behavior for `*` and `@` (`*` = scale)
    TIMES: Swap dyce's default behavior for `*` and `@` (`*` = repeat)
    """
    SCALE = auto()
    TIMES = auto()

def mode() -> _Mode:
    return _mode

def set_mode_times():
    global _mode
    _mode = _Mode.TIMES

def set_mode_scale():
    global _mode
    _mode = _Mode.SCALE

def is_mode_times() -> bool:
    return _mode == _Mode.TIMES

def is_mode_scale() -> bool:
    return _mode == _Mode.SCALE

set_mode_times()
