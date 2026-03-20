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
