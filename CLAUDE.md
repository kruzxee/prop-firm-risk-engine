# CLAUDE.md — Prop-Firm Risk Engine

## Project summary

A Monte Carlo simulator that estimates the probability of passing a futures
prop-firm evaluation (the owner trades NQ/ES through Tradeify). It is a public
portfolio project aimed at data-analyst / risk / software roles, so code
quality, tests and the README matter as much as the numbers.

Roadmap (about 5 hours per week):

| Version | Target date | Scope |
|---|---|---|
| v1 | Dec 4 | The evaluation simulator (current work) |
| v2 | Dec 23 | VaR (historical, parametric, Monte Carlo), Expected Shortfall, Kupiec backtest, stress tests |
| v3 | ~Jan 15 | FastAPI service, Docker, GitHub Actions CI |
| v4 | ~Feb 5 | React + TypeScript front end, AWS ECS Fargate, Kubernetes on kind |

v1 must emit **daily P&L per simulated path** so v2 can consume it directly.
The full v1 model is in `docs/model_spec.md`; read it before touching engine code.

## How we work (follow strictly)

1. **Explain first.** Before writing any code for a step, explain the concept
   with an analogy, pitched at an informed non-specialist.
2. **One step at a time.** After each step, show how to verify it (a test or a
   command the owner can run), then **STOP** and wait for the owner's
   confirmation before starting the next step. Do not chain steps.
3. **Every step that adds logic adds tests.** No logic lands without a test
   that exercises it.
4. **Readable scalar engine is the source of truth.** Write the plain,
   per-trade, per-day loop first and keep it as the reference. No premature
   optimisation (no vectorised/numba rewrite unless asked, and then it must be
   tested against the scalar engine).

## Hard constraints

- **Never invent firm rule values** (profit targets, drawdown amounts, lock
  levels, daily limits, consistency %, min days, max contracts, etc.). Ask the
  owner. Unknown values stay as clearly marked `TODO` placeholders.
- Stack: Python 3.12+, NumPy, pandas, PyYAML, pytest, ruff. `src/` layout
  (`src/pfsim`), configured by `pyproject.toml`.
- Free tools only. The repo is public: no secrets, account numbers or personal
  data in code, configs or commits.
- Work in dollars. Trade P&L = R-multiple × risk per trade − commissions −
  slippage.
- Never drop censored attempts from results.
- Use common random numbers across sizing levels in sensitivity runs.
- Rule sets live in versioned YAML under `config/rulesets/` and must record
  firm, plan, effective date and source.

## Layout

```
src/pfsim/          package (engine code goes here, step by step)
tests/              pytest suite
config/rulesets/    versioned firm rule-set YAML (+ schema)
docs/               model spec and design notes
```

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```
