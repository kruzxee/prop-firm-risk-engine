# Prop-Firm Risk Engine

> Work in progress — v1 (evaluation simulator) under construction.

A Monte Carlo simulator that estimates the probability of passing a futures
prop-firm evaluation account, given a trader's statistical edge, position
sizing and the firm's rules (profit target, trailing drawdown, daily loss
limit, consistency rule, minimum trading days).

## Roadmap

- **v1** — evaluation simulator: pass / fail / censored outcomes with confidence intervals
- **v2** — VaR (historical, parametric, Monte Carlo), Expected Shortfall, Kupiec backtest, stress tests
- **v3** — FastAPI service, Docker, GitHub Actions CI
- **v4** — React + TypeScript front end, AWS ECS Fargate, Kubernetes on kind

## Docs

- [Model specification](docs/model_spec.md)
- [Rule-set schema](config/rulesets/schema.yaml)

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Disclaimer

Educational project. Not financial advice. Firm rules change; always check the
firm's current terms. Rule sets record their source and effective date.
