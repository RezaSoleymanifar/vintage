"""The data layer may not import the engine.

Vintage is a data library that happens to ship a backtester, not a backtester
that happens to fetch data. The dependency runs one way, engine reads data.
And this test is what keeps it that way once someone is in a hurry.

If this fails, the fix is never to loosen the test. It is to move whatever
computation reached for the engine out of the data layer.
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "vintage"

# Everything that answers "what was known, and when".
DATA_MODULES = ["cache.py", "envelope.py", "http.py", "pit.py", "registry.py", "sources"]


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            # level counts the dots: `from ..engine import x` is level 2.
            prefix = "." * node.level
            found.add(f"{prefix}{node.module or ''}")
    return found


def _data_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for name in DATA_MODULES:
        target = SRC / name
        if target.is_dir():
            files.extend(sorted(target.glob("*.py")))
        elif target.exists():
            files.append(target)
    return files


def test_data_layer_does_not_import_engine() -> None:
    offenders: list[str] = []
    for path in _data_files():
        for name in _imports(path):
            stripped = name.lstrip(".")
            if stripped == "engine" or stripped.startswith("engine."):
                offenders.append(f"{path.relative_to(SRC)} imports {name}")
            if stripped.startswith("vintage.engine"):
                offenders.append(f"{path.relative_to(SRC)} imports {name}")
    assert not offenders, (
        "the data layer reached into the engine:\n  " + "\n  ".join(offenders)
    )


def test_data_layer_has_files_to_check() -> None:
    """A guard that silently checks nothing is worse than no guard."""
    assert len(_data_files()) > 5
