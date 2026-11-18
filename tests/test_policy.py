"""Tests for the trader policy, using the owner's default rules."""

import pytest

from pfsim.policy import PolicyDay, TraderPolicy

NOT_FORCED = 0.99  # a draw above any realistic forced_error_prob
FORCED = 0.0  # a draw below any positive forced_error_prob


def day(**kwargs) -> PolicyDay:
    return PolicyDay(TraderPolicy(**kwargs))


def test_fresh_day_may_trade():
    assert day().may_trade()


def test_stop_after_one_win():
    d = day()
    d.record(2.0, NOT_FORCED)
    assert not d.may_trade()


def test_stop_after_one_analysis_loss():
    d = day(forced_error_prob=0.5)
    d.record(-1.0, NOT_FORCED)
    assert d.losses == 1
    assert not d.may_trade()


def test_forced_error_loss_allows_second_trade():
    d = day(forced_error_prob=0.5)
    d.record(-1.0, FORCED)
    assert d.forced_errors == 1 and d.losses == 0
    assert d.may_trade()


def test_two_trade_cap_even_after_two_forced_errors():
    d = day(forced_error_prob=1.0)
    d.record(-1.0, FORCED)
    d.record(-1.0, FORCED)
    assert not d.may_trade()


def test_default_forced_error_prob_zero_never_forgives():
    d = day()
    d.record(-1.0, FORCED)  # even the lowest possible draw
    assert d.losses == 1
    assert not d.may_trade()


def test_forced_error_then_win_stops():
    d = day(forced_error_prob=0.5)
    d.record(-1.0, FORCED)
    d.record(2.0, NOT_FORCED)
    assert not d.may_trade()


def test_scratch_is_neither_win_nor_loss_but_counts_as_trade():
    d = day()
    d.record(0.0, NOT_FORCED)
    assert (d.trades, d.wins, d.losses) == (1, 0, 0)
    assert d.may_trade()
    d.record(0.0, NOT_FORCED)
    assert not d.may_trade()  # cap of 2


def test_stop_when_target_reached():
    assert not day().may_trade(target_reached=True)
    assert day(stop_when_target_reached=False).may_trade(target_reached=True)


def test_limits_can_be_disabled():
    d = day(max_trades_per_day=5, stop_after_wins=None, stop_after_losses=None)
    for r in (2.0, -1.0, 2.0, -1.0):
        d.record(r, NOT_FORCED)
    assert d.may_trade()
    d.record(2.0, NOT_FORCED)
    assert not d.may_trade()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_trades_per_day": 0},
        {"stop_after_wins": 0},
        {"stop_after_losses": 0},
        {"forced_error_prob": -0.1},
        {"forced_error_prob": 1.1},
    ],
)
def test_policy_rejects_bad_inputs(kwargs):
    with pytest.raises(ValueError):
        TraderPolicy(**kwargs)
