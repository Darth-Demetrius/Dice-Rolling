from dyce.h import H as DyceH

import MyDyce


def test_h_uses_dyce_default_mul_and_matmul() -> None:
    base = DyceH(6)
    mine = MyDyce.H(6)

    assert mine * 2 == base * 2
    assert mine @ 2 == base @ 2
    assert 2 * mine == 2 * base
    assert 2 @ mine == 2 @ base


def test_exports_h_and_p_types() -> None:
    h = MyDyce.H(6)
    p = MyDyce.P(h, h)

    assert isinstance(h, MyDyce.H)
    assert isinstance(p, MyDyce.P)


def test_h_pretty_string_format_for_common_dice_notation() -> None:
    assert str(MyDyce.H(6)) == "1d6"
    assert str(2 @ MyDyce.H(6)) == "2d6"
