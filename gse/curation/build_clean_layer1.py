"""Rebuild Layer-1 of the clean lexicon from the scoped external sources.

The reproducible build (the earlier one-off was lost). Policy, confirmed with
Rohan 2026-06-20:

  * **tier-0** primes are axioms (`canonical_decomposition`) — skipped here, they
    already live in the clean DB.
  * **WordNet IS-A** is the *category* source, **authoritative within its scope**
    (SUBSTANTIVES): a scoped category vote counts even as a single source, exactly
    as each source owns its domain and tier-0 owns the primes.
  * **Every other source** (affect / perception) must clear the **A-filter**:
    a primitive is kept only with ≥2 agreeing sources (drops single-source noise,
    incl. Lancaster-only perceptual — the "B" gate).
  * **`wiktionary_v2` is dropped** — it is the degenerate source this rebuild
    replaces; leaving it in re-introduced the dense `dog≈murder` decompositions.

Everything is the *existing* pipeline — `integrator` parsers → `filter_votes_by_scope`
→ `aggregate_weighted`. No new decomposition mechanism.
"""

from __future__ import annotations

import logging
import sqlite3
import time

from gse.curation.external_sources.integrator import ExternalSourcesIntegrator
from gse.curation.external_sources.source_scope import filter_votes_by_scope
from gse.curation.external_sources.tier_0_dispatch import canonical_decomposition
from gse.curation.external_sources.weighted_voting import aggregate_weighted

logger = logging.getLogger(__name__)

CLEAN_DB = "data/lexicon_clean.db"
FREQ_DB = "data/frequency.db"
CATEGORY_SRC = "wordnet_hierarchy"  # authoritative within its (SUBSTANTIVES) scope
DROP_SOURCES = {"wiktionary_v2"}  # the degenerate source being replaced
DEFAULT_CONF = 0.79

# Evidence FAMILIES — the correlation structure of the source set. The gate
# counts agreeing FAMILIES (convergence of independent evidence), and the map
# encodes exactly which sources are near-duplicates of which:
#
#   * The original 7 sources are mutually INDEPENDENT datasets (SentiWordNet /
#     NRC-Emotion / NRC-VAD are different methodologies over different data;
#     their within-set agreement is load-bearing — hate's GOOD:-1 comes from
#     exactly that pair). Each keeps its own family, so the original build's
#     behavior is preserved verbatim.
#   * FrameNet and PropBank are the same KIND of evidence as VerbNet (verb
#     rolesets / frames over the same verbs) — one family. Their mutual
#     agreement is one observation counted twice, not convergence (measured
#     2026-07-01: source-level gating densified the lexicon 1.86→2.9+
#     primes/word and collapsed the dual margin).
#   * ConceptNet and USAS are both broad categorical/topical taggers — one
#     family, for the same reason.
SOURCE_FAMILY = {
    "verbnet": "verb_structure",
    "framenet": "verb_structure",
    "propbank": "verb_structure",
    "conceptnet": "topical",
    "usas": "topical",
}


def build_word(integrator: ExternalSourcesIntegrator, word: str):
    """Layer-1 decomposition for one word, or None if not grounded here."""
    if canonical_decomposition(word):
        return None  # tier-0 axiom, already in the clean DB
    votes = {}
    for name, parser in integrator.parsers.items():
        if name in DROP_SOURCES:
            continue
        conf_aware = getattr(parser, "to_primitives_with_confidence", None)
        if callable(conf_aware):
            pw = conf_aware(word)
        else:
            pw = {p: (v, 1.0) for p, v in parser.to_primitives(word).items()}
        adjusted = {p: (v, (c if c < 1.0 else DEFAULT_CONF)) for p, (v, c) in pw.items()}
        adjusted = filter_votes_by_scope(name, adjusted)
        if adjusted:
            votes[name] = adjusted
    if not votes:
        return None
    agg = aggregate_weighted(word, votes)
    keep = {}
    for prim, vote in agg.primitives.items():
        if vote.value == 0:
            continue
        srcs = set(vote.contributing_sources)
        families = {SOURCE_FAMILY.get(s, s) for s in srcs}
        # WordNet authoritative in-scope OR agreement across independent
        # evidence FAMILIES (see SOURCE_FAMILY — never two correlated sources).
        if CATEGORY_SRC in srcs or len(families) >= 2:
            keep[prim] = vote.value
    return keep or None


