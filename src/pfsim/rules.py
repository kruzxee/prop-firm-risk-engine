"""Load and validate firm rule sets from YAML (see config/rulesets/schema.yaml).

This module only reads configuration. Applying the rules (floors, limits,
pass checks) lives in the engine.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from pfsim.instruments import INSTRUMENTS


@dataclass(frozen=True)
class RuleSetMeta:
    firm: str
    plan: str
    version: int
    effective_date: date
    source: str
    notes: str = ""


@dataclass(frozen=True)
class DrawdownRule:
    mode: str  # trailing | static
    amount: float
    hwm_update: str  # eod | intraday
    breach_check: str  # eod | intraday
    lock_level: float | None


@dataclass(frozen=True)
class DailyLossLimitRule:
    enabled: bool
    amount: float | None = None
    basis: str | None = None  # realized | equity
    kind: str | None = None  # soft | hard


@dataclass(frozen=True)
class ConsistencyRule:
    enabled: bool
    max_best_day_pct: float | None = None
    denominator: str | None = None  # total_profit | profit_target
    wording: str | None = None


@dataclass(frozen=True)
class MinTradingDaysRule:
    days: int
    min_day_profit: float | None = None


@dataclass(frozen=True)
class RuleSet:
    meta: RuleSetMeta
    start_balance: float
    profit_target: float
    drawdown: DrawdownRule
    daily_loss_limit: DailyLossLimitRule
    consistency: ConsistencyRule
    min_trading_days: MinTradingDaysRule
    max_contracts: dict[str, int]

    @property
    def target_balance(self) -> float:
        return self.start_balance + self.profit_target

    @property
    def initial_floor(self) -> float:
        return self.start_balance - self.drawdown.amount


class RuleSetError(ValueError):
    """Raised when a rule-set file is incomplete or invalid."""


def _get(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise RuleSetError(f"{where}.{key} is missing")
    value = d[key]
    if isinstance(value, str) and "TODO" in value:
        raise RuleSetError(f"{where}.{key} is an unresolved TODO")
    return value


def _choice(d: dict[str, Any], key: str, where: str, options: tuple[str, ...]) -> str:
    value = _get(d, key, where)
    if value not in options:
        raise RuleSetError(f"{where}.{key} must be one of {options}, got {value!r}")
    return value


def _positive(d: dict[str, Any], key: str, where: str) -> float:
    value = _get(d, key, where)
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise RuleSetError(f"{where}.{key} must be a positive number, got {value!r}")
    return float(value)


def parse_ruleset(data: dict[str, Any]) -> RuleSet:
    """Build a validated :class:`RuleSet` from already-parsed YAML."""
    m = _get(data, "meta", "ruleset")
    effective = _get(m, "effective_date", "meta")
    if not isinstance(effective, date):
        raise RuleSetError("meta.effective_date must be a YYYY-MM-DD date")
    meta = RuleSetMeta(
        firm=_get(m, "firm", "meta"),
        plan=_get(m, "plan", "meta"),
        version=int(_get(m, "version", "meta")),
        effective_date=effective,
        source=_get(m, "source", "meta"),
        notes=m.get("notes") or "",
    )

    start = _positive(_get(data, "account", "ruleset"), "start_balance", "account")
    target = _positive(_get(data, "profit_target", "ruleset"), "amount", "profit_target")

    dd = _get(data, "drawdown", "ruleset")
    mode = _choice(dd, "mode", "drawdown", ("trailing", "static"))
    lock = dd.get("lock_level")
    if isinstance(lock, str):
        raise RuleSetError("drawdown.lock_level must be a number or null")
    drawdown = DrawdownRule(
        mode=mode,
        amount=_positive(dd, "amount", "drawdown"),
        hwm_update=_choice(dd, "hwm_update", "drawdown", ("eod", "intraday"))
        if mode == "trailing"
        else "eod",
        breach_check=_choice(dd, "breach_check", "drawdown", ("eod", "intraday")),
        lock_level=None if lock is None else float(lock),
    )

    dl = _get(data, "daily_loss_limit", "ruleset")
    if _get(dl, "enabled", "daily_loss_limit"):
        daily = DailyLossLimitRule(
            enabled=True,
            amount=_positive(dl, "amount", "daily_loss_limit"),
            basis=_choice(dl, "basis", "daily_loss_limit", ("realized", "equity")),
            kind=_choice(dl, "kind", "daily_loss_limit", ("soft", "hard")),
        )
    else:
        daily = DailyLossLimitRule(enabled=False)

    c = _get(data, "consistency", "ruleset")
    if _get(c, "enabled", "consistency"):
        pct = _positive(c, "max_best_day_pct", "consistency")
        if pct > 1:
            raise RuleSetError("consistency.max_best_day_pct is a fraction in (0, 1]")
        consistency = ConsistencyRule(
            enabled=True,
            max_best_day_pct=pct,
            denominator=_choice(c, "denominator", "consistency", ("total_profit", "profit_target")),
            wording=c.get("wording"),
        )
    else:
        consistency = ConsistencyRule(enabled=False)

    md = _get(data, "min_trading_days", "ruleset")
    days = _get(md, "days", "min_trading_days")
    if not isinstance(days, int) or days < 0:
        raise RuleSetError("min_trading_days.days must be an integer >= 0")
    min_days = MinTradingDaysRule(days=days, min_day_profit=md.get("min_day_profit"))

    mc = _get(data, "max_contracts", "ruleset")
    max_contracts: dict[str, int] = {}
    for symbol in mc:
        if symbol not in INSTRUMENTS:
            raise RuleSetError(f"max_contracts has unknown instrument {symbol!r}")
        n = _get(mc, symbol, "max_contracts")
        if not isinstance(n, int) or n < 1:
            raise RuleSetError(f"max_contracts.{symbol} must be an integer >= 1")
        max_contracts[symbol] = n

    return RuleSet(
        meta=meta,
        start_balance=start,
        profit_target=target,
        drawdown=drawdown,
        daily_loss_limit=daily,
        consistency=consistency,
        min_trading_days=min_days,
        max_contracts=max_contracts,
    )


def load_ruleset(path: str | Path) -> RuleSet:
    """Read a rule-set YAML file and validate it."""
    data = yaml.safe_load(Path(path).read_text())
    return parse_ruleset(data)
