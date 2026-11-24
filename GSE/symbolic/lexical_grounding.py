"""Bind a contextual word-strand witness to an exact dictionary definition."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError

from GSE.curation.lexicon_builder.foundation import _attested_wordnet_lemma, _exact_wordnet_ancestry
from GSE.lexicon.numerals import get_numeral_encoding, is_numeral
from GSE.nlp.native import NativeNLP
from GSE.primitives_v2 import get_hierarchy_encoding

from .expression import _NEGATION_LEMMAS, Atom
from .grounding import _COHERENCE_MARGIN, _jaccard, _select_by_coherence, _signature
from .resolution import Entity

_GENERIC = {"entity.n.01", "physical_entity.n.01", "abstraction.n.06", "object.n.01", "thing.n.12"}
_SENTENCE_BOUNDARIES = {".", "!", "?", ";", ":"}
_CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
_GENERIC_TERMS = {"act", "event", "something", "someone", "thing", "one", "be", "have", "do", "get", "make"}
_EXPLANATORY_LINKERS = {"when", "as", "because"}
_PARTICIPANT_ROOT = "person.n.01"
_PERSON_OR_COLLECTION = {_PARTICIPANT_ROOT, "group.n.01"}
_EVENT_ROOT = "event.n.01"
_MATTER_STATE_ROOT = "state_of_matter.n.01"
_TIME_MEASURE_ROOT = "time_unit.n.01"


def _anchors(features: dict) -> set[str]:
    examples = features.get("examples")
    texts = [features["definition"]]
    if isinstance(examples, list):
        texts.extend(example for example in examples if isinstance(example, str))
    return {word for text in texts for word in re.findall(r"[^\W\d_]+", text.casefold())}


@dataclass(frozen=True)
class NativeSense:
    synset: str
    nodes: frozenset[str]
    gloss: str
    anchors: frozenset[str]
    names: frozenset[str]
    examples: tuple[str, ...] = ()


class _NativeThreads:
    """Adapter of already verified snapshot threads to the existing selector."""

    def __init__(self, threads):
        self.threads = threads

    def candidates(self, lemma, pos, is_proper):
        return self.threads.get(lemma, ())


def _unique_native_witness(witnesses):
    if not witnesses:
        return {"code": "NO_DEFINITION_CONSTRUCTION_WITNESS"}
    if len(witnesses) > 1:
        return {"code": "COMPETING_DEFINITION_CONSTRUCTIONS", "construction_candidates": sorted(witnesses)}
    entry_id, evidence = next(iter(witnesses.items()))
    return {
        "code": "EXACT_WORDNET_SENSE",
        "entry_id": entry_id,
        "witness_kind": "WORDNET_DEFINITION_CONSTRUCTION",
        **evidence,
    }


@lru_cache(maxsize=8192)
def _gloss_content(gloss):
    return tuple(
        (token.lemma_, token.pos_)
        for token in NativeNLP()(gloss)
        if token.pos_ in _CONTENT_POS
        and not token.is_stop
        and not is_numeral(token.lemma_)
        and token.lemma_ not in _GENERIC_TERMS
    )


@lru_cache(maxsize=4096)
def _verb_derivations(word):
    """Exact noun targets of the verb spelling's attested WordNet pointers."""
    try:
        verbs = wn.synsets(word, pos=wn.VERB)
        return {
            synset.name(): frozenset(
                related.synset().name()
                for lemma in synset.lemmas()
                if lemma.name() == word
                for related in lemma.derivationally_related_forms()
                if related.synset().pos() == wn.NOUN
            )
            for synset in verbs
        }
    except LookupError, WordNetError:
        return {}


@lru_cache(maxsize=4096)
def _live_native_sense(sense):
    try:
        candidate = wn.synset(sense.synset)
        return candidate.definition() == sense.gloss and frozenset(candidate.lemma_names()) == sense.names
    except LookupError, WordNetError:
        return False


@lru_cache(maxsize=4096)
def _noun_thread(synset):
    try:
        return frozenset(node.name() for path in wn.synset(synset).hypernym_paths() for node in path)
    except LookupError, WordNetError:
        return frozenset()


@lru_cache(maxsize=4096)
def _noun_forms(word):
    try:
        return frozenset(wn._morphy(word.casefold(), wn.NOUN))
    except LookupError:
        return frozenset()


@lru_cache(maxsize=256)
def _catalog_reading(lemma, entry_id):
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    return next((e for e in GSEClosedClassParser().get_entries(lemma) if e.entry_id == entry_id), None)


@lru_cache(maxsize=8192)
def _native_example_signature(text, lemma=None, pos=None):
    """Complete native construction, retaining roles, operators and arguments.

    An example is a positive attestation, not an exhaustive selectional rule.
    In particular, shared examples do not authorize choosing the first sense,
    and omitted examples never exclude a reading. No bank value participates.
    """
    native_pos = {"VERB": wn.VERB, "ADJ": wn.ADJ, "ADV": wn.ADV}.get(pos)
    signature = []
    tokens = tuple(NativeNLP()(text))
    for index, token in enumerate(tokens):
        if index == len(tokens) - 1 and token.text in {".", "!", "?"}:
            continue
        word = token.lemma_.casefold()
        # Membership in the complete native inflection set is not a
        # first-stem preference. The complete source construction is still
        # required; all matching senses compete below.
        if native_pos and token.pos_ == pos and lemma in wn._morphy(token.text.casefold(), native_pos):
            word = lemma
        signature.append((word, token.pos_))
    return tuple(signature)


