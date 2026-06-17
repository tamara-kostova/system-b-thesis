import pytest
from shared.suppression import suppress, THRESHOLD


def test_exact_threshold_not_suppressed():
    assert suppress(THRESHOLD) == THRESHOLD


def test_below_threshold_suppressed():
    for n in range(0, THRESHOLD):
        assert suppress(n) == "<10", f"expected suppression for count={n}"


def test_above_threshold_not_suppressed():
    for n in [THRESHOLD + 1, 100, 1000, 999999]:
        assert suppress(n) == n


def test_suppression_returns_string_below_threshold():
    assert isinstance(suppress(0), str)
    assert isinstance(suppress(9), str)


def test_suppression_returns_int_at_and_above_threshold():
    assert isinstance(suppress(THRESHOLD), int)
    assert isinstance(suppress(THRESHOLD + 1), int)
