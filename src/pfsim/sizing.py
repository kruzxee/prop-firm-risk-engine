"""Position sizing: how many dollars one R is, and how many contracts to trade.

risk_per_trade = contracts x stop_ticks x tick_value
"""

import math

from pfsim.instruments import Instrument

# Guards against float noise such as 2.9999999 contracts rounding down to 2.
_EPS = 1e-9


def risk_per_trade(contracts: int, stop_ticks: int, instrument: Instrument) -> float:
    """Dollars lost if the stop is hit (1R), before costs."""
    if contracts < 0:
        raise ValueError(f"contracts must be >= 0, got {contracts}")
    if stop_ticks <= 0:
        raise ValueError(f"stop_ticks must be > 0, got {stop_ticks}")
    return contracts * stop_ticks * instrument.tick_value


def contracts_for_risk(
    target_risk: float, stop_ticks: int, instrument: Instrument, max_contracts: int
) -> int:
    """Largest whole number of contracts whose risk does not exceed ``target_risk``.

    The result is rounded down (never risk more than intended) and capped at the
    plan's ``max_contracts``. Returns 0 if even one contract risks too much; the
    caller decides whether that means "skip the trade".
    """
    if target_risk < 0:
        raise ValueError(f"target_risk must be >= 0, got {target_risk}")
    if max_contracts < 0:
        raise ValueError(f"max_contracts must be >= 0, got {max_contracts}")
    per_contract = risk_per_trade(1, stop_ticks, instrument)
    affordable = math.floor(target_risk / per_contract + _EPS)
    return min(affordable, max_contracts)
