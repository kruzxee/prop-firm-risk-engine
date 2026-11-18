"""Skeleton smoke tests: the package imports and the rule-set YAML files parse."""

from pathlib import Path

import yaml

import pfsim

RULESETS = Path(__file__).resolve().parents[1] / "config" / "rulesets"
REQUIRED_META = {"firm", "plan", "version", "effective_date", "source"}


def test_package_imports():
    assert pfsim.__version__


def test_schema_parses():
    schema = yaml.safe_load((RULESETS / "schema.yaml").read_text())
    assert schema["type"] == "object"


def test_example_rulesets_parse_and_have_metadata():
    files = [p for p in RULESETS.rglob("*.yaml") if p.name != "schema.yaml"]
    assert files, "expected at least one rule-set file"
    for path in files:
        data = yaml.safe_load(path.read_text())
        assert set(data["meta"]) >= REQUIRED_META, path


def test_real_rulesets_have_no_todo_placeholders():
    """Only the template may carry TODOs; a real rule set must be fully specified."""
    real = [p for p in RULESETS.rglob("*.yaml") if p.name not in {"schema.yaml", "_template.yaml"}]
    assert real, "expected at least one real rule-set file"
    for path in real:
        assert "TODO" not in path.read_text(), f"unresolved TODO in {path.name}"
