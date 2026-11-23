"""Skip guard for lexicon-builder tests that read the real, local-only source files.

The sources live in gitignored `data/external` and `~/nltk_data/corpora`, so a fresh
clone (and CI) does not have them. These paths are the builder's CLI defaults, which
the guarded tests pass explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SOURCES = Path("data/external")
NLTK = Path.home() / "nltk_data/corpora"
REQUIRED = (
    SOURCES / "usas/semantic_lexicon_en.tsv",
    SOURCES / "concreteness.csv",
    SOURCES / "lancaster_sensorimotor.csv",
    SOURCES / "nrc_vad.txt",
    SOURCES / "nrc_emotion.txt",
    NLTK / "framenet_v17/luIndex.xml",
    NLTK / "verbnet",
)
MISSING = tuple(str(path) for path in REQUIRED if not path.exists())

requires_lexicon_sources = pytest.mark.skipif(
    bool(MISSING), reason=f"local lexicon sources absent: {', '.join(MISSING)}"
)
