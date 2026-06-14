import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Protocol, runtime_checkable


class POS(Enum):
    """Part of speech tags (simplified from SpaCy's tag set)."""
    NOUN = "NOUN"
    VERB = "VERB"
    ADJ = "ADJ"
    ADV = "ADV"
    PRON = "PRON"
    DET = "DET"
    ADP = "ADP"      # Preposition
    CONJ = "CONJ"
    PUNCT = "PUNCT"
    NUM = "NUM"
    AUX = "AUX"
    PART = "PART"    # Particle (e.g., "to", "'s")
    OTHER = "OTHER"

@dataclass
class Token:
    """Parsed token with linguistic annotations."""
    surface: str          # Original text
    lemma: str            # Base form
    pos: POS              # Part of speech
    dep: str              # Dependency relation
    head_idx: int         # Index of syntactic head
    idx: int              # Token index in sentence
    is_root: bool         # Is this the root of the parse?

@dataclass
class SemanticRole:
    """Semantic role assignment."""
    role: str             # agent, patient, theme, etc.
    token_idx: int        # Which token fills this role
    confidence: float     # How confident are we?

@dataclass
class ParsedSentence:
    """Complete parse of a sentence."""
    text: str
    tokens: List[Token]
    roles: List[SemanticRole]
    root_idx: int

    def get_dependents(self, idx: int) -> List[Token]:
        """Get all tokens that depend on the given token."""
        return [t for t in self.tokens if t.head_idx == idx and t.idx != idx]

    def bottom_up_order(self) -> List[int]:
        """Return token indices in bottom-up order for composition."""
        # Topological sort based on dependency structure
        visited = set()
        order = []

        def visit(idx: int):
            if idx in visited:
                return

            # Visit children first (post-order traversal)
            # Find all tokens that have this idx as head
            children = [t for t in self.tokens if t.head_idx == idx and t.idx != idx]

            for t in children:
                visit(t.idx)

            visited.add(idx)
            order.append(idx)

        # Start from root?
        # Actually standard topological sort can start anywhere, but for dependency tree
        # we want to ensure we cover everything.
        # Since it's a tree (single root), visiting root will visit everything.
        if self.tokens:
            visit(self.root_idx)

            # Just in case there are disconnected components (shouldn't be in valid parse)
            for t in self.tokens:
                if t.idx not in visited:
                    visit(t.idx)

        return order


# Mapping from SpaCy dependency relations to semantic roles
DEP_TO_ROLE = {
    # Core arguments
    "nsubj": "agent",           # Nominal subject
    "nsubjpass": "patient",     # Passive nominal subject
    "dobj": "patient",          # Direct object
    "obj": "patient",           # Object (newer SpaCy)
    "iobj": "recipient",        # Indirect object
    "dative": "recipient",      # Dative (indirect object)

    # Oblique arguments
    "obl": "oblique",           # Oblique nominal
    "nmod": "modifier",         # Nominal modifier

    # Modifiers
    "amod": "attribute",        # Adjectival modifier
    "advmod": "manner",         # Adverbial modifier
    "nummod": "quantity",       # Numeric modifier

    # Function words
    "det": "determiner",        # Determiner
    "case": "case",             # Case marking
    "aux": "auxiliary",         # Auxiliary verb
    "cop": "copula",            # Copula

    # Coordination and subordination
    "conj": "conjunction",      # Conjunct
    "cc": "coordinator",        # Coordinating conjunction
    "mark": "marker",           # Marker (subordinating conjunction)

    # Other
    "compound": "compound",     # Compound
    "poss": "possessor",        # Possessive
    "prep": "preposition",      # Prepositional modifier
    "pobj": "prep_object",      # Object of preposition
}


