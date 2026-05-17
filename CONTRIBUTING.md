# Contributing to science-cli

Thanks for your interest! This is a research tool for memristor and electrochemistry data analysis.

## Getting Started

```bash
git clone https://github.com/taixuann/science-cli.git
cd science-cli
pip install -e .
pytest
```

## Development Workflow

1. **Check existing PLANs** in `documentation/plans/` before starting work
2. **Create a PLAN** for any non-trivial change (see `AGENTS.md` for template)
3. **Implement** following existing code style (type hints, f-strings, pathlib)
4. **Test** — run `pytest` to verify no regressions
5. **Update docs** — README.md, AGENTS.md, relevant module READMEs
6. **Commit** with descriptive message referencing the PLAN

## Code Style

- Python 3.9+, type hints required for all public functions
- Follow PEP 8 (enforced by ruff)
- Use pathlib, not `os.path`
- Use f-strings, not `%` or `.format()`
- Core modules (`core/`) must not import from `cli/`

## Test Requirements

- All guardrail tests in `test_guardrails.py` must pass
- New features should include pytest tests in `tests/`
- Run: `pytest`

## Branch Convention

- `main` — stable releases
- `refactor/*` — major refactoring branches
- `feature/*` — feature branches
