"""Trades and the parametric trade generator.

The generator answers one question: "give me the candidate trades for the next
day". The trader policy later decides how many of them are actually taken.

Every random draw goes through an inverse-CDF mapping of a uniform number, and
each trade always consumes the same three uniforms (outcome, MAE, MFE). That
keeps random streams aligned across scenarios (common random numbers): changing
size, excursion model or even win rate re-maps the same underlying draws instead
of reshuffling them.
"""

from dataclasses import dataclass
from itertools import accumulate
from typing import Literal, Protocol

import numpy as np

STOP_R = 1.0  # a full stop-out loses exactly 1R by definition
_TOL = 1e-9


@dataclass(frozen=True)
class Trade:
    """One trade's result, in R.

    ``mfe_r`` / ``mae_r`` are non-negative magnitudes: how far the trade moved in
    your favour / against you before it closed. ``None`` means "path unknown".
    The closing result must lie inside that range: ``-mae_r <= r_multiple <= mfe_r``.
    """

    r_multiple: float
    mfe_r: float | None = None
    mae_r: float | None = None

    def __post_init__(self) -> None:
        if self.r_multiple < -STOP_R - _TOL:
            raise ValueError(f"r_multiple {self.r_multiple} is beyond the -1R stop")
        if self.mfe_r is not None:
            if self.mfe_r < 0:
                raise ValueError(f"mfe_r must be >= 0, got {self.mfe_r}")
            if self.r_multiple > self.mfe_r + _TOL:
                raise ValueError("r_multiple cannot exceed mfe_r")
        if self.mae_r is not None:
            if not 0 <= self.mae_r <= STOP_R + _TOL:
                raise ValueError(f"mae_r must be in [0, 1], got {self.mae_r}")
            if -self.r_multiple > self.mae_r + _TOL:
                raise ValueError("a loss cannot be larger than mae_r")


# --- outcome models: map a uniform u in [0, 1) to an R-multiple --------------


@dataclass(frozen=True)
class WinRateRR:
    """Win -> +rr, loss -> -1R."""

    win_rate: float
    rr: float

    def __post_init__(self) -> None:
        if not 0 <= self.win_rate <= 1:
            raise ValueError(f"win_rate must be in [0, 1], got {self.win_rate}")
        if self.rr <= 0:
            raise ValueError(f"rr must be > 0, got {self.rr}")

    @property
    def max_r(self) -> float:
        return self.rr

    def r_from_uniform(self, u: float) -> float:
        return self.rr if u < self.win_rate else -STOP_R


@dataclass(frozen=True)
class DiscreteR:
    """A list of possible R results with their probabilities."""

    values: tuple[float, ...]
    probs: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values or len(self.values) != len(self.probs):
            raise ValueError("values and probs must be non-empty and the same length")
        if any(p < 0 for p in self.probs):
            raise ValueError("probs must be >= 0")
        if abs(sum(self.probs) - 1) > 1e-6:
            raise ValueError(f"probs must sum to 1, got {sum(self.probs)}")
        if min(self.values) < -STOP_R - _TOL:
            raise ValueError("no value may be worse than the -1R stop")

    @property
    def max_r(self) -> float:
        return max(max(self.values), 0.0)

    def r_from_uniform(self, u: float) -> float:
        for value, cum in zip(self.values, accumulate(self.probs), strict=True):
            if u < cum:
                return value
        return self.values[-1]  # u within float rounding of 1


# --- trades-per-day models -------------------------------------------------


@dataclass(frozen=True)
class FixedCount:
    n: int

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ValueError(f"n must be >= 0, got {self.n}")

    def draw(self, rng: np.random.Generator) -> int:
        return self.n


@dataclass(frozen=True)
class PoissonCount:
    lam: float

    def __post_init__(self) -> None:
        if self.lam < 0:
            raise ValueError(f"lam must be >= 0, got {self.lam}")

    def draw(self, rng: np.random.Generator) -> int:
        return int(rng.poisson(self.lam))


# --- the generator ---------------------------------------------------------

Excursion = Literal["none", "uniform"]
EXCURSION_MODELS: tuple[str, ...] = ("none", "uniform")


def excursions(
    r_multiple: float, max_r: float, u_mae: float, u_mfe: float, model: Excursion
) -> tuple[float, float]:
    """Return ``(mfe_r, mae_r)`` for a trade that closed at ``r_multiple``.

    - ``none``: the trade went straight to its result (smallest consistent path).
    - ``uniform``: the unseen side of the path is uniform between that minimum
      and its cap (the -1R stop for MAE, the best possible R for MFE).
    """
    min_mae = max(0.0, -r_multiple)
    min_mfe = max(0.0, r_multiple)
    if model == "none":
        return min_mfe, min_mae
    if model == "uniform":
        mae = min_mae + u_mae * (STOP_R - min_mae)
        mfe = min_mfe + u_mfe * (max(max_r, min_mfe) - min_mfe)
        return mfe, mae
    raise ValueError(f"unknown excursion model {model!r}; known: {EXCURSION_MODELS}")


class TradeGenerator(Protocol):
    """Anything that can produce the next day's candidate trades."""

    def next_day(self, rng: np.random.Generator) -> list[Trade]: ...


@dataclass(frozen=True)
class ParametricGenerator:
    outcome: WinRateRR | DiscreteR
    count: FixedCount | PoissonCount
    excursion: Excursion

    def __post_init__(self) -> None:
        if self.excursion not in EXCURSION_MODELS:
            raise ValueError(f"unknown excursion model {self.excursion!r}")

    def next_day(self, rng: np.random.Generator) -> list[Trade]:
        n = self.count.draw(rng)
        draws = rng.random((n, 3))  # always 3 uniforms per trade
        trades = []
        for u_outcome, u_mae, u_mfe in draws:
            r = self.outcome.r_from_uniform(float(u_outcome))
            mfe, mae = excursions(r, self.outcome.max_r, float(u_mae), float(u_mfe), self.excursion)
            trades.append(Trade(r, mfe_r=mfe, mae_r=mae))
        return trades
