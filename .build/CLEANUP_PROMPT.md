# Cleanup Task: Remove stale build/lib directory and prevent recurrence

## Context

`sage-solver-cloud/build/lib/sage_cloud/` contains 18 stale `.py` files from a previous `python setup.py build` run. Even though `build/` is in `.gitignore`, these files exist on disk and have caused repeated import conflicts — Python sometimes loads modules from `build/lib/` instead of the source directory, silently running old code. This cost us hours of debugging (broken pipe errors, missing traceback logging, stale pause/resume endpoints).

The project uses PEP 660 editable installs (`pip install -e .`), so `build/lib/` serves no purpose.

## What to do

1. **Delete the stale build directory:**
   ```bash
   rm -rf sage-solver-cloud/build/
   ```

2. **Add a safety guard in `reinstall.sh`** — after the pip installs, add a cleanup step:
   ```bash
   # Remove stale build artifacts that can shadow editable installs
   rm -rf sage-solver-core/build/ sage-solver-mcp/build/ sage-solver-cloud/build/
   ```
   Read the existing `reinstall.sh` first to understand its structure, then add this cleanup at the appropriate place (after pip installs, before any "done" message).

3. **Add a `conftest.py` guard in `sage-solver-cloud/`** (project root level) that detects and warns if `build/lib/` exists at test time:
   ```python
   import warnings
   from pathlib import Path

   _build_lib = Path(__file__).parent / "build" / "lib"
   if _build_lib.exists():
       warnings.warn(
           f"Stale build/lib/ detected at {_build_lib}. "
           "This can shadow editable installs and cause import conflicts. "
           "Run: rm -rf sage-solver-cloud/build/",
           stacklevel=1,
       )
   ```

4. **Verify** — after cleanup, run:
   ```bash
   cd sage-solver-core && python -m pytest tests/ -v
   ```
   All 439 tests should still pass.

## What NOT to do

- Do NOT modify any source code in `sage_solver_core/`, `sage_solver_mcp/`, or `sage_cloud/`
- Do NOT change `.gitignore` (it already covers `build/`)
- Do NOT run `python setup.py build` — we use `pip install -e .` exclusively
