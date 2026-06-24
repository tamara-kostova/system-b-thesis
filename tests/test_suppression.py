from shared.suppression import THRESHOLD, suppress


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


def test_suppression_string_value():
    # The exact string matters — downstream callers check for "<10"
    for n in range(0, THRESHOLD):
        assert suppress(n) == "<10"


def test_zero_suppressed():
    # Zero is a valid query result (no patients match) and must be suppressed
    assert suppress(0) == "<10"


def test_negative_suppressed():
    # Negative counts should not occur in practice but must not leak if they do
    assert suppress(-1) == "<10"
    assert suppress(-100) == "<10"


def test_large_counts_not_suppressed():
    assert suppress(10_000_000) == 10_000_000


def test_threshold_boundary_off_by_one():
    # Classic fence-post: 9 suppressed, 10 not, 11 not
    assert suppress(THRESHOLD - 1) == "<10"
    assert suppress(THRESHOLD) == THRESHOLD
    assert suppress(THRESHOLD + 1) == THRESHOLD + 1


def test_differencing_attack_not_prevented_at_function_level():
    """
    The suppress() function operates on single counts and cannot prevent
    differencing attacks: if count(A OR B) = 15 and count(A) = '<10',
    an attacker can infer count(B) is between 6 and 15.

    This is a known limitation of per-query suppression (documented in
    redteam/adversarial_prompts.md #23). The function is not expected to
    prevent it — this test documents the behaviour explicitly so the
    limitation is acknowledged in the test suite.
    """
    count_a = suppress(7)  # suppressed
    count_a_or_b = suppress(15)  # not suppressed

    assert count_a == "<10"
    assert count_a_or_b == 15
    # An attacker can bound count(B) as [15 - 9, 15 - 0] = [6, 15]
    # Mitigation: linked-count suppression or noise addition (out of scope for this thesis)
