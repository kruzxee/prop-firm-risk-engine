"""Tests for proportion uncertainty and the gambler's-ruin formula."""

import numpy as np
import pytest

from pfsim.stats import normal_ci, proportion_se, wilson_ci
from pfsim.validation import gamblers_ruin_pass_probability

# --- stats -----------------------------------------------------------------


def test_se_half_with_100_trials():
    assert proportion_se(0.5, 100) == pytest.approx(0.05)


def test_se_zero_at_extremes():
    assert proportion_se(0.0, 50) == 0.0
    assert proportion_se(1.0, 50) == 0.0


def test_se_10k_attempts_is_at_most_half_a_percent():
    assert proportion_se(0.5, 10_000) == pytest.approx(0.005)


def test_normal_ci_symmetric_and_clipped():
    lo, hi = normal_ci(0.5, 100)
    assert lo == pytest.approx(0.5 - 0.098, abs=1e-3)
    assert hi == pytest.approx(0.5 + 0.098, abs=1e-3)
    assert normal_ci(0.01, 10)[0] == 0.0


def test_wilson_zero_of_ten():
    # Known value: Wilson 95% upper bound for 0/10 is about 0.2775
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=1e-4)


def test_wilson_close_to_normal_for_large_n():
    w = wilson_ci(5_000, 10_000)
    n = normal_ci(0.5, 10_000)
    assert w == pytest.approx(n, abs=1e-4)


@pytest.mark.parametrize(
    ("fn", "args"),
    [
        (proportion_se, (0.5, 0)),
        (proportion_se, (1.5, 10)),
        (wilson_ci, (11, 10)),
        (wilson_ci, (-1, 10)),
    ],
)
def test_stats_reject_bad_inputs(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


# --- gambler's ruin ---------------------------------------------------------


def test_fair_game_is_distance_ratio():
    assert gamblers_ruin_pass_probability(0.5, 10, 15) == pytest.approx(0.4)


def test_one_step_each_way_is_just_p():
    assert gamblers_ruin_pass_probability(0.6, 1, 1) == pytest.approx(0.6)


def test_hand_computed_biased_game():
    # p=0.6, a=2, b=1: r=2/3 -> (1-4/9)/(1-8/27) = (5/9)/(19/27) = 15/19
    assert gamblers_ruin_pass_probability(0.6, 2, 1) == pytest.approx(15 / 19)


def test_certain_edges():
    assert gamblers_ruin_pass_probability(0.0, 3, 3) == 0.0
    assert gamblers_ruin_pass_probability(1.0, 3, 3) == 1.0


def test_continuous_near_half():
    near = gamblers_ruin_pass_probability(0.5 + 1e-7, 10, 15)
    assert near == pytest.approx(0.4, abs=1e-4)


def test_symmetry_swapping_sides():
    # P(pass | p, a, b) = 1 - P(pass | 1-p, b, a)
    p, a, b = 0.45, 7, 4
    assert gamblers_ruin_pass_probability(p, a, b) == pytest.approx(
        1 - gamblers_ruin_pass_probability(1 - p, b, a)
    )


def test_formula_matches_brute_force_random_walk():
    """Independent check of the formula itself (not yet of the engine)."""
    p, a, b, n = 0.55, 5, 5, 20_000
    rng = np.random.default_rng(2026)
    passes = 0
    for _ in range(n):
        x = 0
        while -a < x < b:
            x += 1 if rng.random() < p else -1
        passes += x == b
    expected = gamblers_ruin_pass_probability(p, a, b)
    se = np.sqrt(expected * (1 - expected) / n)
    assert abs(passes / n - expected) < 4 * se


@pytest.mark.parametrize("args", [(-0.1, 1, 1), (0.5, 0, 1), (0.5, 1, 0)])
def test_ruin_rejects_bad_inputs(args):
    with pytest.raises(ValueError):
        gamblers_ruin_pass_probability(*args)
