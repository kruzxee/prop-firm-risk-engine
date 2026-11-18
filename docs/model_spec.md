# v1 Model Specification — Evaluation Simulator

Status: **agreed design, not yet implemented.** Values marked `TODO` are
waiting on the owner; never fill them in by guessing.

## 1. Purpose

Estimate, by Monte Carlo, the probability that a trader with a given
statistical edge and sizing passes a futures prop-firm evaluation, and how
long it takes. Every simulated path also produces daily P&L so v2 (VaR, ES,
Kupiec backtest, stress tests) can consume it without re-simulating.

## 2. Units and trade P&L

All money is in **US dollars**.

```
risk_per_trade = contracts × stop_ticks × tick_value
trade_pnl      = r_multiple × risk_per_trade − commissions − slippage
```

| Instrument | Tick value |
|---|---|
| NQ  | $5.00 |
| MNQ | $0.50 |
| ES  | $12.50 |
| MES | $1.25 |

- `contracts` is an integer (sizing is quantised) and is capped by the rule
  set's `max_contracts` for that instrument.
- Commissions are per contract, round trip. Slippage is expressed in ticks per
  contract per round trip and converted to dollars with the tick value.

## 3. Trade generator

One interface: **"give me the next day's trades"** (a list of trades for one
session, possibly empty). Implementations are swappable.

### v1: parametric generator
- Outcome model, one of:
  - **win rate + reward:risk** — win → `+RR` R, loss → `−1` R;
  - **discrete R distribution** — list of (r_multiple, probability) pairs.
- Trades per day: **fixed** count or **Poisson(λ)**.
- Optional per-trade `mfe_r` / `mae_r` (max favourable / adverse excursion, in
  R) to drive intraday drawdown checks.

Implementation conventions (`src/pfsim/trades.py`):
- `mfe_r` and `mae_r` are **non-negative magnitudes**; a trade must satisfy
  `-mae_r ≤ r_multiple ≤ mfe_r` and `mae_r ≤ 1` (the stop).
- The generator returns **candidate** trades for a day; the trader policy
  decides how many are taken.
- Excursion models: `none` (the trade goes straight to its result) and
  `uniform` (the unseen side of the path is uniform between the minimum the
  result implies and its cap: the stop for MAE, the best R for MFE).
- Common random numbers: each trade always consumes three uniforms (outcome,
  MAE, MFE), mapped by inverse CDF, so changing sizing, excursion model or win
  rate re-maps the same draws rather than reshuffling them.
- With EOD high-water-mark updates, **only MAE affects outcomes** (intraday
  drawdown and equity-based daily limit). MFE is carried for later analysis.

### Later: empirical generator
Resamples a real trade list. Columns:

| Column | Required |
|---|---|
| session_date | yes |
| r_multiple | yes |
| mfe_r | no |
| mae_r | no |
| stop_ticks | no |
| instrument | no |
| setup_tag | no |

## 4. Trader policy (separate from firm rules)

The policy is what the trader chooses to do; firm rules are what the firm
enforces. They are configured and tested separately.

- personal max trades per day;
- stop for the day after N losses (consecutive or total — to be configured);
- post-target behaviour (e.g. stop trading, trade only until min days are met,
  reduce size).

Default policy (owner, 2026-11-17):
- max **2 trades per day**;
- **stop after one win**;
- after a loss, stop for the day, **unless** that loss was a "forced error"
  (bad execution such as a late or early entry, or noise, rather than wrong
  analysis), in which case one more trade is allowed (still capped at 2).
  Forced errors are discretionary and have no fixed rate, so the simulator
  treats `forced_error_prob` as a **sensitivity parameter, not a fact**:
  default `0` (strict one-loss stop, the conservative baseline), swept over a
  range (e.g. 0, 0.25, 0.5) to show how much the second-chance trade matters;
- once the evaluation profit target is reached on closed balance, take no
  more trades that day. (The pass is then confirmed at end of day, which ends
  the attempt.)

With the default (`forced_error_prob = 0`) the policy is effectively **one
trade per day**; a second trade only happens after a forced-error loss.

## 5. Attempt and terminal states

An **attempt** is one evaluation account run from the starting balance to
exactly one terminal state:

| Outcome | Meaning |
|---|---|
| `PASS` | profit target reached on closed balance **and** min trading days met **and** consistency rule satisfied |
| `FAIL_TRAILING_DD` | balance/equity breached the drawdown floor |
| `FAIL_DAILY_LIMIT` | daily loss limit breached **and** the limit is configured as hard |
| `CENSORED` | still alive at the `max_days` horizon |

Censored attempts are **never dropped**; they are reported as their own
outcome and included in every denominator.

## 6. Firm rules (configurable, versioned YAML)

Each rule set records `firm`, `plan`, `version`, `effective_date` and
`source` (URL or document). Schema: `config/rulesets/schema.yaml`.

### 6.1 Profit target
Measured on **closed balance** (realised P&L only).

### 6.2 Trailing drawdown
```
floor = min(HWM − dd_amount, lock_level)
```
- `hwm_update`: `eod` (closing balance at end of day) or `intraday`
  (uses trade MFE to raise HWM mid-trade).
