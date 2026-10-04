"""agent_eligibility — a CONSTRAINT cassette: WHAT KIND of referent is this, so the right frames fire?

The engine keys ``x is a person`` off an entity's emitted ``type_thread``, and an entity with an EMPTY
thread defaults to person-eligible. So a PLACE (``bosnia``) or a plural people-COLLECTIVE
(``patriots``/``loyalists``/``powers``) with no thread fires the person-typed frames (relationship
objectification, narrative_base harm-chains, creation, victory…) as if it were an individual person —
the dominant noise class in the 2026-07-01 stress-test (~63 hits).

This cassette answers, per referent, WHICH of three kinds it is — reading the SAME multi-scale grounding
every cassette composes, with sparse-wiki world-type as the load-bearing signal:

  PERSON  an individual — leave its typing alone.
  GROUP   a people-collective (a demonym / ethnic group / organisation / a plural person-noun) — re-type
          ``group``: NON-person, so interpersonal frames self-reject it, but still an ANIMATE agent (a
          freed people is a valid liberation captive — Step B).
  PLACE   a location (settlement / country / region) — re-type ``location``: non-person AND non-animate,
          so BOTH interpersonal frames and liberation/aid reject it (a place is not freed as a captive).

Discipline (mirrors person_validation): fire ONLY on POSITIVE non-person evidence; a genuine person, or
a referent with no discriminating signal, is left UNTOUCHED (abstain-keep) — never re-type a real
person-agent. The verdicts become a ``{lemma: type_thread}`` re-type map applied at the
``from_document(repair=)`` seam by ``cheatsheet.make_retype_repair`` (non-destructive: only the type is
set, the name/id/predicates are intact)."""

from __future__ import annotations

from typing import Dict, Optional

from .multiscale import MultiScaleDoc
from .person_validation import _facets, _is_person_safe, _world_threads

# sparse-wiki / DBpedia world-type roots. PLACE and GROUP are the two non-person animate/inanimate kinds.
_PLACE_WORLD = frozenset(
    {
        "Place",
        "PopulatedPlace",
        "Settlement",
        "Location",
        "Region",
        "Country",
        "City",
        "Town",
        "Village",
        "Continent",
        "Island",
        "River",
        "Mountain",
        "Building",
        "Territory",
        "State",
        "Province",
    }
)
_GROUP_WORLD = frozenset(
    {
        "EthnicGroup",
        "Organisation",
        "Organization",
        "Company",
        "Band",
        "SportsTeam",
        "MilitaryUnit",
        "PoliticalParty",
    }
)
_PLACE_WORDNET = frozenset({"location", "region", "district", "geographical_area"})
_GROUP_WORDNET = frozenset({"social_group", "people", "nation", "organization"})


