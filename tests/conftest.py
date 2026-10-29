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
