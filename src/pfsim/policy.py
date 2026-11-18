"""Trader policy: the trader's own rules, separate from the firm's rules.

The defaults are the owner's stated policy (2026-11-17):
- at most 2 trades per day;
- stop after one win;
- stop after one loss, unless that loss was a "forced error" (bad execution
  rather than wrong analysis), which allows one more trade within the cap;
- stop for the day once the evaluation profit target is reached.

Forced errors are discretionary, so ``forced_error_prob`` is a sensitivity
parameter. Default 0 is the strict, conservative baseline.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TraderPolicy:
    max_trades_per_day: int = 2
    stop_after_wins: int | None = 1
    stop_after_losses: int | None = 1
    forced_error_prob: float = 0.0
    stop_when_target_reached: bool = True

    def __post_init__(self) -> None:
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be >= 1")
        for name in ("stop_after_wins", "stop_after_losses"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"{name} must be >= 1 or None")
        if not 0 <= self.forced_error_prob <= 1:
            raise ValueError("forced_error_prob must be in [0, 1]")


class PolicyDay:
    """Tracks one trading day against a :class:`TraderPolicy`.

    Wins and losses are classified by the trade's R-multiple: > 0 is a win,
    < 0 a loss, exactly 0 a scratch (counts as a trade, but neither a win nor
    a loss).
    """

    def __init__(self, policy: TraderPolicy) -> None:
        self.policy = policy
        self.trades = 0
        self.wins = 0
        self.losses = 0  # losses that count toward the stop (analysis errors)
        self.forced_errors = 0  # losses forgiven as execution errors

    def record(self, r_multiple: float, forced_error_draw: float) -> None:
        """Record a closed trade.

        ``forced_error_draw`` is a uniform number in [0, 1) that the engine always
        supplies (even when the probability is 0) so random streams stay aligned.
        """
        self.trades += 1
        if r_multiple > 0:
            self.wins += 1
        elif r_multiple < 0:
            if forced_error_draw < self.policy.forced_error_prob:
                self.forced_errors += 1
            else:
                self.losses += 1

    def may_trade(self, target_reached: bool = False) -> bool:
        """Would the trader take another trade today?"""
        p = self.policy
        if self.trades >= p.max_trades_per_day:
            return False
        if p.stop_after_wins is not None and self.wins >= p.stop_after_wins:
            return False
        if p.stop_after_losses is not None and self.losses >= p.stop_after_losses:
            return False
        return not (target_reached and p.stop_when_target_reached)
