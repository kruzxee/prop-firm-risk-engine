"""Uncertainty for Monte Carlo proportions (e.g. the pass rate).

A pass rate from N simulated attempts is an estimate; its standard error
SE = sqrt(p(1 - p) / N) says how much it would wobble if we re-ran with a
different seed.
"""

import math

Z_95 = 1.959963984540054  # two-sided 95% normal quantile


def _check(n: int) -> None:
    if n <= 0:
        raise ValueError(f"n must be > 0, got {n}")


def proportion_se(p: float, n: int) -> float:
    """Standard error of a proportion ``p`` estimated from ``n`` trials."""
    _check(n)
    if not 0 <= p <= 1:
        raise ValueError(f"p must be in [0, 1], got {p}")
    return math.sqrt(p * (1 - p) / n)


def normal_ci(p: float, n: int, z: float = Z_95) -> tuple[float, float]:
    """Normal-approximation interval ``p ± z·SE``, clipped to [0, 1]."""
    half = z * proportion_se(p, n)
    return max(0.0, p - half), min(1.0, p + half)


def wilson_ci(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval; behaves well when p is near 0 or 1."""
    _check(n)
    if not 0 <= successes <= n:
        raise ValueError(f"successes must be in [0, {n}], got {successes}")
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)
