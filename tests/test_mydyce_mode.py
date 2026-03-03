from dyce.h import H

import MyDyce


def test_mode_times_swaps_mul_and_matmul_both_directions() -> None:
    base = H(6)
    mine = MyDyce.MyH(6)

    MyDyce.set_mode_times()

    assert mine * 2 == base @ 2
    assert mine @ 2 == base * 2
    assert 2 * mine == 2 @ base
    assert 2 @ mine == 2 * base


def test_mode_scale_matches_dyce_defaults_both_directions() -> None:
    base = H(6)
    mine = MyDyce.MyH(6)

    MyDyce.set_mode_scale()

    assert mine * 2 == base * 2
    assert mine @ 2 == base @ 2
    assert 2 * mine == 2 * base
    assert 2 @ mine == 2 @ base
