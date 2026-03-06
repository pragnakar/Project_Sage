# Contributing to SAGE

Thank you for your interest in contributing. This document covers the development setup, test instructions, and conventions.

---

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- Git

### Install from source

```bash
git clone https://github.com/pragnakar/sage
cd sage

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install both packages in editable mode
pip install -e sage-core/[dev]
pip install -e sage-mcp/[dev]
```

### Verify the install

```bash
python -m pytest sage-core/tests/ -q   # should show ~382 passing
python -m pytest sage-mcp/tests/ -q    # should show ~72 passing
python -m sage_mcp --help 2>&1 | head  # prints nothing (stdio mode — that is correct)
```

---

## Running Tests

```bash
# All tests
python -m pytest

# One package
python -m pytest sage-core/tests/
python -m pytest sage-mcp/tests/

# One module
python -m pytest sage-mcp/tests/test_examples.py -v

# Stop on first failure
python -m pytest -x
```

Tests are co-located with their packages:
```
sage-core/tests/    # 382 tests — solver, builder, fileio, explainer, models
sage-mcp/tests/     # 72 tests — 7 MCP tools, state sequences, error handling, examples
```

---

## Branch Conventions

| Branch | Purpose |
|---|---|
| `main` | Stable release — only merge from `develop` via PR |
| `develop` | Integration branch — target for feature branches |
| `feature/<name>` | New feature or phase |
| `fix/<name>` | Bug fix |
| `docs/<name>` | Documentation only |

Workflow:
```bash
git checkout develop
git checkout -b feature/my-feature
# ... work ...
git push origin feature/my-feature
# Open PR → develop
```

---

## Code Conventions

- **Formatter**: `ruff format` (line length 100)
- **Linter**: `ruff check` (see `ruff.toml`)
- **Types**: All public functions must have type annotations
- **Docstrings**: Module, class, and public function docstrings required
- **No print()**: Use `logging` in production code
- **Error handling**: All MCP tool handlers must return structured error text — never raise

Run linting:
```bash
ruff check sage-core/ sage-mcp/
ruff format --check sage-core/ sage-mcp/
```

---

## Adding a New Problem Type

1. **Model** — Add a new Pydantic model in `sage-core/sage_core/models.py`
2. **Builder** — Add `build_from_<type>` in `sage-core/sage_core/builder.py`
3. **Solver** — Add a solver path in `sage-core/sage_core/solver.py`
4. **File I/O** — Add `_parse_<type>` and `_gen_<type>_template` in `sage-core/sage_core/fileio.py`
5. **Explainer** — Update `explain_result` in `sage-core/sage_core/explainer.py`
6. **MCP server** — Update `_detect_model_type` and `_parse_model` in `sage-mcp/sage_mcp/server.py`
7. **Tests** — Add tests to both `sage-core/tests/` and `sage-mcp/tests/`

---

## Submitting Changes

1. Write tests for your change. New features need unit + integration tests.
2. All tests must pass: `python -m pytest`
3. Linting must be clean: `ruff check . && ruff format --check .`
4. Update `BUILD_LOG.md` with a summary of what changed
5. Open a pull request targeting `develop`

---

## Reporting Bugs

Open an issue on GitHub with:
- Python version
- Package version (`pip show sage-mcp`)
- The model JSON or file that caused the problem
- The full error message (including any MCP response text)
