"""Hand-computed checks for instruments, sizing and trade P&L.

Commission and slippage numbers below are arbitrary test inputs, not the
owner's real costs.
"""

import pytest

from pfsim.instruments import INSTRUMENTS, Instrument, get_instrument
from pfsim.pnl import trade_costs, trade_pnl
from pfsim.sizing import contracts_for_risk, risk_per_trade

NQ = get_instrument("NQ")
MNQ = get_instrument("MNQ")
ES = get_instrument("ES")
MES = get_instrument("MES")


# --- instruments -----------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "tick_value"), [("NQ", 5.0), ("MNQ", 0.5), ("ES", 12.5), ("MES", 1.25)]
)
def test_tick_values_match_spec(symbol, tick_value):
    assert get_instrument(symbol).tick_value == tick_value


def test_micro_is_one_tenth_of_mini():
    assert MNQ.tick_value * 10 == NQ.tick_value
    assert MES.tick_value * 10 == ES.tick_value


def test_unknown_instrument_raises_with_known_list():
    with pytest.raises(KeyError, match="known: ES, MES, MNQ, NQ"):
        get_instrument("CL")


def test_registry_has_exactly_the_four_spec_instruments():
    assert set(INSTRUMENTS) == {"NQ", "MNQ", "ES", "MES"}


# --- risk per trade --------------------------------------------------------


def test_risk_one_nq_twenty_ticks():
    assert risk_per_trade(1, 20, NQ) == 100.0  # 1 x 20 x $5


def test_risk_two_es_eight_ticks():
    assert risk_per_trade(2, 8, ES) == 200.0  # 2 x 8 x $12.50


def test_ten_micros_risk_same_as_one_mini():
    assert risk_per_trade(10, 40, MNQ) == risk_per_trade(1, 40, NQ) == 200.0


def test_zero_contracts_is_zero_risk():
    assert risk_per_trade(0, 20, NQ) == 0.0


@pytest.mark.parametrize(("contracts", "stop_ticks"), [(-1, 20), (1, 0), (1, -5)])
def test_risk_rejects_bad_inputs(contracts, stop_ticks):
    with pytest.raises(ValueError):
        risk_per_trade(contracts, stop_ticks, NQ)


# --- contracts for a risk budget -------------------------------------------


def test_sizing_rounds_down():
    # $300 budget, 20-tick NQ stop = $100/contract -> 3 contracts
    assert contracts_for_risk(300, 20, NQ, max_contracts=4) == 3
    # $299 cannot afford a third contract
    assert contracts_for_risk(299, 20, NQ, max_contracts=4) == 2


def test_sizing_exact_boundary_is_included():
    assert contracts_for_risk(200, 20, NQ, max_contracts=4) == 2


def test_sizing_capped_by_25k_plan_max():
    # 25K Growth allows 1 mini: a big budget still yields 1
    assert contracts_for_risk(1000, 20, NQ, max_contracts=1) == 1


def test_sizing_capped_by_50k_plan_micro_max():
    # 50K Growth allows 40 micros; $500 / (10 ticks x $0.50) = 100 -> capped at 40
    assert contracts_for_risk(500, 10, MNQ, max_contracts=40) == 40


def test_sizing_returns_zero_when_one_contract_too_risky():
    assert contracts_for_risk(99, 20, NQ, max_contracts=4) == 0


def test_sizing_survives_float_noise():
    # 0.3 / 0.1 is 2.9999999999999996 in floating point; a hypothetical
    # $0.10-tick contract checks that this still sizes to 3, not 2.
    assert contracts_for_risk(0.3, 1, Instrument("X", 0.1), max_contracts=10) == 3


@pytest.mark.parametrize(("target", "cap"), [(-1, 4), (100, -1)])
def test_sizing_rejects_bad_inputs(target, cap):
    with pytest.raises(ValueError):
        contracts_for_risk(target, 20, NQ, max_contracts=cap)


# --- costs and trade P&L ---------------------------------------------------


def test_costs_one_nq():
    # $4.00 commission + 1 tick x $5 slippage = $9
    assert trade_costs(1, NQ, 4.00, 1) == 9.0


def test_costs_scale_with_contracts():
    assert trade_costs(3, NQ, 4.00, 1) == 3 * trade_costs(1, NQ, 4.00, 1)


def test_costs_zero_when_free():
    assert trade_costs(5, ES, 0.0, 0.0) == 0.0


@pytest.mark.parametrize(("contracts", "comm", "slip"), [(-1, 4, 1), (1, -4, 1), (1, 4, -1)])
def test_costs_reject_bad_inputs(contracts, comm, slip):
    with pytest.raises(ValueError):
        trade_costs(contracts, NQ, comm, slip)


def test_pnl_two_r_winner():
    # 1 NQ, 20-tick stop: 1R = $100. +2R = $200 - $9 costs = $191
    assert trade_pnl(2.0, 1, 20, NQ, 4.00, 1) == 191.0


def test_pnl_one_r_loser():
    # -1R = -$100 - $9 costs = -$109
    assert trade_pnl(-1.0, 1, 20, NQ, 4.00, 1) == -109.0


def test_pnl_scratch_trade_costs_money():
    assert trade_pnl(0.0, 1, 20, NQ, 4.00, 1) == -9.0


def test_pnl_micros():
    # 10 MNQ, 40-tick stop: 1R = $200. +1.5R = $300.
    # costs: 10 x ($1.00 + 1 tick x $0.50) = $15 -> $285
    assert trade_pnl(1.5, 10, 40, MNQ, 1.00, 1) == 285.0


def test_pnl_without_costs_is_r_times_risk():
    assert trade_pnl(1.0, 2, 8, ES, 0.0, 0.0) == pytest.approx(200.0)
