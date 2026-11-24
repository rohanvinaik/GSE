"""Expose repository scripts consistently for both supported pytest entry points.

The console entry point does not put the working directory on sys.path as
``python -m pytest`` does. Tests exercise operational scripts as well as the
installed gse package, so establish that source root explicitly at collection.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# Scoped runs. Every test is marked with the GSE areas its file imports, derived from the code at
# collection, so `uv run pytest -m symbolic` runs the tests of one area without a hand-kept list.
# The large curation area is split into its lexicon builder and external sources.
import ast  # noqa: E402
from functools import lru_cache  # noqa: E402

GSE_DIR = Path(ROOT) / "GSE"
CURATION_AREAS = ("lexicon_builder", "external_sources")


def _areas() -> frozenset[str]:
    names = {
        path.stem if path.suffix == ".py" else path.name
        for path in GSE_DIR.iterdir()
        if not path.name.startswith(("_", "."))
        and (path.suffix == ".py" or (path.is_dir() and (path / "__init__.py").exists()))
    }
    return frozenset(names | set(CURATION_AREAS))


AREAS = _areas()


@lru_cache(maxsize=None)
def _file_areas(path: str) -> frozenset[str]:
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except OSError, SyntaxError, UnicodeDecodeError:
        return frozenset()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        elif isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            parts = module.split(".")
            if parts[0] != "GSE" or len(parts) < 2:
                continue
            area = parts[1]
            if area == "curation" and len(parts) > 2 and parts[2] in CURATION_AREAS:
                area = parts[2]
            found.add(area)
    return frozenset(found & AREAS)


def pytest_configure(config):
    for area in sorted(AREAS):
        config.addinivalue_line("markers", f"{area}: the test's file imports GSE.{area} (marked automatically)")


def pytest_collection_modifyitems(config, items):
    for item in items:
        for area in sorted(_file_areas(str(item.path))):
            item.add_marker(area)
