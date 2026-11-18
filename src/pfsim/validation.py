"""Closed-form results used to validate the Monte Carlo engine.

Gambler's ruin: start between a floor and a target; each step is +1 with
probability p, else -1. The chance of reaching the target first has an exact
formula. With a static drawdown, no daily limit and fixed ±1R trades, an
evaluation is exactly this game, so the simulated pass rate must match it.
"""


def gamblers_ruin_pass_probability(p: float, floor_steps: int, target_steps: int) -> float:
    """P(hit +target_steps before -floor_steps) for a ±1 random walk from 0.

    ``floor_steps`` (a) is the distance down to the floor and ``target_steps``
    (b) the distance up to the target, both in steps (1R each).

        r = (1 - p) / p
        P = (1 - r^a) / (1 - r^(a+b))     if p != 0.5
        P = a / (a + b)                   if p == 0.5
    """
    if not 0 <= p <= 1:
        raise ValueError(f"p must be in [0, 1], got {p}")
    if floor_steps < 1 or target_steps < 1:
        raise ValueError("floor_steps and target_steps must be >= 1")
    a, b = floor_steps, target_steps
    if p == 0:
        return 0.0
    if p == 1:
        return 1.0
    if abs(p - 0.5) < 1e-12:
        return a / (a + b)
    r = (1 - p) / p
    return (1 - r**a) / (1 - r ** (a + b))
