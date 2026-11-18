"""Turning an R-multiple into dollars, net of trading costs.

trade_pnl = r_multiple x risk_per_trade - commissions - slippage
"""

from pfsim.instruments import Instrument
from pfsim.sizing import risk_per_trade


def trade_costs(
    contracts: int,
    instrument: Instrument,
    commission_per_contract: float,
    slippage_ticks_per_contract: float,
) -> float:
    """Total round-trip cost in dollars: commission plus slippage, per contract.

    Both inputs are round trip (entry + exit). Costs are always paid, win or lose.
    """
    if contracts < 0:
        raise ValueError(f"contracts must be >= 0, got {contracts}")
    if commission_per_contract < 0:
        raise ValueError(f"commission must be >= 0, got {commission_per_contract}")
    if slippage_ticks_per_contract < 0:
        raise ValueError(f"slippage must be >= 0, got {slippage_ticks_per_contract}")
    slippage = slippage_ticks_per_contract * instrument.tick_value
    return contracts * (commission_per_contract + slippage)


def trade_pnl(
    r_multiple: float,
    contracts: int,
    stop_ticks: int,
    instrument: Instrument,
    commission_per_contract: float,
    slippage_ticks_per_contract: float,
) -> float:
    """Net dollar P&L of one closed trade."""
    gross = r_multiple * risk_per_trade(contracts, stop_ticks, instrument)
    costs = trade_costs(contracts, instrument, commission_per_contract, slippage_ticks_per_contract)
    return gross - costs