class Parser:
    """SpaCy-based parser with semantic role extraction."""

    def __init__(self, model: str = "en_core_web_sm"):
        # Lazy import — keeps gse.parser importable without spacy in env.
        import spacy
        if not spacy.util.is_package(model):
            # Try to download if missing?
            # It's better to warn or error.
            # But the user might be able to run the command.
            # I will try to download it seamlessly if possible, or raise clear error.
            print(f"Warning: {model} not found. Attempting to download...")
            try:
                from spacy.cli import download
                download(model)
            except Exception:
                pass

        try:
            self.nlp = spacy.load(model)
        except OSError as exc:
            raise OSError(
                f"Could not load SpaCy model '{model}'. "
                f"Please install it with: python -m spacy download {model}"
            ) from exc

    def parse(self, text: str) -> List[ParsedSentence]:
        """Parse text into sentences with full annotations."""
        doc = self.nlp(text)
        sentences = []

        for sent in doc.sents:
            tokens = []
            root_idx = 0

            # Map sentence-relative indices
            sent_start = sent.start

            for i, token in enumerate(sent):
                # Map POS
                try:
                    pos = POS[token.pos_]
                except KeyError:
                    pos = POS.OTHER

                # Calculate head index relative to sentence
                # token.head gives the head token. We need its index relative to sentence start.
                # Careful: token.head.i is absolute document index.
                head_abs_idx = token.head.i
                head_rel_idx = head_abs_idx - sent_start

                # Ensure head is within sentence (it should be for projective dependency trees)
                # But spacy sents are spans, token.head might be outside if we are not careful,
                # but doc.sents usually respects sentence boundaries for heads unless it's weird text.
                if head_rel_idx < 0 or head_rel_idx >= len(sent):
                    # Fallback or weird case: set head to self (root behavior)
                    head_rel_idx = i

                is_root = (token.head.i == token.i)
                if is_root:
                    root_idx = i

                tokens.append(Token(
                    surface=token.text,
                    lemma=token.lemma_.lower(),
                    pos=pos,
                    dep=token.dep_,
                    head_idx=head_rel_idx,
                    idx=i,
                    is_root=is_root
                ))

            # If no root found (rare), default to 0
            if not any(t.is_root for t in tokens) and tokens:
                # Find the token whose head is itself, that's the root logic above.
                # Doubly ensure we have a root_idx
                pass

            # Extract semantic roles
            roles = self._extract_roles(tokens, root_idx)

            sentences.append(ParsedSentence(
                text=sent.text,
                tokens=tokens,
                roles=roles,
                root_idx=root_idx
            ))

        return sentences

    def _extract_roles(self, tokens: List[Token], root_idx: int) -> List[SemanticRole]:
        """Extract semantic roles from dependency structure."""
        roles = []

        for token in tokens:
            dep = token.dep.lower()

            if dep in DEP_TO_ROLE:
                role = DEP_TO_ROLE[dep]

                # Special handling for preposition objects
                if dep == "pobj":
                    # Find the preposition. The pobj's head should be the preposition?
                    # In SpaCy: prep --pobj--> noun
                    # So noun.head is prep.
                    prep_token = tokens[token.head_idx]

                    if prep_token.lemma in ["for", "to"]:
                        role = "beneficiary" # or recipient or goal
                    elif prep_token.lemma in ["with"]:
                        role = "instrument" # or comitative
                    elif prep_token.lemma in ["in", "at", "on"]:
                        role = "location"
                    elif prep_token.lemma in ["from"]:
                        role = "source"
                    elif prep_token.lemma in ["by"]:
                        role = "agent" # in passive

                # Special handling for passive subjects
                if dep == "nsubjpass":
                    role = "patient"

                roles.append(SemanticRole(
                    role=role,
                    token_idx=token.idx,
                    confidence=0.9
                ))

        return roles

    def parse_single(self, text: str) -> ParsedSentence:
        """Parse a single sentence."""
        sentences = self.parse(text)
        if not sentences:
            raise ValueError(f"Could not parse: {text}")
        return sentences[0]


# =============================================================================
# POS TAGGER ABSTRACTION
# =============================================================================
#
# The Parser class above is the spaCy implementation. The Protocol below
# defines what any parser must do; HeuristicParser is a dependency-free
# fallback for environments without spaCy. make_parser() tries spaCy first
# and falls back transparently.

@runtime_checkable
class POSTagger(Protocol):
    """Anything that can turn text into a list of ParsedSentence objects."""

    def parse(self, text: str) -> List[ParsedSentence]: ...

    def parse_single(self, text: str) -> ParsedSentence: ...


# Word-class heuristic dictionaries for the fallback tagger.
# These cover the highest-frequency function words and a handful of
# productive content-word patterns. Coverage is intentionally narrow —
# the fallback is a "last resort" tagger, not a replacement for spaCy.

_HEURISTIC_PRONOUNS = {
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their",
    "this", "that", "these", "those", "who", "what", "which",
}
_HEURISTIC_DETS = {"the", "a", "an", "some", "any", "every", "each", "no"}
_HEURISTIC_ADPS = {
    "of", "in", "on", "at", "to", "for", "from", "by", "with", "without",
    "into", "onto", "over", "under", "above", "below", "between",
}
_HEURISTIC_CONJS = {"and", "or", "but", "nor", "yet", "so", "because", "although", "if"}
_HEURISTIC_AUX = {"is", "am", "are", "was", "were", "be", "been", "being",
                  "do", "does", "did", "has", "have", "had",
                  "can", "could", "will", "would", "should", "may", "might", "must"}
_HEURISTIC_PARTS = {"to", "'s", "'re", "'ve", "'ll", "'d", "not", "n't"}
_HEURISTIC_PUNCT = set(".,;:!?-—()[]\"'")


