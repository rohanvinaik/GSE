"""Word-scale morphological operations — the comparative/superlative slice.

The first instance of *morphology-as-operation* (``docs/MORPHOLOGY_RESEARCH_BRIEF.md``).
An inflected surface collapses to ``base × grammatical-feature`` via the same
propose→coherence-resolve shape as :mod:`gse.nlp.contractions`:

1. **marker** — an inflectional process on the surface triggers the operation
   (here ``-er``/``-est``, or a suppletive degree form).
2. **propose base candidate(s)** — the *inverse formation model*: the four regular
   English orthographic processes (bare / silent-``e`` / gemination / ``y→i``) run
   BACKWARD. A small, closed generator — not a per-word table, not a lookup DB.
3. **resolve by coherence** — keep the candidate that GROUNDS as a gradable
   adjective (WordNet, the token-layer lexical oracle). The oracle, not a rule
   order, decides — which also resolves the ``-er`` collision for free: comparative
   ``bigger`` (base ``big`` grounds) vs agentive ``teacher`` (``teach`` is a verb,
   not gradable → declines) vs non-morphemic ``water`` (no base grounds → declines).

The orthographic facts of English are encoded ONCE here, as the *definition* of the
operation, gated by the grounding oracle — categorically different from an ad-hoc
suffix-strip or a runtime DB. The base is the word-lens identity (the lemma); the
degree is the sentence-lens half of the decomposition.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from nltk.corpus import wordnet as wn

# The degree feature carried alongside the base (the sentence-lens half of the
# decomposition). Recorded by the operation; a future slice rides it on the `morph`
# channel once a consumer exists (MORPH_TO_TAM ignores unknown features).
COMPARATIVE = "Degree=Cmp"
SUPERLATIVE = "Degree=Sup"

# Word-scale negation features. NEGATION = the evaluative sign-flip
# (``unhappy`` = NOT(happy)); REVERSAL = action undoing (``unlock`` = undo lock),
# a distinct, non-sign-flip semantics handled recognition-only in v1.
NEGATION = "Polarity=Neg"
REVERSAL = "Reversal=Yes"

# Negation prefixes and whether each can also form a VERB reversal. ``un-``/``dis-``
# form both adjectival negation (unkind/disloyal) AND verb reversal
# (unlock/disconnect); ``in-``/``im-``/``il-``/``ir-``/``non-`` are negation-only.
# Over-proposing is harmless — the grounding gate (a real adjective/verb must exist)
# rejects false prefixes (uncle→cle, income→come-but-in-is-negation-only, internal→ternal).
_NEG_PREFIXES = (
    ("un", True),
    ("dis", True),
    ("non", False),
    ("im", False),
    ("il", False),
    ("ir", False),
    ("in", False),
)

# Suppletive degree forms — a FINITE closed list (a fact of the language, like the
# irregular-verb table; legitimately enumerable, NOT the rejected lookup DB).
# Restricted to the unambiguous adjective suppletives; the overloaded quantifier
# degrees (more/most/less/least) are deferred — they are periphrastic markers and
# determiners, a separate concern.
_SUPPLETIVE_DEGREE = {
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "further": "far",
    "furthest": "far",
    "farther": "far",
    "farthest": "far",
}
# (elder/eldest excluded — too often nominal: "the elder", "village elder".)


def _is_gradable_adjective(word: str) -> bool:
    """The grounding oracle at the token layer: a known adjective (WordNet ``a``/``s``
    synsets). Adjectives are the gradable category, so a verb base (``teach``) or a
    non-word (``wat``/``togeth``) fails — which is exactly what declines the ``-er``
    collision and the false strips."""
    return bool(wn.synsets(word, pos="a") or wn.synsets(word, pos="s"))


def _candidate_bases(stem: str) -> List[str]:
    """Inverse comparative/superlative formation — the four regular orthographic
    processes run BACKWARD, proposing base candidates. The grounding oracle selects,
    so over-proposing is harmless; the set is closed (the four processes), not open.

    bare ``tall(er)→tall`` · silent-``e`` ``larg(er)→large`` · gemination
    ``bigg(er)→big`` · ``y→i`` ``earli(er)→early``.
    """
    cands = [stem, stem + "e"]
    if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
        cands.append(stem[:-1])  # gemination: bigg → big
    if stem.endswith("i"):
        cands.append(stem[:-1] + "y")  # y→i: earli → early, happi → happy
    return cands


def resolve_degree(surface: str) -> Optional[Tuple[str, str]]:
    """The comparative/superlative operation: ``surface → (base, degree-feature)``,
    or ``None`` when ``surface`` is not a degree form.

    Suppletive forms resolve via the finite list; otherwise strip ``-est``/``-er``
    and select the PROPOSED base that grounds as a gradable adjective. A word that
    merely ends in ``-er``/``-est`` without a grounding base (``together``, ``water``,
    ``teacher``) returns ``None`` — it is not a degree form.
    """
    low = surface.lower()
    if low in _SUPPLETIVE_DEGREE:
        feat = SUPERLATIVE if low.endswith("st") else COMPARATIVE
        return _SUPPLETIVE_DEGREE[low], feat
    for suffix, feat in (("est", SUPERLATIVE), ("er", COMPARATIVE)):
        if low.endswith(suffix) and len(low) > len(suffix) + 1:
            stem = low[: -len(suffix)]
            # The complete surface's lexical adjective reading licenses which
            # orthographic candidate is its base. Merely finding *an* adjective
            # (number -> numb, forest -> fore, cuter -> cut) is insufficient.
            surface_known = bool(wn.synsets(low))
            licensed = {lemma.name() for syn in wn.synsets(low, pos="a") for lemma in syn.lemmas()}
            for cand in _candidate_bases(stem):
                if _is_gradable_adjective(cand) and (not surface_known or cand in licensed):
                    return cand, feat
            return None  # ends in the suffix but no base grounds → not a degree form
    return None


def negation_evidence(surface: str) -> dict:
    """Evidenced negation/reversal, with lexical identity preceding apparent prefixes.

    Known surfaces require a WordNet antonym link to the stripped base. A truly
    absent surface permits productive un-/non- plus a grounded adjective.
    Other apparent prefixes remain unresolved. Reversal never flips a sign.
    """
    from gse.lexical_evidence import lookup_lexeme

    out = {
        "surface": surface,
        "policy": "gse.negation/2",
        "state": "resolved",
        "decision": "no_prefix",
        "base": None,
        "feature": None,
        "evidence": [],
    }
    low = surface.lower()
    candidates = [
        (prefix, reversal, low[len(prefix) :])
        for prefix, reversal in _NEG_PREFIXES
        if low.startswith(prefix) and len(low) > len(prefix) + 2
    ]
    if not candidates:
        return out
    lexical = lookup_lexeme(low)
    out["evidence"].append(
        {
            "source": "GSE-lexicon",
            "state": lexical["state"],
            "record": lexical["selected_record"],
            "provenance": lexical["provenance"],
        }
    )
    try:
        surface_synsets = wn.synsets(low)
        known = bool(surface_synsets) or lexical["state"] in ("primes", "no_primes")
        for prefix, allow_reversal, base in candidates:
            oppositions = [
                {"synset": syn.name(), "lemma": lemma.name(), "antonym": antonym.name()}
                for syn in surface_synsets
                for lemma in syn.lemmas()
                for antonym in lemma.antonyms()
                if antonym.name().lower() == base
            ]
            adjective = _is_gradable_adjective(base)
            if known and not oppositions:
                continue
            if not known and (lexical["state"] == "unread" or prefix not in ("un", "non")):
                continue
            if adjective:
                out.update(decision="negation", base=base, feature=NEGATION)
            elif known and oppositions and allow_reversal and wn.synsets(base, pos="v"):
                out.update(decision="reversal", base=base, feature=REVERSAL)
            else:
                continue
            out["evidence"].append(
                {
                    "source": "WordNet",
                    "prefix": prefix,
                    "base": base,
                    "opposition": oppositions,
                    "rule": "lexical-opposition" if known else "productive-adjective",
                }
            )
            return out
        if known:
            out.update(decision="lexical")
        else:
            out.update(
                state="unread" if lexical["state"] == "unread" else "unresolved",
                decision="lexical_unread" if lexical["state"] == "unread" else "unresolved_prefix",
            )
    except LookupError:
        out.update(state="unread", decision="lexical_unread")
        out["evidence"].append({"source": "WordNet", "state": "unread"})
    return out


def resolve_negation(surface: str) -> Optional[Tuple[str, str]]:
    """Tuple projection of negation_evidence; only evidenced operations compose.

    ``inside``/``under`` retain lexical identity; ``unloyal`` can compose.
    """
    evidence = negation_evidence(surface)
    if evidence["decision"] in ("negation", "reversal"):
        return evidence["base"], evidence["feature"]
    return None


def negation_admission(recognition: dict, surface: dict, base: dict, token_pos: str) -> dict:
    """Whether a recognized negative may replace the encoder's selected row.

    Selection and composition are distinct decisions. Existing lexical evidence
    can be extended only where every represented prime/sign is preserved. Generic
    POS rows are supported at this declared projection, never sense resolution.
    """
    from gse.primitives_v2 import negate_decomposition

    out = {
        "decision": "preserve",
        "code": "not_negation",
        "primitives": None,
        "token_pos": token_pos,
        "surface_record": surface.get("selected_record"),
        "base_record": base.get("selected_record"),
        "policy": "gse.negation-admission/1",
    }
    if recognition.get("feature") != NEGATION or recognition.get("state") != "resolved":
        return out
    if surface.get("state") == "unread" or base.get("state") == "unread":
        out["code"] = "lexical_unread"
        return out
    record = base.get("selected_record") or {}
    if record.get("component_type") == "closed_class" or record.get("comp_operation") or record.get("comp_primitive"):
        out["code"] = "base_closed_class_or_operator"
        return out
    if base.get("state") != "primes" or not base.get("primitives"):
        out["code"] = "base_without_primitives"
        return out
    if base.get("ambiguous") or surface.get("ambiguous"):
        out["code"] = "sense_unresolved"
        return out
    if record.get("pos") not in (None, "x", "a", "s", "ADJ", "adj"):
        out["code"] = "base_pos_mismatch"
        return out
    selected = surface.get("selected_record") or {}
    if selected and (selected.get("pos") not in (None, "x", "a", "s", "ADJ", "adj") or token_pos != "ADJ"):
        out["code"] = "surface_pos_mismatch"
        return out
    if surface.get("state") == "no_primes":
        out["code"] = "surface_lexical_zero"
        return out
    candidate = negate_decomposition(base["primitives"])
    if candidate == base["primitives"]:
        out["code"] = "base_without_bipolar_sign"
        return out
    if any(candidate.get(prime) != value for prime, value in surface.get("primitives", {}).items()):
        out["code"] = "selected_lexical_conflict"
        return out
    out.update(
        decision="compose",
        code="productive_negative" if not selected else "compatible_lexical_negative",
        primitives=candidate,
    )
    return out
