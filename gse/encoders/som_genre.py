"""SoM-backed document genre detection — the replacement for the legacy keyword bag.

Genre is resolved by the trained Society-of-Mind register router
(:mod:`gse.discourse`, the nested confidence-gated descent) over GSE's *deterministic
text profile* — operator mix, complexity, coherence, affect, register, primitive
signature — NOT by matching storytelling keywords ("once upon a time", "he said").
A narrative is recognized by its EVENT-heavy structure, not its vocabulary, so a terse
"Duncan is the king. Macbeth murders Duncan." is seen for the narrative it is.

The router resolves a ``super_register``; this maps it to the document ``Genre`` and
**abstains** (MIXED) when the gated descent cannot classify — which is the honest
behavior on hand-crafted fragments and non-prose registers, by design, not a bug.

Inference is pure numpy (:class:`gse.discourse.infer.NumpyNestedRouter`); the router
is trained offline with torch. No torch in the encoder runtime.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

# Artifact written by `python scripts/train_register_router.py --nested`.
_ARTIFACT = Path(__file__).resolve().parents[2] / "data" / "register_router.nested.pkl"


@lru_cache(maxsize=1)
def _router():
    """Load the trained nested router once. Returns None (→ the detector abstains to
    MIXED) when the artifact is absent, with a ONE-TIME visible warning — the artifact
    is rebuilt against the live encoder by `scripts/build_l2_corpus.py` +
    `train_register_router.py --nested` (the corpus and encoder must share a
    distribution; a stale corpus is train/serve skew, not a usable router). This is a
    *documented, announced* degrade, not the silent keyword fallback we removed: a
    present-but-corrupt artifact still raises."""
    from gse.discourse.infer import NumpyNestedRouter
    if not _ARTIFACT.exists():
        import sys
        print(f"[gse.som_genre] register-router artifact missing ({_ARTIFACT.name}); "
              "genre abstains to MIXED until it is (re)built — "
              "`python scripts/train_register_router.py --nested`.", file=sys.stderr)
        return None
    return NumpyNestedRouter.load(_ARTIFACT)


class SomGenreDetector:
    """Document genre via the SoM register router over the structural text profile.

    ``gate`` is the confidence floor for the super_register descent: below it the
    detector abstains (the document resolves to *no* genre at that granularity, →
    MIXED) rather than coercing a low-confidence guess into the slot.
    """

    # super_register -> the document Genre the Genesis grounds key on. The non-prose /
    # contemporary super_registers (poetry, list, reference, archaic, social, review,
    # lexically_divergent) deliberately map to nothing -> MIXED: Genesis has no ground
    # for them, and saying so honestly beats forcing a coarse label.
    SUPER_TO_GENRE = {
        "narrative": "NARRATIVE",
        "essayistic": "ARGUMENTATIVE",
        "reportorial": "EXPOSITORY",
    }

    def __init__(self, encoder, gate: float = 0.5):
        self.encoder = encoder
        self.gate = gate

    def classify(self, text: str):
        """Resolve ``text`` to (Genre, confidence). Genre.MIXED on abstention or when
        no router artifact is available yet."""
        from gse.encoders.text_structure_encoder import Genre

        router = _router()
        if router is None:                       # artifact not built yet → honest MIXED
            return Genre.MIXED, 0.0

        from gse.discourse import text_profile
        prof = text_profile(self.encoder, text)
        vec = np.asarray(prof.vector(), dtype=np.float32)
        sup, conf = router.resolve_at(vec, "super_register", gate=self.gate)
        name = self.SUPER_TO_GENRE.get(sup or "")
        if name is None:
            return Genre.MIXED, float(conf)
        return Genre[name], float(conf)
