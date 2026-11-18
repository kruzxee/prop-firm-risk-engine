"""Tests for Trade, outcome models, daily counts and the parametric generator."""

import numpy as np
import pytest

from pfsim.trades import (
    DiscreteR,
    FixedCount,
    ParametricGenerator,
    PoissonCount,
    Trade,
    WinRateRR,
    excursions,
)

# --- Trade -----------------------------------------------------------------


def test_trade_accepts_consistent_path():
    Trade(2.0, mfe_r=2.0, mae_r=0.4)
    Trade(-1.0, mfe_r=0.7, mae_r=1.0)
    Trade(0.5)  # path unknown is fine


@pytest.mark.parametrize(
    "kwargs",
    [
        {"r_multiple": -1.5},  # beyond the stop
        {"r_multiple": 2.0, "mfe_r": 1.5},  # closed above its best point
        {"r_multiple": -0.8, "mae_r": 0.5},  # lost more than its worst point
        {"r_multiple": 0.0, "mae_r": -0.1},
        {"r_multiple": 0.0, "mae_r": 1.2},  # heat beyond the stop
        {"r_multiple": 0.0, "mfe_r": -0.1},
    ],
)
def test_trade_rejects_inconsistent_path(kwargs):
    with pytest.raises(ValueError):
        Trade(**kwargs)


# --- outcome models --------------------------------------------------------


def test_win_rate_rr_maps_uniform():
    m = WinRateRR(win_rate=0.4, rr=2.0)
    assert m.r_from_uniform(0.0) == 2.0
    assert m.r_from_uniform(0.399) == 2.0
    assert m.r_from_uniform(0.4) == -1.0
    assert m.r_from_uniform(0.999) == -1.0


def test_higher_win_rate_only_flips_losses_to_wins():
    """Same uniforms, higher win rate: every old win is still a win (CRN property)."""
    u = np.random.default_rng(1).random(1000)
    low, high = WinRateRR(0.4, 2.0), WinRateRR(0.5, 2.0)
    for x in u:
        if low.r_from_uniform(x) > 0:
            assert high.r_from_uniform(x) > 0


@pytest.mark.parametrize(("wr", "rr"), [(-0.1, 2), (1.1, 2), (0.5, 0), (0.5, -1)])
def test_win_rate_rr_rejects_bad_inputs(wr, rr):
    with pytest.raises(ValueError):
        WinRateRR(wr, rr)


def test_discrete_r_maps_uniform_by_cumulative_probability():
    m = DiscreteR(values=(-1.0, 0.0, 2.0), probs=(0.5, 0.1, 0.4))
    assert m.r_from_uniform(0.0) == -1.0
    assert m.r_from_uniform(0.49) == -1.0
    assert m.r_from_uniform(0.5) == 0.0
    assert m.r_from_uniform(0.59) == 0.0
    assert m.r_from_uniform(0.6) == 2.0
    assert m.r_from_uniform(1.0 - 1e-12) == 2.0
    assert m.max_r == 2.0


def test_discrete_r_max_r_is_never_negative():
    assert DiscreteR((-1.0, -0.5), (0.5, 0.5)).max_r == 0.0


@pytest.mark.parametrize(
    ("values", "probs"),
    [
        ((), ()),
        ((1.0,), (0.5, 0.5)),
        ((-1.0, 2.0), (0.5, 0.6)),
        ((-1.0, 2.0), (-0.1, 1.1)),
        ((-2.0, 2.0), (0.5, 0.5)),
    ],
)
def test_discrete_r_rejects_bad_inputs(values, probs):
    with pytest.raises(ValueError):
        DiscreteR(values, probs)


def test_discrete_r_frequencies_match_probabilities():
    m = DiscreteR(values=(-1.0, 1.0, 2.0), probs=(0.5, 0.2, 0.3))
    u = np.random.default_rng(7).random(50_000)
    r = np.array([m.r_from_uniform(x) for x in u])
    for value, p in zip(m.values, m.probs, strict=True):
        freq = np.mean(r == value)
        se = np.sqrt(p * (1 - p) / len(u))
        assert abs(freq - p) < 4 * se


# --- counts ----------------------------------------------------------------


def test_fixed_count():
    assert FixedCount(2).draw(np.random.default_rng(0)) == 2


def test_poisson_count_mean():
    rng = np.random.default_rng(3)
    draws = [PoissonCount(1.5).draw(rng) for _ in range(20_000)]
    assert abs(np.mean(draws) - 1.5) < 4 * np.sqrt(1.5 / 20_000)


@pytest.mark.parametrize("bad", [FixedCount, PoissonCount])
def test_counts_reject_negative(bad):
    with pytest.raises(ValueError):
        bad(-1)


# --- excursions ------------------------------------------------------------


def test_excursion_none_is_straight_line():
    assert excursions(2.0, 2.0, 0.9, 0.9, "none") == (2.0, 0.0)
    assert excursions(-1.0, 2.0, 0.9, 0.9, "none") == (0.0, 1.0)


def test_excursion_uniform_winner_heat_between_zero_and_stop():
    mfe, mae = excursions(2.0, 2.0, u_mae=0.25, u_mfe=0.9, model="uniform")
    assert mfe == 2.0  # a target hit's best point is the target
    assert mae == 0.25  # 25% of the way to the stop


def test_excursion_uniform_loser_runup_between_zero_and_target():
    mfe, mae = excursions(-1.0, 2.0, u_mae=0.9, u_mfe=0.5, model="uniform")
    assert mae == 1.0  # a stop-out's worst point is the stop
    assert mfe == 1.0  # halfway to the 2R target


def test_excursion_unknown_model_raises():
    with pytest.raises(ValueError):
        excursions(1.0, 2.0, 0.5, 0.5, "worst")  # type: ignore[arg-type]


# --- generator -------------------------------------------------------------


def make_gen(excursion="uniform", count=None):
    return ParametricGenerator(WinRateRR(0.45, 2.0), count or FixedCount(2), excursion)


def test_generator_returns_fixed_number_of_valid_trades():
    trades = make_gen().next_day(np.random.default_rng(0))
    assert len(trades) == 2
    assert all(t.r_multiple in (2.0, -1.0) for t in trades)
    assert all(0 <= t.mae_r <= 1 and 0 <= t.mfe_r <= 2 for t in trades)


def test_generator_is_reproducible_from_seed():
    a = [make_gen().next_day(np.random.default_rng(42)) for _ in range(3)]
    b = [make_gen().next_day(np.random.default_rng(42)) for _ in range(3)]
    assert a == b


def test_excursion_model_does_not_change_outcomes():
    """Common random numbers: switching the path model keeps the same R results."""
    rng_a, rng_b = np.random.default_rng(5), np.random.default_rng(5)
    for _ in range(200):
        a = make_gen("none").next_day(rng_a)
        b = make_gen("uniform").next_day(rng_b)
        assert [t.r_multiple for t in a] == [t.r_multiple for t in b]


def test_generator_zero_trade_day():
    assert make_gen(count=FixedCount(0)).next_day(np.random.default_rng(0)) == []


def test_generator_win_rate_matches():
    gen = make_gen(count=FixedCount(1))
    rng = np.random.default_rng(11)
    wins = sum(gen.next_day(rng)[0].r_multiple > 0 for _ in range(20_000))
    p = wins / 20_000
    assert abs(p - 0.45) < 4 * np.sqrt(0.45 * 0.55 / 20_000)


def test_generator_rejects_unknown_excursion():
    with pytest.raises(ValueError):
        make_gen("worst")
