"""Futures instruments and their tick values (dollars per tick per contract)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    """A futures contract, described only by what the simulator needs."""

    symbol: str
    tick_value: float  # dollars per one-tick move, per contract


INSTRUMENTS: dict[str, Instrument] = {
    "NQ": Instrument("NQ", 5.00),
    "MNQ": Instrument("MNQ", 0.50),
    "ES": Instrument("ES", 12.50),
    "MES": Instrument("MES", 1.25),
}


def get_instrument(symbol: str) -> Instrument:
    """Look up an instrument by symbol, e.g. ``get_instrument("NQ")``."""
    try:
        return INSTRUMENTS[symbol]
    except KeyError:
        known = ", ".join(sorted(INSTRUMENTS))
        raise KeyError(f"unknown instrument {symbol!r}; known: {known}") from None