def main(clean_db: str = CLEAN_DB, freq_db: str = FREQ_DB) -> dict:
    logging.basicConfig(level=logging.ERROR)
    it = ExternalSourcesIntegrator()
    it.load_all_sources()
    sources = [s for s in it.parsers if s not in DROP_SOURCES]
    logger.info("sources: %s", sources)

    fc = sqlite3.connect(f"file:{freq_db}?mode=ro", uri=True)
    words = fc.execute("SELECT word, combined_rank FROM frequency ORDER BY combined_rank").fetchall()
    fc.close()

    built = {}
    t0 = time.time()
    for i, (w, rank) in enumerate(words):
        lemma = w.lower().strip()
        d = build_word(it, lemma)
        if d:
            built[lemma] = (rank, d)
        if (i + 1) % 4000 == 0:
            print(f"  {i + 1}/{len(words)} grounded={len(built)} {time.time() - t0:.0f}s", flush=True)
    it.close()

    con = sqlite3.connect(clean_db)
    old = [r[0] for r in con.execute("SELECT id FROM lexemes WHERE source='layer1'")]
    con.executemany("DELETE FROM primitive_values WHERE lexeme_id=?", [(i,) for i in old])
    con.execute("DELETE FROM lexemes WHERE source='layer1'")
    # Collision policy (the layered design): Layer-2 exists only for words the
    # sources didn't ground — a word the sources NOW ground supersedes its old
    # genus-chain row. Grammatical lemmas (tier_0 / operators / quantifiers) are
    # never displaced: a content decomposition for one is a scope leak — skip it.
    existing = {r[1]: (r[0], r[2]) for r in con.execute("SELECT id, lemma, source FROM lexemes")}
    superseded = skipped = 0
    for lemma, (rank, d) in built.items():
        prior = existing.get(lemma)
        if prior is not None:
            pid, psrc = prior
            if psrc == "layer2":
                con.execute("DELETE FROM primitive_values WHERE lexeme_id=?", (pid,))
                con.execute("DELETE FROM lexemes WHERE id=?", (pid,))
                superseded += 1
            else:
                skipped += 1
                continue
        cur = con.execute(
            "INSERT INTO lexemes(lemma,pos,sense_id,source,frequency_rank,confidence,validation_status)"
            " VALUES(?,?,?,?,?,?,?)",
            (lemma, "x", "0", "layer1", rank, 1.0, "grounded"),
        )
        con.executemany(
            "INSERT INTO primitive_values(lexeme_id,primitive,value,confidence,source) VALUES(?,?,?,?,?)",
            [(cur.lastrowid, p, v, 1.0, "layer1") for p, v in d.items()],
        )
    con.commit()
    tier0 = con.execute("SELECT count(*) FROM lexemes WHERE source='tier_0'").fetchone()[0]
    layer1 = con.execute("SELECT count(*) FROM lexemes WHERE source='layer1'").fetchone()[0]
    con.close()
    stats = {
        "layer1": layer1,
        "tier_0": tier0,
        "superseded_layer2": superseded,
        "skipped_grammatical": skipped,
        "seconds": round(time.time() - t0, 1),
    }
    print(
        f"WROTE {clean_db}: tier_0={tier0}, layer1={layer1} "
        f"(superseded {superseded} layer2 rows, skipped {skipped} grammatical)  "
        f"({stats['seconds']}s)"
    )
    return stats


if __name__ == "__main__":
    main()
