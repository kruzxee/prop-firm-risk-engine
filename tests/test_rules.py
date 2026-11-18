"""Tests for loading and validating rule-set YAML files."""

import copy
from datetime import date
from pathlib import Path

import pytest
import yaml

from pfsim.rules import RuleSetError, load_ruleset, parse_ruleset

TRADEIFY = Path(__file__).resolve().parents[1] / "config" / "rulesets" / "tradeify"


@pytest.fixture
def raw_25k() -> dict:
    return yaml.safe_load((TRADEIFY / "growth_25k_v1.yaml").read_text())


def test_load_25k_growth():
    rs = load_ruleset(TRADEIFY / "growth_25k_v1.yaml")
    assert rs.meta.firm == "Tradeify"
    assert rs.meta.effective_date == date(2026, 11, 17)
    assert rs.start_balance == 25_000
    assert rs.target_balance == 26_500
    assert rs.initial_floor == 24_000
    assert rs.drawdown.mode == "trailing"
    assert rs.drawdown.hwm_update == "eod"
    assert rs.drawdown.breach_check == "intraday"
    assert rs.drawdown.lock_level is None
    assert rs.daily_loss_limit.amount == 600
    assert rs.daily_loss_limit.basis == "equity"
    assert rs.daily_loss_limit.kind == "soft"
    assert not rs.consistency.enabled
    assert rs.min_trading_days.days == 0
    assert rs.max_contracts == {"NQ": 1, "ES": 1, "MNQ": 10, "MES": 10}


def test_load_50k_growth():
    rs = load_ruleset(TRADEIFY / "growth_50k_v1.yaml")
    assert rs.target_balance == 53_000
    assert rs.initial_floor == 48_000
    assert rs.daily_loss_limit.amount == 1_250
    assert rs.max_contracts["NQ"] == 4
    assert rs.max_contracts["MNQ"] == 40


def test_template_is_rejected_as_incomplete():
    with pytest.raises(RuleSetError):
        load_ruleset(TRADEIFY / "_template.yaml")


def _with(raw: dict, path: str, value):
    data = copy.deepcopy(raw)
    *parents, leaf = path.split(".")
    node = data
    for key in parents:
        node = node[key]
    node[leaf] = value
    return data


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("drawdown.breach_check", "TODO", "unresolved TODO"),
        ("drawdown.mode", "weekly", "must be one of"),
        ("drawdown.amount", -1000, "positive number"),
        ("drawdown.amount", None, "missing"),
        ("drawdown.lock_level", "TODO", "number or null"),
        ("daily_loss_limit.kind", "maybe", "must be one of"),
        ("account.start_balance", 0, "positive number"),
        ("min_trading_days.days", -1, "integer >= 0"),
        ("max_contracts.CL", 1, "unknown instrument"),
        ("max_contracts.NQ", 0, "integer >= 1"),
        ("meta.effective_date", "soon", "YYYY-MM-DD"),
    ],
)
def test_invalid_values_are_rejected(raw_25k, path, value, message):
    with pytest.raises(RuleSetError, match=message):
        parse_ruleset(_with(raw_25k, path, value))


def test_disabled_daily_limit_needs_no_details(raw_25k):
    data = _with(raw_25k, "daily_loss_limit", {"enabled": False})
    assert not parse_ruleset(data).daily_loss_limit.enabled


def test_enabled_consistency_requires_fraction(raw_25k):
    data = _with(
        raw_25k,
        "consistency",
        {"enabled": True, "max_best_day_pct": 35, "denominator": "total_profit"},
    )
    with pytest.raises(RuleSetError, match="fraction"):
        parse_ruleset(data)
    data["consistency"]["max_best_day_pct"] = 0.35
    assert parse_ruleset(data).consistency.max_best_day_pct == 0.35


def test_static_drawdown_ignores_hwm_update(raw_25k):
    data = _with(raw_25k, "drawdown.mode", "static")
    data["drawdown"].pop("hwm_update")
    assert parse_ruleset(data).drawdown.mode == "static"