class AgentEligibility:
    """Classify each referent PERSON / GROUP / PLACE and emit a ``{lemma: type_thread}`` re-type map for
    the non-person kinds. Not routed through the merge deck — it is a direct multi-scale classifier
    (the cheat-sheet's re-type companion to the merge/veto cassettes)."""

    name = "agent_eligibility"

    def classify(self, doc: MultiScaleDoc) -> Dict[str, tuple]:
        out: Dict[str, tuple] = {}
        for eid, ms in doc.by_id.items():
            # a representative mention: prefer a PROPN (the naming mention)
            rep = next((m for m in ms if m.pos == "PROPN"), ms[0] if ms else None)
            if rep is None:
                continue
            lemma = rep.lemma
            if lemma in out:
                continue
            kind = self._kind(doc, rep, ms)
            if kind == "PLACE":
                out[lemma] = ("location",)
            elif kind == "GROUP":
                out[lemma] = ("group",)
        return out

    def _kind(self, doc: MultiScaleDoc, rep, ms) -> Optional[str]:
        """PERSON (None → leave) unless POSITIVE evidence of PLACE or GROUP."""
        lemma = rep.lemma
        wn = _is_person_safe(lemma)  # True person / False non-person / None unknown
        # The WHOLE ranked candidate set, not candidates[0]: the token-alias table makes a
        # bare forename/surname ('washington', 'louis') rank a place first with the person
        # behind it — kind-level verdicts on the pagerank-primary alone would re-type a
        # possible person. Heterogeneous kinds → disambiguation needed → abstain-keep.
        world = set().union(*_world_threads(doc, lemma)) or set()
        facets = _facets(doc, lemma)
        dom = set(facets.get("DOMAIN", ()) if isinstance(facets, dict) else ())

        # --- POSITIVE person evidence SHORT-CIRCUITS the guessers (abstain-keep).
        #     A Person/Deity candidate ANYWHERE in the set (post-backfill, ~74K typed
        #     persons) or the DOMAIN=People facet (39K entities) outranks the WordNet
        #     fallback: a PROPN person whose name collides with a non-person entity must
        #     never be guessed into a PLACE. A possible world individual is not a
        #     GROUP either, so the demonym/plural heuristics are skipped too. ---
        if world & {"Person", "Deity"} or (dom & {"People"} and not (world & _GROUP_WORLD)):
            return None

        # --- PLACE: POSITIVE evidence only — the world strand types it a place,
        #     or WordNet-nonperson WITH a geographic facet. The former bare-PROPN
        #     guess ("wn says non-person and it's a name → call it a place") is
        #     REMOVED: it was the branch that over-typed protagonists as locations
        #     (Viola → the instrument → "location"; the 2026-07-01 disable in
        #     gse_emit_narrative). Its motivating case — "bosnia: wn=False, no
        #     world" — no longer exists: the alias backfill gives partial labels
        #     their world thread, so a real place is caught by the world branch.
        #     Shallow/unknown → abstain-keep, per the cassette law.
        #     PRIMARY-sense person words are excluded: a person-word colliding with
        #     a world place NAME ("thane" → Thane, India) is a CONFLICT, and conflict
        #     → abstain-keep, never a re-type (the story's thane is a lord, not the
        #     Indian city). Primary sense, NOT the any-sense union — a stray person
        #     homograph ("france" → Anatole France) must not shield a country.
        #     ANCHOR-CORROBORATED: a world place reading must be corroborated by the
        #     DOCUMENT (≥1 of the entity's semantic anchors appears in the raw text —
        #     sparse-wiki's ground(mention, context)). The failure class is a WRONG
        #     REFERENT: 'santiago' the fisherman would ground to the Chilean city
        #     (0/20 anchors in-doc) and be re-typed a location; every genuine place
        #     in the corpus corroborates ≥1 (france/bosnia/cawdor/everest — measured
        #     2026-07-01). Uncorroborated world-place → abstain-keep, ALL branches
        #     (a contradicted world reading must not fall through to the WordNet
        #     branch — the wrong referent is wrong in both strands). ---
        anchored = _anchors_in_doc(doc, lemma)
        # --- GROUP evidence is WordNet/facet-side (plural person-noun, demonym, ethnic/org)
        #     and is judged INDEPENDENTLY of the anchor gate: an uncorroborated world
        #     reading discredits a PLACE verdict, not the plural/demonym signal. ---
        is_group = self._is_group(doc, rep, ms, wn, world, dom)
        if anchored is not False:  # the PLACE verdicts, anchor-gated as a block
            if _is_primary_person_safe(lemma) is not True and (
                world & _PLACE_WORLD or set(_lower(world)) & _PLACE_WORDNET
            ):
                return "PLACE"
            if wn is False and not is_group and dom & {"Geography"}:
                return "PLACE"
            # word strand's POSITIVE place signal — the WordNet-primary-sense location
            # check (scotland/navy carry honest ["Thing"] world stubs, but WordNet
            # types their primary identity a location). Positive evidence, not a guess.
            if wn is not True and not is_group and _is_location_safe(lemma) is True:
                return "PLACE"

        # --- GROUP: world says ethnic/org, OR a demonym (Geography domain on a PERSON word), OR a plural
        #     person-noun (patriots/loyalists), OR wordnet social_group ---
        if is_group:
            return "GROUP"
        return None

    def _is_group(self, doc, rep, ms, wn, world, dom) -> bool:
        if world & _GROUP_WORLD or set(_lower(world)) & _GROUP_WORDNET:
            return True
        # a plural PERSON-noun is a collective, not an individual (patriots/loyalists/powers) —
        # corroborated by the DEFINITE-COLLECTIVE surface form in the raw text: a people takes
        # "the" ("the Ottomans", "the Russians"); a bare -s SURNAME never does ("Adams" the
        # climber, stem "adam" a person word) — without the corroboration, abstain-keep.
        if wn is True and _is_plural(rep, ms) and _definite_in_raw(doc, rep.lemma):
            return True
        # a demonym: a geographic-domain word that IS a person (Russian/Germanic) → a people
        if wn is True and (dom & {"Geography"}):
            return True
        return False


def _lower(strings) -> list:
    return [s.lower() for s in strings]


def _anchors_in_doc(doc, lemma: str):
    """Tri-state anchor corroboration for a mention's world reading (the wrong-referent
    detector): True = ≥1 of the entity's semantic anchors appears in the raw text;
    False = the entity has anchors and NONE appear (the 'santiago'-the-fisherman class);
    None = nothing to consult (no store / no anchors / no raw) — never gates."""
    raw = getattr(doc, "raw", None)
    store = getattr(doc, "store", None)
    if not raw or store is None or not hasattr(store, "anchors"):
        return None
    try:
        bag = store.anchors(lemma) or {}
    except Exception:
        return None
    if not bag:
        return None
    import re

    low = raw.lower()
    for a in bag:
        if a and re.search(r"\b" + re.escape(a) + r"\b", low):
            return True
    return False


def _definite_in_raw(doc, lemma: str) -> bool:
    """Does the raw text ever use ``the <lemma>``? The definite-collective corroboration for the
    plural-person GROUP heuristic. Missing raw text → not corroborated (abstain-keep)."""
    raw = getattr(doc, "raw", None)
    if not raw or not lemma:
        return False
    import re

    return re.search(r"\bthe\s+" + re.escape(lemma) + r"\b", raw, re.IGNORECASE) is not None


def _is_location_safe(lemma: str):
    try:
        from gse.symbolic.grounding import _is_location

        return _is_location(lemma)
    except Exception:
        return None


def _is_primary_person_safe(lemma: str):
    try:
        from gse.symbolic.grounding import _is_primary_person

        return _is_primary_person(lemma)
    except Exception:
        return None


def _is_plural(rep, ms) -> bool:
    if getattr(rep, "number", None) == "plural":
        return True
    if any(getattr(m, "number", None) == "plural" for m in ms):
        return True
    # morphological fallback: an un-lemmatized plural person-noun ("ottomans"/"russians") ends
    # in -s AND its de-pluralized stem is itself a person word — the stem check kills the
    # -is/-us/-os name class ("louis" → "loui" is no word → NOT a plural collective).
    if not (rep.lemma.endswith("s") and len(rep.lemma) > 3 and not rep.lemma.endswith("ss")):
        return False
    return _is_person_safe(rep.lemma[:-1]) is True