def _heuristic_pos(word: str, idx: int) -> POS:
    """Best-effort POS tag for an isolated lowercased token."""
    if not word:
        return POS.OTHER
    if word in _HEURISTIC_PUNCT or all(c in _HEURISTIC_PUNCT for c in word):
        return POS.PUNCT
    if word.replace(",", "").replace(".", "").isdigit():
        return POS.NUM
    if word in _HEURISTIC_DETS:
        return POS.DET
    if word in _HEURISTIC_PRONOUNS:
        return POS.PRON
    if word in _HEURISTIC_ADPS:
        return POS.ADP
    if word in _HEURISTIC_CONJS:
        return POS.CONJ
    if word in _HEURISTIC_AUX:
        return POS.AUX
    if word in _HEURISTIC_PARTS:
        return POS.PART
    if word.endswith("ly"):
        return POS.ADV
    if word.endswith(("ing", "ed")) or word.endswith("s") and idx > 0:
        # crude verb heuristic
        return POS.VERB
    if word.endswith(("ous", "ful", "less", "ive", "able", "ible", "al")):
        return POS.ADJ
    return POS.NOUN  # last-resort default


class HeuristicParser:
    """Dependency-free fallback parser.

    Produces POS tags via word-class dictionaries and suffix heuristics.
    Dependency edges and semantic roles are limited to a single guess:
    the first noun/pronoun in each sentence is tagged as the subject
    (agent), pointing at the first verb (head); other tokens point at
    that verb too. This is enough to keep downstream code that consumes
    ParsedSentence objects functional in environments without spaCy.
    """

    _TOKEN_RE = re.compile(r"\w+|[^\w\s]")
    _SENT_RE = re.compile(r"(?<=[.!?])\s+")

    def parse(self, text: str) -> List[ParsedSentence]:
        sentences: List[ParsedSentence] = []
        for sent_text in self._SENT_RE.split(text.strip()):
            if not sent_text:
                continue
            sentences.append(self._parse_sentence(sent_text))
        return sentences

    def parse_single(self, text: str) -> ParsedSentence:
        sentences = self.parse(text)
        if not sentences:
            raise ValueError(f"Could not parse: {text}")
        return sentences[0]

    def _parse_sentence(self, text: str) -> ParsedSentence:
        raw_words = self._TOKEN_RE.findall(text)
        if not raw_words:
            return ParsedSentence(text=text, tokens=[], roles=[], root_idx=0)

        # First pass: POS tag each token, find the verb that becomes root.
        tokens: List[Token] = []
        root_idx = 0
        verb_found = False
        for i, word in enumerate(raw_words):
            lemma = word.lower()
            pos = _heuristic_pos(lemma, i)
            if not verb_found and pos == POS.VERB:
                root_idx = i
                verb_found = True
            tokens.append(Token(
                surface=word,
                lemma=lemma,
                pos=pos,
                dep="ROOT" if False else "dep",  # placeholder, rewritten below
                head_idx=i,
                idx=i,
                is_root=False,
            ))

        # Second pass: wire heads and deps relative to root.
        for i, tok in enumerate(tokens):
            if i == root_idx:
                tok.dep = "ROOT"
                tok.is_root = True
                tok.head_idx = i
            elif tok.pos in (POS.PRON, POS.NOUN) and i < root_idx:
                tok.dep = "nsubj"
                tok.head_idx = root_idx
            elif tok.pos in (POS.PRON, POS.NOUN) and i > root_idx:
                tok.dep = "dobj"
                tok.head_idx = root_idx
            elif tok.pos == POS.PUNCT:
                tok.dep = "punct"
                tok.head_idx = root_idx
            else:
                tok.dep = "dep"
                tok.head_idx = root_idx

        # Best-effort role extraction reuses the spaCy DEP_TO_ROLE mapping.
        roles = [
            SemanticRole(
                role=DEP_TO_ROLE[tok.dep],
                token_idx=tok.idx,
                confidence=0.4,  # lower than spaCy's 0.9
            )
            for tok in tokens
            if tok.dep in DEP_TO_ROLE
        ]
        return ParsedSentence(text=text, tokens=tokens, roles=roles, root_idx=root_idx)


def make_parser(prefer: str = "spacy", model: str = "en_core_web_sm") -> POSTagger:
    """Pick the best available parser implementation.

    With ``prefer="spacy"`` (default), attempts to build a spaCy ``Parser``
    and falls back to ``HeuristicParser`` only if spaCy or the model is
    unavailable. With ``prefer="heuristic"``, always returns the
    dependency-free fallback.
    """
    if prefer == "heuristic":
        return HeuristicParser()

    try:
        return Parser(model=model)
    except (ImportError, OSError):
        return HeuristicParser()