- `breach_check`: `eod` or `intraday` (uses MAE path).
- Lock level: once the floor reaches it, the floor stops trailing.
- **Static drawdown** is the special case where HWM never updates
  (`floor = start_balance − dd_amount`).

### 6.3 Daily loss limit
- Reference: prior day's closing balance.
- Basis: `realized` (closed P&L) or `equity` (includes open-trade MAE).
- Type: `soft` (ends the trading day) or `hard` (ends the attempt with
  `FAIL_DAILY_LIMIT`).
- May be disabled.

### 6.4 Consistency
```
best_day_profit ≤ pct × denominator
```
- `denominator`: `total_profit` or `profit_target`.
- Checked **at pass time** (when the target and min-days conditions are met).
- Exact firm wording: **TODO (owner)**.

### 6.5 Minimum trading days
- Count of days that qualify as trading days.
- Optional `min_day_profit`: a day only counts if its P&L ≥ this amount.

## 7. Order of evaluation

Per trade:
1. **Intra-trade path** — apply MFE/MAE to intraday HWM, intraday drawdown and
   equity-based daily limit checks. Ordering of MFE vs MAE within the trade
   is configurable: `conservative` (MAE first), `optimistic` (MFE first) or
   `random`. Default: **`conservative`** (owner, 2026-11-17).
   Bounds for the parametric generator: the stop caps adverse excursion at
   `mae_r ≤ 1` and the take-profit caps favourable excursion at
   `mfe_r ≤ RR` (RR between 1 and 2), so intraday excursion lies in
   [−1R, +RR].
2. **Close trade** — add `trade_pnl` net of commissions and slippage; run
   closed-balance checks.
3. **Trader policy** — decide whether to take the next trade today.

End of day:
1. Update EOD HWM and floor (respecting the lock).
2. Run EOD drawdown check if configured.
3. Decide whether the day counts toward min trading days.
4. Check pass conditions. **Pass is checked at end of day only** (owner,
   2026-11-17): balances are updated by the firm at EOD, so an intraday touch
   of the target that closes below it does not pass.

## 8. Outputs (tables)

| Table | Grain | Key columns |
|---|---|---|
| `attempts` | one row per attempt | scenario_id, attempt_id, outcome, fail_reason, days, trades, final_balance, best_day, max_drawdown_used, … |
| `scenario_summary` | one row per scenario | N, p_pass, p_fail_dd, p_fail_daily, p_censored, each with SE and 95% CI; median days to pass |
| `equity_paths` | sampled attempts × day | scenario_id, attempt_id, day, balance, hwm, floor |
| `daily_pnl` | every attempt × day | scenario_id, attempt_id, day, pnl — **input to v2** |

Standard error for a proportion: `SE = sqrt(p(1 − p) / N)`; 95% CI ≈
`p ± 1.96 × SE` (Wilson interval may be added for p near 0 or 1).

## 9. Randomness

- All randomness comes from seeded NumPy `Generator`s; a run is reproducible
  from its seed.
- **Common random numbers**: when sweeping sizing levels, every level sees the
  same underlying trade-outcome draws, so differences between levels reflect
  sizing, not noise. Sensitivity curves are therefore smooth.

## 10. Validation

1. **Deterministic sequences** — hand-computed trade sequences, one or more
   per rule (target hit, trailing floor breach, lock engaged, soft vs hard
   daily limit, consistency failure, min-days gating, censoring).
2. **Gambler's ruin check** — static drawdown, no daily limit, fixed ±1R
   trades with win probability p. Probability of reaching the target before
   the floor has a closed form:
   ```
   q = 1 − p, r = q / p
   P(pass) = (1 − r^a) / (1 − r^(a+b))    (p ≠ 0.5)
   P(pass) = a / (a + b)                  (p = 0.5)
   ```
   where `a` = distance to the floor and `b` = distance to the target, both in
   units of 1R. The simulated pass rate must fall within Monte Carlo error
   (e.g. ±3 SE) of this value.

## 11. Implementation principles

- A readable, scalar (per-trade, per-day) engine is the source of truth. Any
  later optimisation must be tested against it.
- Each rule is a small, separately tested unit.

## 12. Decisions and open questions

Decided (2026-11-17):
- Rule sets: `config/rulesets/tradeify/growth_25k_v1.yaml` and
  `growth_50k_v1.yaml` (evaluation only; v1 does not simulate funded accounts).
- Pass checked at end of day.
- Lock level: none on evaluation. Under EOD trailing plus an EOD pass check,
  the floor can only reach start + (target − DD) when the EOD high-water mark
  equals the target balance, which is already a pass, so a lock cannot change
  evaluation outcomes.
- Default trader policy: see section 4 (stop after one win; forced-error
  second trade is a sensitivity parameter, default 0).
- Trailing drawdown: HWM updates EOD; breach is checked **intraday on
  equity** and is **hard** (attempt fails).
- Daily loss limit: **intraday on equity** from prior day close, **soft**
  (no more trading that day).
- MFE/MAE ordering default: conservative. Excursions bounded to [−1R, +RR].

Open: none for v1 rules. Commissions and slippage per contract are scenario
inputs (not firm rules) and will be asked for when the cost step is built.