@lru_cache(maxsize=1)
def _primary_frames():
    """Read the existing primary-unit identities and their bounded frames.

    This is source syntax, NOT a second prime/sign registry. In particular a
    frame never supplies a bank, a negative default, or a finer WordNet sense.
    Unsupported chart notation stays unsupported rather than becoming a
    wildcard. The existing catalogue is the authority for native alignments.
    """
    from GSE.curation.lexicon_builder.catalog import _CHART_BOXES, SOURCE, foundation_prime_links

    source = Path(__file__).resolve().parents[2] / SOURCE["path"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE["sha256"]:
        raise ValueError("NSM_CHART_SOURCE_REVISION_MISMATCH")
    links = foundation_prime_links()
    frames = []
    for key, _, _, box in _CHART_BOXES:
        # Wrapped parentheses and slash alternatives are one source frame.
        lines = []
        for line in box.splitlines():
            if lines and (lines[-1].endswith("/") or lines[-1].count("(") > lines[-1].count(")")):
                lines[-1] += " " + line
            else:
                lines.append(line)
        for line in lines:
            for fragment in line.split(","):
                pending = [fragment.strip()]
                expanded = []
                while pending and len(pending) + len(expanded) < 64:
                    variant = pending.pop()
                    optional = re.search(r"\(([^()]*)\)", variant)
                    if optional:
                        pending.extend(
                            variant[: optional.start()] + value + variant[optional.end() :]
                            for value in ("", optional[1])
                        )
                        continue
                    # The chart's NP alternative is a whole proform phrase,
                    # not the nonsensical token substitution 'someone something'.
                    alternative = re.search(r"\b(someone|something) else/\s*(someone|something)\b", variant)
                    if alternative:
                        pending.extend(
                            variant[: alternative.start()] + value + variant[alternative.end() :]
                            for value in (alternative[1] + " else", alternative[2])
                        )
                        continue
                    alternative = re.search(r"\b(\w+(?:/\s*\w+)+)\b", variant)
                    if alternative:
                        pending.extend(
                            variant[: alternative.start()] + value + variant[alternative.end() :]
                            for value in re.split(r"/\s*", alternative[1])
                        )
                        continue
                    if not re.fullmatch(r"[A-Za-z ]+", variant):
                        continue
                    tokens = tuple(NativeNLP()(variant))
                    if tokens:
                        expanded.append(tokens)
                for tokens in expanded:
                    frames.append((f"nsm:v20:{key}", links[f"nsm:v20:{key}"], line, tokens))
    return tuple(frames), dict(SOURCE)


@lru_cache(maxsize=1)
def _primary_records():
    """Exact existing catalogue observations, in their JSON wire form."""
    from GSE.curation.lexicon_builder.catalog import chart_definition_records

    return {record["entry_id"]: json.loads(json.dumps(record)) for record in chart_definition_records()}


class LexicalGrounding:
    """Sentence-local grounding from the snapshot's exact WordNet records.

    Nominal anchors and type threads are the first path. When they abstain,
    a bounded grammatical construction can supply a unique native witness.
    The selected definition supplies the bank values.
    """

    def __init__(self, conn, doc, clause_linkers):
        self.conn = conn
        self.doc = doc
        self.sentence_boundaries = {token.i for token in doc if token.text in _SENTENCE_BOUNDARIES}
        self.boundaries = clause_linkers | self.sentence_boundaries
        self._by_lemma: dict[tuple[str, str], dict[str, NativeSense]] = {}

    def _senses(self, lemma, pos="NOUN"):
        key = (lemma, pos)
        if key in self._by_lemma:
            return self._by_lemma[key]
        rows = self.conn.execute(
            """SELECT d.entry_id, d.code, l.lemma, l.pos, l.gloss, o.payload
               FROM lexemes l JOIN definition_states d ON d.lexeme_id=l.id
               JOIN source_observations o ON o.entry_id=d.entry_id AND o.record_id=d.entry_id
               WHERE l.lemma=? AND o.source='wordnet_hierarchy' AND o.family='wordnet' AND o.scope='lexical'
               ORDER BY d.entry_id""",
            (lemma,),
        )
        results = {}
        eligible_pos = {
            "NOUN": {"n", "noun"},
            "VERB": {"v", "verb"},
            "ADJ": {"a", "s", "adj", "adjective"},
            "ADV": {"r", "adv", "adverb"},
        }.get(pos, set())
        for entry_id, code, word, native_pos, gloss, raw in rows:
            if native_pos not in eligible_pos or code not in {"PARTIAL", "RESOLVED"}:
                continue
            try:
                observation = json.loads(raw)
            except ValueError, TypeError:
                continue
            definition = {"entry_id": entry_id, "lemma": word, "pos": native_pos, "definition": gloss}
            nodes = _exact_wordnet_ancestry(definition, observation)
            if nodes and _attested_wordnet_lemma(definition, observation):
                features = observation["features"]
                results[entry_id] = NativeSense(
                    features["synset_name"],
                    nodes - _GENERIC,
                    gloss,
                    frozenset(_anchors(features)),
                    frozenset(features["lemma_names"]),
                    tuple(e for e in features.get("examples", ()) if isinstance(e, str)),
                )
        self._by_lemma[key] = results
        return results

    def grammatical_eligibility(self, position, lemma, entry_id):
        """Challenge a catalog role with a *local construction*, never a keyword.

        The native front-end labels closed-class spellings before reading their
        surroundings. A determined nominal followed by that token (``the ...
        symbol He``), or a positively witnessed specific native type, can
        challenge that role. Absence of a person node is NOT disjointness:
        broad ancestors such as entity/organism remain compatible with people.
        Merely mentioning a substance elsewhere cannot challenge a pronoun.
        """
        native = _catalog_reading(lemma, entry_id)
        if native is None or native.catalog != "pronoun" or native.primitives.get("SOMEONE") != 1:
            return {"code": "GRAMMATICAL_ROLE_ELIGIBLE"}
        start, end = self._bounds(position, self.sentence_boundaries)
        left = tuple(self.doc[start + 1 : position])
        right = tuple(self.doc[position + 1 : end])
        witness = None
        if (
            len(left) >= 2
            and left[0].pos_ == "DET"
            and left[-1].pos_ == "NOUN"
            and all(t.pos_ in {"ADJ", "NOUN"} for t in left[1:])
        ):
            witness = {"kind": "DETERMINED_NOMINAL_NAME", "tokens": [t.i for t in left]}
        elif (
            len(right) >= 3
            and right[0].lemma_ == "be"
            and right[0].pos_ == "AUX"
            and right[1].lemma_ in {"a", "an"}
            and (end == len(self.doc) or self.doc[end].text != "?")
        ):
            nominal = right[2:]
            # Native noun witnesses can challenge a mislabeled complement too
            # (e.g. zero-inflection ``gas`` also has a verb reading). The
            # article/copula construction, not that POS label, supplies the role.
            if nominal and all(t.pos_ in {"ADJ", "NOUN"} for t in nominal[:-1]):
                phrase = "_".join(t.lemma_ for t in nominal)
                # Read the complete nominal type (``noble gas``), not a POS
                # veto or a list of chemistry words. These are the existing
                # local WordNet type threads, never lexical-bank projections.
                types = wn.synsets(phrase, pos=wn.NOUN)
                person_ancestors = _noun_thread(_PARTICIPANT_ROOT)
                specific = {t.name() for t in types if t.name() not in person_ancestors}
                supported = {key for key, sense in self._senses(lemma).items() if sense.nodes & specific}
                if specific and len(supported) == 1:
                    witness = {
                        "kind": "ASSERTED_NATIVE_READING_TYPE",
                        "tokens": [t.i for t in right],
                        "native_type_ids": sorted(specific),
                        "supported_entry_ids": sorted(supported),
                    }
        if witness is None:
            return {"code": "GRAMMATICAL_ROLE_ELIGIBLE"}
        alternatives = sorted(self._senses(lemma))
        contextual = (
            self.select(position, lemma, alternatives) if alternatives else {"code": "NO_EXACT_WORDNET_WITNESS"}
        )
        if witness["kind"] == "ASSERTED_NATIVE_READING_TYPE":
            supported = witness["supported_entry_ids"][0]
            if contextual["code"] == "EXACT_WORDNET_SENSE" and contextual["entry_id"] != supported:
                contextual = {"code": "CONTEXTUAL_WITNESSES_DISAGREE", "construction_witness": contextual}
            elif contextual["code"] != "CONTEXTUAL_WITNESSES_DISAGREE":
                # The complete positively asserted native type itself is an
                # independent witness, even when the head is parsed correctly
                # as nominal and no accidental verbal derivation is available.
                contextual = {
                    **contextual,
                    "code": "EXACT_WORDNET_SENSE",
                    "entry_id": supported,
                    "witness_kind": "ASSERTED_NATIVE_READING_TYPE",
                    "native_type_ids": witness["native_type_ids"],
                }
        if contextual["code"] == "EXACT_WORDNET_SENSE":
            return {
                "code": "CONTEXTUAL_DEFINITION_SELECTED",
                "entry_id": contextual["entry_id"],
                "challenged_grammatical_entry_id": entry_id,
                "catalog_provenance": list(native.provenance),
                "construction": witness,
                "contextual_grounding": contextual,
                "considered_entry_ids": alternatives,
            }
        return {
            "code": "GRAMMATICAL_CONTEXT_CONFLICT",
            "entry_id": entry_id,
            "catalog_provenance": list(native.provenance),
            "grammar_roles": list(native.grammar_roles),
            "grammatical_features": native.grammatical_features,
            "construction": witness,
            "contextual_grounding": contextual,
            "considered_entry_ids": alternatives,
        }

    def select(self, position, lemma, candidates, *, pos="NOUN"):
        candidate_ids = set(candidates)
        senses = {key: value for key, value in self._senses(lemma, pos).items() if key in candidate_ids}
        if not senses:
            return self._primary_frame_support(position, lemma, candidate_ids, pos)
        if pos in {"VERB", "ADJ", "ADV"}:
            native = self._native_example_support(position, lemma, senses, pos)
            if native["code"] != "NO_DEFINITION_CONSTRUCTION_WITNESS":
                return native
            primary = self._primary_frame_support(position, lemma, candidate_ids, pos)
            return native if primary["code"] == "NO_PRIMARY_FRAME_WITNESS" else primary
        start, end = self._bounds(position, self.boundaries)
        nominal = self._nominal_support(lemma, senses, start, end)
        definition_only = self.doc[position].pos_ == "PROPN"
        if nominal["code"] == "CONTEXTUAL_WITNESSES_DISAGREE" or (
            nominal["code"] == "EXACT_WORDNET_SENSE" and not definition_only
        ):
            return nominal
        contextual = self._construction_support(position, lemma, senses, definition_only=definition_only)
        if contextual["code"] != "EXACT_WORDNET_SENSE":
            code = contextual["code"] if definition_only else nominal["code"]
            return {**nominal, "code": code, "construction": contextual}
        supported = set(nominal.get("native_anchor_support", {}))
        thread = nominal.get("type_thread_candidate")
        if (supported and contextual["entry_id"] not in supported) or (thread and thread != contextual["entry_id"]):
            return {**nominal, "code": "CONTEXTUAL_WITNESSES_DISAGREE", "construction_witness": contextual}
        return {**nominal, **contextual, "code": "EXACT_WORDNET_SENSE"}

    def _primary_role(self, token):
        """A source-attested proform role, independent of learned bank values.

        Arbitrary nouns are deliberately NOT slot wildcards. An unknown noun,
        a nominal chemical symbol, or a conflicting grammatical reading cannot
        become a person just to make a primary frame match.
        """
        if token.pos_ != "PRON":
            return None
        entry_id = f"gse_closed_class:pronoun:{token.lemma_}"
        native = _catalog_reading(token.lemma_, entry_id)
        if native is None or native.grammar_roles != ("PRON",):
            return None
        rows = self.conn.execute(
            """SELECT o.record_id,o.payload FROM source_observations o
               JOIN definition_states d ON d.entry_id=o.entry_id
               WHERE o.entry_id=? AND o.source='gse_closed_class'
                 AND o.family='gse_curated_grammar' AND o.scope='lexical'
                 AND d.code IN ('PARTIAL','RESOLVED')""",
            (entry_id,),
        ).fetchall()
        for record_id, raw in rows:
            features = json.loads(raw).get("features", {})
            if (
                features.get("entry_id") == entry_id
                and features.get("definition") == native.definition
                and features.get("grammar_roles") == list(native.grammar_roles)
                and features.get("grammatical_features") == native.grammatical_features
                and features.get("primitives") == native.primitives
                and self.grammatical_eligibility(token.i, token.lemma_, entry_id)["code"] == "GRAMMATICAL_ROLE_ELIGIBLE"
            ):
                return {"entry_id": entry_id, "record_id": record_id, "roles": dict(native.primitives)}
        return None

    def _primary_frame_support(self, position, lemma, candidate_ids, pos):
        """Unify a complete source frame as compatibility, not sense identity.

        Primary chart units are independently named meanings. Their allowable
        frames attest a possible use, not exclusion of ordinary meanings with
        the same grammar (visual seeing versus consulting someone, for example).
        Even an explicit catalogue alignment therefore cannot turn this match
        into a selected row. Retain the exact source/role proof for concurrent
        grounding, but assert no identity or bank from this witness alone.
        """
        if pos not in {"VERB", "ADJ", "ADV"}:
            return {"code": "NO_PRIMARY_FRAME_WITNESS"}
        frames, source = _primary_frames()
        units = {}
        for unit_id, linked_ids, _, _ in frames:
            for entry_id in set(linked_ids) & candidate_ids:
                # The unit identity itself must be usable in this snapshot.
                row = self.conn.execute("SELECT code FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
                if row and row[0] in {"PARTIAL", "RESOLVED"}:
                    if entry_id.startswith("wordnet:") and entry_id not in self._senses(lemma, pos):
                        continue
                    units[entry_id] = unit_id
        if not units:
            return {"code": "NO_PRIMARY_FRAME_WITNESS"}
        start, end = self._bounds(position, self.sentence_boundaries)
        actual = tuple(self.doc[start + 1 : end])
        scope = []
        # Existing ordinal/sign grammar is orthogonal to lexical identity.
        # Only a contiguous pre-adjectival/adverbial chain can scope the head;
        # never erase arguments, clause operators or a verb's valency. The
        # actual tokens remain in the trace for bind_degree_modifiers/_sign_owners.
        if pos in {"ADJ", "ADV"}:
            head_index = next((i for i, token in enumerate(actual) if token.i == position), -1)
            first = head_index
            while first > 0:
                token = actual[first - 1]
                hierarchy = get_hierarchy_encoding(token.lemma_.upper())
                if token.lemma_ in _NEGATION_LEMMAS and token.pos_ in {"PART", "ADV"}:
                    kind = "EXISTING_SIGN_GRAMMAR"
                elif token.pos_ == "ADV" and hierarchy and hierarchy[0] == "INTENSITY":
                    kind = "EXISTING_INTENSITY_GRAMMAR"
                else:
                    break
                scope.insert(0, {"position": token.i, "lemma": token.lemma_, "grammar": kind})
                first -= 1
            actual = actual[:first] + actual[head_index:]
        witnesses = {}
        for frame_unit, _, original, pattern in frames:
            heads = [i for i, t in enumerate(pattern) if t.lemma_ == lemma and t.pos_ in _CONTENT_POS]
            if len(heads) != 1 or len(pattern) != len(actual) or actual[heads[0]].i != position:
                continue
            slots = []
            for i, (expected, observed) in enumerate(zip(pattern, actual, strict=True)):
                if i == heads[0]:
                    continue
                expected_native = _catalog_reading(expected.lemma_, f"gse_closed_class:pronoun:{expected.lemma_}")
                if expected.pos_ == "PRON" and expected_native is not None:
                    role = self._primary_role(observed)
                    required = expected_native.primitives
                    if role is None or not required or any(role["roles"].get(k) != v for k, v in required.items()):
                        break
                    slots.append({"position": observed.i, "source_exponent": expected.text, **role})
                elif (expected.lemma_, expected.pos_) != (observed.lemma_, observed.pos_):
                    break
            else:
                # A canonical chart identity must still carry its exact source
                # observation. A stale/changed chart row is not runtime authority.
                for entry_id, unit_id in units.items():
                    if entry_id.startswith("nsm_chart:"):
                        observations = self.conn.execute(
                            """SELECT record_id,payload FROM source_observations WHERE entry_id=?
                               AND source='nsm_chart' AND family='nsm_primary_chart' AND scope='source_structure'""",
                            (entry_id,),
                        ).fetchall()
                        records = [
                            record_id
                            for record_id, raw in observations
                            if json.loads(raw).get("features", {}) == _primary_records().get(entry_id)
                        ]
                        if not records:
                            continue
                    else:
                        records = [entry_id]
                    witnesses.setdefault(entry_id, []).append(
                        {
                            "primary_unit_id": unit_id,
                            "source_frame_unit_id": frame_unit,
                            "source_frame": original,
                            "expanded_frame": " ".join(t.text for t in pattern),
                            "source_record_ids": records,
                            "role_witnesses": slots,
                            "orthogonal_scope_grammar": scope,
                        }
                    )
        if len(witnesses) != 1:
            return {
                "code": "COMPETING_PRIMARY_FRAMES" if witnesses else "NO_PRIMARY_FRAME_WITNESS",
                "primary_candidates": sorted(witnesses),
            }
        entry_id = next(iter(witnesses))
        return {
            "code": "PRIMARY_FRAME_COMPATIBLE_NOT_IDENTIFYING",
            "compatible_entry_id": entry_id,
            "witness_kind": "NSM_PRIMARY_TYPED_FRAME",
            "identity_scope": "UNRESOLVED",
            "missing_witness": "INDEPENDENT_MEANING_DISCRIMINATION",
            "unresolved_ordinary_entry_ids": sorted(candidate_ids - {entry_id}),
            "source_reference": source,
            "frames": witnesses[entry_id],
        }

    def _native_example_support(self, position, lemma, senses, pos):
        """Make attested non-nominal identities reachable without a POS override.

        Compare the complete sentence construction rather than isolated cue
        words. A source example's initial personal subject may vary only with
        independently attested person-reference grammar and an otherwise
        identical complete construction. This is source-example-derived
        evidence, NOT independent held-out accuracy or arbitrary frame matching.
        Nominal type threads remain separate: noun/verb types are incomparable.
        """
        start, end = self._bounds(position, self.sentence_boundaries)
        actual_tokens = tuple(self.doc[start + 1 : end])
        actual = tuple((t.lemma_.casefold(), t.pos_) for t in actual_tokens)
        witnesses = {}
        for entry_id, sense in senses.items():
            examples, subject_variants = [], []
            for example in sense.examples:
                expected = _native_example_signature(example, lemma, pos)
                if expected == actual:
                    examples.append(example)
                elif (
                    expected
                    and len(expected) == len(actual)
                    and expected[1:] == actual[1:]
                    and expected[0][1] == actual[0][1] == "PRON"
                    and actual_tokens[0].i < position
                ):
                    # The substitution changes WHO bears the attested meaning,
                    # not the word's valency, complements, scope or qualifiers.
                    source_token = NativeNLP()(example)[0]
                    source_role = self._primary_role(source_token)
                    actual_role = self._primary_role(actual_tokens[0])
                    if (
                        source_role
                        and actual_role
                        and source_role["roles"].get("SOMEONE") == 1
                        and actual_role["roles"].get("SOMEONE") == 1
                    ):
                        examples.append(example)
                        subject_variants.append({"source": source_role, "occurrence": actual_role})
            if examples:
                witnesses[entry_id] = {
                    "witness_kind": (
                        "WORDNET_NATIVE_EXAMPLE_PERSON_SUBSTITUTION"
                        if subject_variants
                        else "WORDNET_NATIVE_EXAMPLE_CONSTRUCTION"
                    ),
                    "native_synset": sense.synset,
                    "native_examples": examples,
                    "construction_signature": [list(pair) for pair in actual],
                    "eligible_pos": pos,
                    "source_record_id": entry_id,
                    "subject_role_witnesses": subject_variants,
                }
        return _unique_native_witness(witnesses)

    def _bounds(self, position, boundaries):
        return (
            max((i for i in boundaries if i < position), default=-1),
            min((i for i in boundaries if i > position), default=len(self.doc)),
        )

    def _nominal_support(self, lemma, senses, start, end):
        context = {
            token.lemma_.casefold()
            for token in self.doc[start + 1 : end]
            if token.pos_ == "NOUN" and token.lemma_.casefold() != lemma
        }
        if not context:
            return {"code": "NO_NOMINAL_CONTEXT"}
        context_nodes = set()
        witnessed_words = set()
        context_senses = {}
        context_entry_ids = {}
        for word in sorted(context):
            alternatives = self._senses(word)
            if len(alternatives) == 1:
                native_sense = next(iter(alternatives.values()))
                context_senses[word] = native_sense
                context_entry_ids[word] = next(iter(alternatives))
                context_nodes.update(native_sense.nodes)
                witnessed_words.add(word)
        # An independently unambiguous context noun can name the very same
        # native synset (a symbol and its expanded name, for example). This is
        # native lexical identity, not mere ancestry or a first-sense guess.
        # Keep the ordinary production type-thread agreement check below.
        synonym_support = {
            key: sorted(word for word, native in context_senses.items() if native.synset == sense.synset)
            for key, sense in senses.items()
            if any(native.synset == sense.synset for native in context_senses.values())
        }
        support = {
            key: sorted((sense.anchors & witnessed_words) | set(synonym_support.get(key, ())))
            for key, sense in senses.items()
            if sense.anchors & witnessed_words or key in synonym_support
        }
        common = set.intersection(*(set(sense.nodes) for sense in senses.values())) if len(senses) > 1 else set()
        scores = sorted(
            (
                (_jaccard(set(sense.nodes) - common, context_nodes), key)
                for key, sense in senses.items()
                if (sense.nodes - common) & context_nodes
            ),
            reverse=True,
        )
        thread = (
            scores[0][1]
            if scores and scores[0][0] > (scores[1][0] if len(scores) > 1 else 0) + _COHERENCE_MARGIN
            else None
        )
        if thread:
            # Eligibility and lexical witnesses are established above. The
            # production coherence selector, not a parallel similarity resolver,
            # then consumes the native type threads. Common nodes carry no WSD
            # signal and are removed on both sides, as in the diagnostics.
            ordered = sorted(senses)
            threads = {lemma: [tuple(sorted(senses[key].nodes - common)) for key in ordered]}
            threads.update(
                (word, [tuple(sorted(next(iter(self._senses(word).values())).nodes))])
                for word in sorted(witnessed_words)
            )
            entities = [Entity(Atom(word, pos="NOUN")) for word in threads]
            chosen = _select_by_coherence(entities, _NativeThreads(threads), native_only=True)
            selected_thread = chosen.get(_signature(entities[0]), ())
            if selected_thread != threads[lemma][ordered.index(thread)]:
                thread = None
        anchor = next(iter(support)) if len(support) == 1 else None
        evidence = {"native_anchor_support": support, "type_coherence": dict((key, score) for score, key in scores)}
        if synonym_support:
            evidence["native_synonym_support"] = {
                key: {
                    "synset": senses[key].synset,
                    "context_entry_ids": {word: context_entry_ids[word] for word in words},
                }
                for key, words in synonym_support.items()
            }
        if thread:
            evidence["type_thread_candidate"] = thread
        if not support:
            code = "TYPE_COHERENCE_WITHOUT_LEXICAL_WITNESS" if thread else "INSUFFICIENT_CONTEXTUAL_SUPPORT"
            return {"code": code, **evidence}
        if thread and thread not in support:
            return {"code": "CONTEXTUAL_WITNESSES_DISAGREE", **evidence}
        selected = anchor or thread
        if selected is None:
            return {"code": "INSUFFICIENT_CONTEXTUAL_SUPPORT", **evidence}
        return {"code": "EXACT_WORDNET_SENSE", "entry_id": selected, **evidence}

    def _construction_support(self, position, lemma, senses, *, definition_only=False):
        """Bind multiple gloss cues or an exact derivation in a linked clause."""
        tokens, linked = self._construction_span(position)
        cues = {
            token.lemma_: token.pos_
            for token in tokens
            if token.i != position
            and token.lemma_ != lemma
            and token.pos_ in _CONTENT_POS
            and token.lemma_ not in _GENERIC_TERMS
            and not token.is_stop
            and not is_numeral(token.lemma_)
        }
        type_witness = self._construction_type(position, tokens, linked)
        predication = self._definition_predication(position)
        sentence_start, sentence_end = self._bounds(position, self.sentence_boundaries)
        # A construction span can stop at a coordinator. The material before
        # an alternative is not, by itself, asserted context: deriving a noun
        # identity from just that first disjunct would silently discard the
        # other reading. Complete definition matching already checks this
        # scope; weaker gloss/derivation evidence must not bypass that check.
        alternative_context = any(t.lemma_ == "or" for t in self.doc[sentence_start + 1 : sentence_end])
        derivations = {word: _verb_derivations(word) for word, pos in cues.items() if pos == "VERB"}
        linked_verbs = {t.lemma_ for t in tokens if linked is not None and t.i > linked and t.pos_ == "VERB"}
        witnesses, definition_witnesses = {}, {}
        for entry_id, sense in senses.items():
            gloss = dict(_gloss_content(sense.gloss))
            matched = frozenset(gloss.keys() & cues.keys())
            exact, related = self._derivation_support(sense, gloss, matched, derivations, linked_verbs, type_witness)
            verb_match = any(gloss[word] == cues[word] == "VERB" for word in matched)
            typed = self._matches_construction_type(sense, type_witness, matched, gloss)
            repeated = self._matches_definition_predication(sense, predication)
            if repeated or (
                not definition_only
                and not alternative_context
                and (exact or (verb_match and len(matched) >= 2) or related or typed)
            ):
                witnesses[entry_id] = {
                    "gloss_terms": sorted(matched),
                    "exact_derivation": exact,
                    "related_derivation": related,
                    "construction_type": predication if repeated else type_witness if typed or related else None,
                }
                if repeated:
                    definition_witnesses[entry_id] = witnesses[entry_id]
        # Complete definition identity precedes weaker derivational similarity;
        # two exact definitions still abstain rather than choosing by order.
        result = _unique_native_witness(definition_witnesses or witnesses)
        if alternative_context:
            result["unasserted_context"] = "DISJUNCTIVE_CONSTRUCTION_ALTERNATIVES"
        return result

    def _definition_predication(self, position):
        """Read an explicit nominal equivalence with the target as its subject."""
        start, end = self._bounds(position, self.sentence_boundaries)
        preceding = tuple(self.doc[start + 1 : position])
        following = tuple(self.doc[position + 1 : end])
        if (
            (preceding and (len(preceding) != 1 or preceding[0].lemma_ != "the"))
            or len(following) < 4
            or following[0].lemma_ != "be"
            or following[0].pos_ != "AUX"
            or following[1].lemma_ not in {"a", "an", "the"}
            or (end < len(self.doc) and self.doc[end].text == "?")
            or any(t.lemma_ == "or" for t in following)
        ):
            return None
        complement = following[2:]
        # A state's defining condition can contain its own prepositions,
        # predicates and negation. Match that complete native definition;
        # negation of the outer copula never reaches this article-led branch.
        if (
            len(complement) >= 3
            and complement[0].lemma_ == "state"
            and complement[0].pos_ == "NOUN"
            and (
                complement[1].lemma_ == "of"
                or (len(complement) >= 4 and [t.lemma_ for t in complement[1:3]] == ["in", "which"])
            )
            and not any(t.pos_ == "PUNCT" for t in complement)
        ):
            return {
                "kind": "EXPLICIT_DEFINITION_PREDICATION",
                "terms": [t.text.casefold() for t in complement],
                "state_condition": complement[2].text.casefold()
                if len(complement) == 3 and complement[1].lemma_ == "of" and complement[2].pos_ == "NOUN"
                else None,
            }
        if any(t.lemma_ in {"not", "never"} for t in following):
            return None
        # Retain the entire asserted nominal clause, including a relative or
        # prepositional modifier. It may identify a source reading only by
        # exact comparison with that reading's complete native definition (or
        # its complete principal clause before an explanatory semicolon).
        complete_terms = [t.text.casefold() for t in complement]
        # A relative clause can elaborate an already asserted complement.
        relative = next((i for i, t in enumerate(following[2:], 2) if t.lemma_ in {"that", "which"}), len(following))
        nominal = following[2:relative]
        if (
            len(nominal) < 2
            or nominal[-1].pos_ != "NOUN"
            or any(t.pos_ not in {"ADJ", "NOUN"} for t in nominal)
            or (relative < len(following) and not any(t.pos_ == "VERB" for t in following[relative + 1 :]))
        ):
            return {
                "kind": "EXPLICIT_DEFINITION_PREDICATION",
                "terms": complete_terms,
                "complete_terms": complete_terms,
                "exact_clause_only": True,
            }
        return {
            "kind": "EXPLICIT_DEFINITION_PREDICATION",
            "terms": [t.text.casefold() for t in nominal],
            "complete_terms": complete_terms,
        }

    @staticmethod
    def _matches_definition_predication(sense, predication):
        if predication is None:
            return False
        principal = sense.gloss.casefold().split(";", 1)[0].removesuffix(".")
        principal_terms = re.findall(r"\w+|[^\w\s]", principal)
        if principal_terms and principal_terms[0] in {"a", "an", "the"}:
            principal_terms = principal_terms[1:]
        if predication.get("complete_terms") == principal_terms:
            return True
        if predication.get("exact_clause_only"):
            return False
        terms = predication["terms"]
        gloss = sense.gloss.casefold().removesuffix(".").split()
        if gloss and gloss[0] in {"a", "an", "the"}:
            gloss = gloss[1:]
        if terms == gloss or "_".join(terms) in sense.names:
            return True
        # An explicitly asserted state genus can identify a unique native
        # reading even when its definition adds a qualifier after the complete
        # condition noun (e.g. inactivity following an interruption).
        return (
            predication.get("state_condition") is not None
            and "state.n.02" in sense.nodes
            and len(gloss) > len(terms)
            and gloss[: len(terms)] == terms
        )

    def _construction_span(self, position):
        start, end = self._bounds(position, self.boundaries)
        _, sentence_end = self._bounds(position, self.sentence_boundaries)
        cuts = sorted(self.boundaries | {sentence_end})
        # A temporal preposition with no predicate in its own segment is
        # nominal context, e.g. “before six, when …” or “after midnight”.
        while end < sentence_end and self.doc[end].lemma_ in {"after", "before"}:
            following = next(i for i in cuts if i > end)
            if any(token.pos_ == "VERB" for token in self.doc[end + 1 : following]):
                break
            end = following
        linked = next(
            (
                t.i
                for t in self.doc[position + 1 : min(end + 1, sentence_end)]
                if t.lemma_ in _EXPLANATORY_LINKERS and t.pos_ == "SCONJ"
            ),
            None,
        )
        if linked is not None:
            linked_end = next(i for i in cuts if i > linked)
            if any(token.pos_ == "VERB" for token in self.doc[linked + 1 : linked_end]):
                end = linked_end
            else:
                linked = None
        elif end < sentence_end and self.doc[end].lemma_ == "and":
            following = next(i for i in cuts if i > end)
            if self.doc[end + 1 : following] and self.doc[end + 1].pos_ == "VERB":
                end = following
            elif self.doc[end + 1 : following] and not self.doc[end + 1].is_stop:
                # A zero-inflection verb with an immediate object determiner
                # is a shared-subject conjunct even when POS remains nominal.
                if (
                    end + 2 < following
                    and self.doc[end + 2].pos_ == "DET"
                    and _verb_derivations(self.doc[end + 1].lemma_)
                ):
                    end = following
        return tuple(self.doc[start + 1 : end]), linked

    def _construction_type(self, position, tokens, linked):
        following = [t for t in tokens if t.i > position]
        if len(following) >= 3 and [t.lemma_ for t in following[:2]] in (["be", "a"], ["be", "an"]):
            complement = following[2]
            if complement.pos_ == "NOUN" and not any(t.lemma_ == "not" for t in tokens):
                threads = tuple(s.nodes for s in self._senses(complement.lemma_).values())
                if any(_PARTICIPANT_ROOT in thread for thread in threads) and all(
                    thread & _PERSON_OR_COLLECTION for thread in threads
                ):
                    return {"kind": "PERSON_TYPE_ASSERTION", "token": complement.i}
        if (
            len(following) >= 4
            and following[0].lemma_ == "from"
            and following[2].lemma_ == "to"
            and following[1].lemma_ != following[3].lemma_
            and all(
                t.pos_ == "NOUN" and any(_MATTER_STATE_ROOT in s.nodes for s in self._senses(t.lemma_).values())
                for t in (following[1], following[3])
            )
        ):
            return {"kind": "STATE_TRANSITION", "tokens": [t.i for t in following[:4]]}
        if linked is not None and len(following) >= 3 and following[0].lemma_ == "take":
            if any(_TIME_MEASURE_ROOT in s.nodes for s in self._senses(following[2].lemma_).values()):
                return {
                    "kind": "ELABORATED_DURATION",
                    "token": linked,
                    "elaboration_verbs": sorted({t.lemma_ for t in following if t.i > linked and t.pos_ == "VERB"}),
                }
        if (
            linked is not None
            and self.doc[linked].lemma_ == "when"
            and len(following) >= 5
            and [t.lemma_ for t in following[:2]] == ["of", "the"]
            and following[2].pos_ == "NOUN"
            and following[3].lemma_ == "come"
            and following[4].i == linked
        ):
            return {"kind": "EVENT_TIME_ELABORATION", "topic": following[2].lemma_, "token": linked}
        if len(following) >= 2 and following[0].lemma_ == "start":
            return {"kind": "EVENT_ONSET", "token": following[0].i}
        for first, second in zip(following, following[1:]):
            numeral = get_numeral_encoding(first.lemma_) or {}
            if numeral.get("quantity_type") == "cardinal":
                forms = _noun_forms(second.text)
                if forms and first.i > position + 1 and self.doc[first.i - 1].lemma_ in {"into", "to"}:
                    return {"kind": "COUNTED_RESULT", "token": second.i, "lemmas": sorted(forms | {second.lemma_})}
        return None

    def _matches_construction_type(self, sense, witness, matched, gloss):
        if witness is None:
            return False
        kind = witness["kind"]
        if kind == "PERSON_TYPE_ASSERTION":
            return _PARTICIPANT_ROOT in sense.nodes
        if kind == "STATE_TRANSITION":
            return _EVENT_ROOT in sense.nodes and "state" in gloss
        if kind == "EVENT_TIME_ELABORATION":
            return _EVENT_ROOT in sense.nodes and witness["topic"] in matched
        if kind == "EVENT_ONSET":
            return _EVENT_ROOT in sense.nodes and any(gloss[term] == "VERB" for term in matched)
        return False

    def _derivation_support(self, sense, gloss, matched, derivations, linked_verbs, type_witness):
        if not derivations or not _live_native_sense(sense):
            return [], []
        exact, related = [], []
        kind = type_witness["kind"] if type_witness else None
        for word, verbs in derivations.items():
            targets = frozenset().union(*verbs.values())
            if sense.synset in targets and (
                (len(verbs) == 1 and word in linked_verbs) or (word in matched and gloss[word] == "VERB")
            ):
                exact.append(word)
            if (
                kind == "ELABORATED_DURATION"
                and word in type_witness["elaboration_verbs"]
                and any(sense.synset in _noun_thread(target) for target in targets)
            ):
                related.append(word)
            if (
                kind == "COUNTED_RESULT"
                and (sense.nodes - {sense.synset}) & targets
                and gloss.keys() & set(type_witness["lemmas"])
            ):
                related.append(word)
        return sorted(exact), sorted(related)
