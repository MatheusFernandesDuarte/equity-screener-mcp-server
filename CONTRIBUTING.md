# Contributing

## Setup

```bash
git clone <repo>
cd yahoo_finance_service
uv sync
uv run pytest tests/ -v    # verify everything passes
```

Python 3.11+ required. No browser needed to run the test suite.

---

## Development rules

- **TDD enforced** — write the failing test first, then the implementation
- **No broken commits** — all tests must pass before committing
- **Small commits** — one logical change per commit, conventional commit messages
- **No Selenium outside `src/scraper/engine.py`** — this boundary is a hard rule

### Commit format

```
feat(scope): short description
fix(scope): short description
refactor(scope): short description
test(scope): short description
docs(scope): short description
```

---

## Running tests

```bash
uv run pytest tests/ -v               # all tests
uv run pytest tests/test_engine.py    # single module
uv run pytest -k "test_search"        # by name pattern
```

All tests are fast (<10s total), deterministic, and require no external services.

---

## Adding a new AI provider

See [docs/extending-providers.md](docs/extending-providers.md) for a full walkthrough.

Short version:
1. Create `src/ai/your_provider.py` implementing `AIProvider`
2. Register it in `src/ai/factory.py` `_PROVIDERS` dict
3. Add the required API key env var
4. Write tests in `tests/test_ai_providers.py`

---

## Adding a new region

Regions are strings passed to the scraper. No code change needed — just pass any region name that exists in the Yahoo Finance screener:

```bash
python run.py "United Kingdom"
python run.py Japan
```

---

## Pull requests

1. Fork and create a branch: `git checkout -b feat/your-feature`
2. Write tests first
3. Implement
4. Run `uv run pytest tests/` — must be green
5. Open a PR against `main` with a clear description of what and why
