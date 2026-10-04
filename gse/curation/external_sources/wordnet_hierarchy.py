"""
WordNet Semantic Hierarchy Parser

Leverages WordNet's taxonomy for:
- Hypernym chains (IS-A relationships) → category primitives
- Hyponym expansions → specificity
- Meronym/holonym (PART-OF) → PART primitive
- Domain categories → semantic field primitives
- Semantic similarity for inheritance

Key insight: Words higher in hierarchy are more abstract (THINK),
words lower are more concrete (SOMETHING).
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)


@dataclass
class WordNetHierarchyEntry:
    """Entry with hierarchy data from WordNet."""
    word: str
    pos: str
    synset_name: str
    hypernym_depth: int  # Distance to root
    hyponym_count: int  # Number of descendants
    has_meronyms: bool
    has_holonyms: bool
    lexname: Optional[str]  # Semantic domain


# Semantic domains (lexnames) to primitives mapping
LEXNAME_TO_PRIMITIVE = {
    # Noun domains
    'noun.body': {'BODY': 1, 'SOMETHING': 1},
    'noun.animal': {'ALIVE': 1, 'SOMETHING': 1},
    'noun.person': {'SOMEONE': 1, 'ALIVE': 1},
    'noun.cognition': {'THINK': 1},
    'noun.communication': {'SAY': 1, 'WORDS': 1},
    'noun.feeling': {'FEEL': 1},
    'noun.location': {'WHERE': 1},
    'noun.time': {'WHEN': 1},
    'noun.quantity': {'QUANTITY': 1},
    'noun.artifact': {'SOMETHING': 1},
    'noun.food': {'SOMETHING': 1, 'BODY': 1},
    'noun.substance': {'SOMETHING': 1},
    'noun.object': {'SOMETHING': 1},
    'noun.plant': {'ALIVE': 1, 'SOMETHING': 1},
    'noun.shape': {'SOMETHING': 1},
    'noun.state': {'BE': 1},
    'noun.event': {'HAPPEN': 1},
    'noun.act': {'DO': 1},
    'noun.process': {'HAPPEN': 1},
    'noun.phenomenon': {'HAPPEN': 1},
    'noun.attribute': {'BE': 1},
    'noun.relation': {'WITH': 1},
    'noun.group': {'PEOPLE': 1},
    'noun.motive': {'WANT': 1},
    'noun.possession': {'HAVE': 1},

    # Verb domains
    'verb.motion': {'MOVE': 1},
    'verb.perception': {'SEE': 1},
    'verb.cognition': {'THINK': 1},
    'verb.communication': {'SAY': 1},
    'verb.emotion': {'FEEL': 1},
    'verb.creation': {'DO': 1, 'START': 1},
    'verb.change': {'HAPPEN': 1},
    'verb.possession': {'HAVE': 1},
    'verb.body': {'BODY': 1, 'DO': 1},
    'verb.consumption': {'BODY': 1},
    'verb.contact': {'TOUCH': 1, 'DO': 1},
    'verb.stative': {'BE': 1},
    'verb.social': {'SOMEONE': 1, 'DO': 1},
    'verb.competition': {'DO': 1},
    'verb.weather': {'HAPPEN': 1},

    # Adjective domains
    'adj.all': {},  # Too general
    'adj.pert': {},  # Pertaining to
    'adj.ppl': {},  # Participial

    # Adverb domains
    'adv.all': {},
}


# Root synsets that indicate specific primitives
ROOT_CONCEPT_PRIMITIVES = {
    'entity.n.01': {'SOMETHING': 1},
    'physical_entity.n.01': {'SOMETHING': 1},
    'abstraction.n.06': {'THINK': 1},
    'psychological_feature.n.01': {'FEEL': 1, 'THINK': 1},
    'living_thing.n.01': {'ALIVE': 1},
    'organism.n.01': {'ALIVE': 1},
    'person.n.01': {'SOMEONE': 1},
    'causal_agent.n.01': {'DO': 1, 'CAUSE': 1},
    'act.n.02': {'DO': 1},
    'event.n.01': {'HAPPEN': 1},
    'state.n.02': {'BE': 1},
    'state.n.04': {'BE': 1},
    'location.n.01': {'WHERE': 1},
    'time.n.01': {'WHEN': 1},
    'group.n.01': {'PEOPLE': 1},
    'body_part.n.01': {'BODY': 1, 'PART': 1},
    'artifact.n.01': {'SOMETHING': 1},
    'natural_object.n.01': {'SOMETHING': 1},
    'substance.n.01': {'SOMETHING': 1},
    'communication.n.02': {'SAY': 1, 'WORDS': 1},
    'cognition.n.01': {'THINK': 1, 'KNOW': 1},
    'emotion.n.01': {'FEEL': 1},
    'feeling.n.01': {'FEEL': 1},
    'motivation.n.01': {'WANT': 1},
    'attribute.n.02': {'BE': 1},
    'relation.n.01': {'WITH': 1},
    'measure.n.02': {'QUANTITY': 1},
    'shape.n.02': {'SOMETHING': 1},
    'change.n.03': {'HAPPEN': 1},
}


class WordNetHierarchyParser(BaseExternalParser):
    """Parse WordNet hierarchy and map to GSE primitives."""

    def __init__(self, max_hypernym_depth: int = 10):
        super().__init__()
        self.config.name = "wordnet_hierarchy"
        self.max_depth = max_hypernym_depth
        self._synset_cache: Dict[str, Dict] = {}
        self._wn = None  # Lazy-loaded WordNet module

    def load(self) -> bool:
        """Load WordNet hierarchy data."""
        try:
            import nltk
            from nltk.corpus import wordnet as wn

            # Ensure downloaded
            try:
                wn.synsets('test')
            except LookupError:
                logger.info("Downloading WordNet...")
                nltk.download('wordnet', quiet=True)
                nltk.download('omw-1.4', quiet=True)

            self._wn = wn

            logger.info("Building WordNet hierarchy index...")
            count = 0

            for synset in wn.all_synsets():
                # Get hierarchy metrics
                hypernyms = synset.hypernyms()
                hyponyms = synset.hyponyms()

                # Calculate depth (distance to root)
                depth = self._get_hypernym_depth(synset)

                # Get domain
                lexname = synset.lexname() if hasattr(synset, 'lexname') else None

                for lemma in synset.lemmas():
                    word = lemma.name().lower().replace('_', ' ')
                    pos = self._convert_pos(synset.pos())

                    entry = WordNetHierarchyEntry(
                        word=word,
                        pos=pos,
                        synset_name=synset.name(),
                        hypernym_depth=depth,
                        hyponym_count=len(hyponyms),
                        has_meronyms=bool(synset.part_meronyms() or synset.member_meronyms() or synset.substance_meronyms()),
                        has_holonyms=bool(synset.part_holonyms() or synset.member_holonyms() or synset.substance_holonyms()),
                        lexname=lexname,
                    )

                    if word not in self.entries:
                        self.entries[word] = []
                    self.entries[word].append(entry)
                    count += 1

            logger.info(f"Loaded {count} WordNet entries for {len(self.entries)} words")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load WordNet hierarchy: {e}")
            return False

    def _get_hypernym_depth(self, synset) -> int:
        """Calculate depth from root (cached)."""
        try:
            paths = synset.hypernym_paths()
            if not paths:
                return 0
            return min(len(p) for p in paths)
        except:
            return 0

    def _convert_pos(self, wn_pos: str) -> str:
        """Convert WordNet POS to readable form."""
        pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 'r': 'adv', 's': 'adj'}
        return pos_map.get(wn_pos, 'unknown')

    @lru_cache(maxsize=10000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map a word to GSE category primitives from its PRIMARY sense's IS-A path.

        Two corrections over the original union-over-senses version (both found
        in the Layer-1 audit):
          * **Primary sense only.** WordNet orders senses by frequency, so the
            primary synset is the everyday meaning. Unioning every sense bled
            ``dog``/``sauce`` → ``SOMEONE`` from the "contemptible person" sense.
          * **No meronym/holonym → PART.** "Has parts" is not the PART prime;
            tagging it fired PART on nearly everything (``tau``, ``georgia``).
            A genuine part still gets PART via its IS-A ancestor (``body_part`` →
            ``BODY/PART`` in ROOT_CONCEPT_PRIMITIVES), so nothing real is lost.
        """
        if not self._loaded:
            self.load()
        if self._wn is None:
            return {}
        syns = self._wn.synsets(word.lower().replace(' ', '_'))
        if not syns:
            return {}
        primary = syns[0]

        primitives: Dict[str, int] = {}
        lexname = primary.lexname() if hasattr(primary, 'lexname') else None
        if lexname and lexname in LEXNAME_TO_PRIMITIVE:
            for prim, val in LEXNAME_TO_PRIMITIVE[lexname].items():
                primitives.setdefault(prim, val)
        for path in primary.hypernym_paths():
            for anc in path:
                if anc.name() in ROOT_CONCEPT_PRIMITIVES:
                    for prim, val in ROOT_CONCEPT_PRIMITIVES[anc.name()].items():
                        primitives.setdefault(prim, val)
        return primitives

    def _apply_ancestor_primitives(self, word: str, primitives: Dict[str, int]):
        """Apply primitives from ancestor synsets."""
        if self._wn is None:
            return

        try:
            for synset in self._wn.synsets(word):
                for path in synset.hypernym_paths():
                    # Check first 5 ancestors (closer to word)
                    for ancestor in path[:5]:
                        if ancestor.name() in ROOT_CONCEPT_PRIMITIVES:
                            for prim, val in ROOT_CONCEPT_PRIMITIVES[ancestor.name()].items():
                                if prim not in primitives:
                                    primitives[prim] = val
        except:
            pass

    def get_all_words(self) -> List[str]:
        """Get all unique words."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_hypernyms(self, word: str, pos: str = None) -> List[str]:
        """Get hypernym chain for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            pos_char = pos[0] if pos else None
            synsets = self._wn.synsets(word, pos=pos_char)
            if not synsets:
                return []

            hypernyms = []
            for path in synsets[0].hypernym_paths():
                hypernyms.extend([s.name().split('.')[0] for s in path])

            # Remove duplicates while preserving order
            seen = set()
            result = []
            for h in hypernyms:
                if h not in seen:
                    seen.add(h)
                    result.append(h)
            return result
        except:
            return []

    def get_hyponyms(self, word: str, pos: str = None) -> List[str]:
        """Get direct hyponyms for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            pos_char = pos[0] if pos else None
            synsets = self._wn.synsets(word, pos=pos_char)
            if not synsets:
                return []

            hyponyms = []
            for hypo in synsets[0].hyponyms():
                for lemma in hypo.lemmas():
                    hyponyms.append(lemma.name().lower().replace('_', ' '))
            return hyponyms[:20]  # Limit results
        except:
            return []

    def get_meronyms(self, word: str) -> List[str]:
        """Get part-of relations for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            synsets = self._wn.synsets(word)
            if not synsets:
                return []

            meronyms = []
            for synset in synsets[:3]:  # Check first 3 senses
                for mero in synset.part_meronyms() + synset.member_meronyms() + synset.substance_meronyms():
                    for lemma in mero.lemmas():
                        meronyms.append(lemma.name().lower().replace('_', ' '))
            return list(set(meronyms))[:20]
        except:
            return []

    def get_domain(self, word: str) -> Optional[str]:
        """Get the primary semantic domain for a word."""
        if not self._loaded:
            self.load()

        entries = self.entries.get(word.lower(), [])
        if entries:
            return entries[0].lexname
        return None


def download_wordnet():
    """Download WordNet via NLTK."""
    import nltk
    nltk.download('wordnet')
    nltk.download('omw-1.4')
    print("WordNet downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = WordNetHierarchyParser()
    parser.load()

    # Test some words
    test_words = ['dog', 'run', 'happy', 'think', 'person', 'hand', 'love', 'water', 'tree']
    for word in test_words:
        domain = parser.get_domain(word)
        primitives = parser.to_primitives(word)
        hypernyms = parser.get_hypernyms(word)[:3]
        print(f"{word}: domain={domain}, primitives={primitives}, hypernyms={hypernyms}")
