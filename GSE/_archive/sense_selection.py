"""
Context-Sensitive Sense Selection for GSE.

Implements word sense disambiguation using:
1. Semantic bank compatibility with context
2. Syntactic context (dependency relations)
3. Selectional preferences of predicates
4. Domain/topic coherence
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import numpy as np

from gse.vectors import SparseVector, D, DIMS_PER_BANK, SemanticBank
from gse.lexicon_generator import LexiconEntry, Lexicon


@dataclass
class WordSense:
    """A distinct sense of a word."""
    sense_id: str
    gloss: str
    decomposition: List[Tuple[str, str]]
    vector: SparseVector
    domain: Optional[str]          # Domain/topic (food, sports, etc.)
    frequency: float               # How common is this sense
    selectional_prefs: Dict[str, Set[str]]  # role -> expected primitives


@dataclass
class SenseSelectionResult:
    """Result of sense disambiguation."""
    selected_sense: WordSense
    confidence: float
    alternatives: List[Tuple[WordSense, float]]  # Other senses with scores
    reasoning: str                 # Why this sense was selected


# Common word senses with different meanings
POLYSEMOUS_WORDS: Dict[str, List[Dict]] = {
    "bank": [
        {
            "sense_id": "bank.NOUN.financial",
            "gloss": "financial institution",
            "decomposition": [("SOMETHING", "theme"), ("HAVE", "state"), ("SOMETHING", "content")],
            "domain": "finance",
            "selectional_prefs": {"patient": {"SOMETHING"}, "location": {"WHERE"}},
        },
        {
            "sense_id": "bank.NOUN.river",
            "gloss": "side of a river",
            "decomposition": [("SOMETHING", "theme"), ("WHERE", "location"), ("SIDE", "attribute")],
            "domain": "geography",
            "selectional_prefs": {"location": {"WHERE", "NEAR"}},
        },
    ],
    "run": [
        {
            "sense_id": "run.VERB.motion",
            "gloss": "move quickly on foot",
            "decomposition": [("SOMEONE", "agent"), ("MOVE", "action"), ("VERY", "manner")],
            "domain": "motion",
            "selectional_prefs": {"agent": {"SOMEONE", "SOMETHING"}},
        },
        {
            "sense_id": "run.VERB.operate",
            "gloss": "operate or manage",
            "decomposition": [("SOMEONE", "agent"), ("DO", "action"), ("SOMETHING", "patient")],
            "domain": "business",
            "selectional_prefs": {"agent": {"SOMEONE"}, "patient": {"SOMETHING"}},
        },
        {
            "sense_id": "run.VERB.flow",
            "gloss": "flow (of liquids)",
            "decomposition": [("SOMETHING", "theme"), ("MOVE", "action")],
            "domain": "physical",
            "selectional_prefs": {"theme": {"SOMETHING"}},
        },
    ],
    "light": [
        {
            "sense_id": "light.NOUN.illumination",
            "gloss": "electromagnetic radiation",
            "decomposition": [("SOMETHING", "theme"), ("SEE", "state")],
            "domain": "physics",
            "selectional_prefs": {},
        },
        {
            "sense_id": "light.ADJ.weight",
            "gloss": "not heavy",
            "decomposition": [("SMALL", "attribute"), ("NOT", "state"), ("BIG", "evaluation")],
            "domain": "physical",
            "selectional_prefs": {},
        },
        {
            "sense_id": "light.ADJ.brightness",
            "gloss": "bright, not dark",
            "decomposition": [("GOOD", "attribute"), ("SEE", "state")],
            "domain": "visual",
            "selectional_prefs": {},
        },
    ],
    "break": [
        {
            "sense_id": "break.VERB.physical",
            "gloss": "separate into pieces",
            "decomposition": [("SOMEONE", "agent"), ("DO", "action"), ("SOMETHING", "patient"),
                             ("PART", "result")],
            "domain": "physical",
            "selectional_prefs": {"patient": {"SOMETHING"}},
        },
        {
            "sense_id": "break.VERB.violate",
            "gloss": "violate a rule",
            "decomposition": [("SOMEONE", "agent"), ("DO", "action"), ("NOT", "manner"),
                             ("GOOD", "evaluation")],
            "domain": "social",
            "selectional_prefs": {"patient": {"WORDS", "SOMETHING"}},
        },
        {
            "sense_id": "break.NOUN.pause",
            "gloss": "an interruption",
            "decomposition": [("MOMENT", "time"), ("NOT", "state"), ("DO", "action")],
            "domain": "temporal",
            "selectional_prefs": {},
        },
    ],
    "plant": [
        {
            "sense_id": "plant.NOUN.organism",
            "gloss": "living organism (vegetation)",
            "decomposition": [("SOMETHING", "theme"), ("LIVE", "state"), ("NOT", "attribute"),
                             ("MOVE", "attribute")],
            "domain": "biology",
            "selectional_prefs": {},
        },
        {
            "sense_id": "plant.NOUN.factory",
            "gloss": "industrial facility",
            "decomposition": [("SOMETHING", "theme"), ("WHERE", "location"), ("DO", "action")],
            "domain": "industry",
            "selectional_prefs": {},
        },
        {
            "sense_id": "plant.VERB.sow",
            "gloss": "put a seed in ground",
            "decomposition": [("SOMEONE", "agent"), ("DO", "action"), ("SOMETHING", "patient"),
                             ("INSIDE", "location")],
            "domain": "agriculture",
            "selectional_prefs": {"agent": {"SOMEONE"}, "patient": {"SOMETHING"}},
        },
    ],
}

# Domain indicators - words that suggest a particular domain
DOMAIN_INDICATORS: Dict[str, Set[str]] = {
    "finance": {"money", "account", "deposit", "loan", "interest", "investment", "stock"},
    "geography": {"river", "stream", "water", "shore", "land", "lake", "mountain"},
    "motion": {"fast", "quick", "speed", "race", "move", "walk", "jog"},
    "business": {"company", "manage", "operate", "business", "organization", "staff"},
    "physical": {"heavy", "weight", "mass", "material", "solid", "liquid"},
    "biology": {"grow", "leaf", "root", "flower", "seed", "tree", "garden"},
    "industry": {"factory", "manufacture", "production", "worker", "machine"},
    "social": {"rule", "law", "promise", "agreement", "contract"},
    "temporal": {"time", "pause", "stop", "wait", "continue", "resume"},
}


class SenseSelector:
    """
    Select the most appropriate word sense based on context.

    Uses multiple signals:
    1. Domain coherence with context words
    2. Selectional preference satisfaction
    3. Semantic bank compatibility
    4. Syntactic context
    """

    def __init__(self, lexicon: Lexicon = None):
        self.lexicon = lexicon
        self.polysemous_words = POLYSEMOUS_WORDS
        self.domain_indicators = DOMAIN_INDICATORS

    def get_senses(self, word: str, pos: str = None) -> List[WordSense]:
        """Get all available senses for a word."""
        word_lower = word.lower()
        senses = []

        # Check polysemous word database
        if word_lower in self.polysemous_words:
            for sense_def in self.polysemous_words[word_lower]:
                # Filter by POS if provided
                sense_pos = sense_def["sense_id"].split(".")[1]
                if pos and pos.upper() != sense_pos:
                    continue

                senses.append(WordSense(
                    sense_id=sense_def["sense_id"],
                    gloss=sense_def["gloss"],
                    decomposition=sense_def["decomposition"],
                    vector=SparseVector.zeros(D),  # Would need to encode
                    domain=sense_def.get("domain"),
                    frequency=1.0,
                    selectional_prefs=sense_def.get("selectional_prefs", {}),
                ))

        # Also check lexicon for additional senses
        if self.lexicon:
            entries = self.lexicon.get_all_senses(word_lower)
            for entry in entries:
                if pos and entry.pos != pos:
                    continue
                # Don't duplicate if already in polysemous database
                if not any(s.sense_id == entry.sense_id for s in senses):
                    senses.append(WordSense(
                        sense_id=entry.sense_id,
                        gloss=entry.gloss,
                        decomposition=entry.decomposition,
                        vector=entry.vector,
                        domain=None,
                        frequency=entry.frequency,
                        selectional_prefs={},
                    ))

        return senses

    def detect_domain(self, context_words: List[str]) -> Dict[str, float]:
        """
        Detect likely domains from context words.

        Returns:
            Dict mapping domain names to confidence scores
        """
        domain_scores: Dict[str, float] = {}

        for word in context_words:
            word_lower = word.lower()
            for domain, indicators in self.domain_indicators.items():
                if word_lower in indicators:
                    domain_scores[domain] = domain_scores.get(domain, 0) + 1.0

        # Normalize
        total = sum(domain_scores.values()) or 1.0
        return {d: s / total for d, s in domain_scores.items()}

    def select_sense(
        self,
        word: str,
        pos: str = None,
        context_words: List[str] = None,
        context_vectors: List[SparseVector] = None,
        syntactic_context: Dict[str, str] = None
    ) -> SenseSelectionResult:
        """
        Select the best sense for a word given context.

        Args:
            word: The word to disambiguate
            pos: Part of speech (helps filter senses)
            context_words: Other words in the sentence
            context_vectors: Vectors of context words (for similarity)
            syntactic_context: Dict with syntactic info (head, dependents, etc.)

        Returns:
            SenseSelectionResult with selected sense and confidence
        """
        senses = self.get_senses(word, pos)

        if not senses:
            # No senses found, return default
            return SenseSelectionResult(
                selected_sense=WordSense(
                    sense_id=f"{word}.{pos or 'UNKNOWN'}.default",
                    gloss="default sense",
                    decomposition=[("SOMETHING", "theme")],
                    vector=SparseVector.zeros(D),
                    domain=None,
                    frequency=0.5,
                    selectional_prefs={},
                ),
                confidence=0.5,
                alternatives=[],
                reasoning="No specific senses found, using default"
            )

        if len(senses) == 1:
            return SenseSelectionResult(
                selected_sense=senses[0],
                confidence=1.0,
                alternatives=[],
                reasoning="Only one sense available"
            )

        # Score each sense
        sense_scores: List[Tuple[WordSense, float, str]] = []

        # Detect domain from context
        context_words = context_words or []
        domain_scores = self.detect_domain(context_words)

        for sense in senses:
            score = 0.0
            reasons = []

            # 1. Domain match
            if sense.domain and sense.domain in domain_scores:
                domain_bonus = domain_scores[sense.domain] * 2.0
                score += domain_bonus
                reasons.append(f"domain match ({sense.domain})")

            # 2. Frequency prior
            freq_score = sense.frequency * 0.5
            score += freq_score
            if sense.frequency > 0.7:
                reasons.append("high frequency")

            # 3. Selectional preference satisfaction
            if syntactic_context and sense.selectional_prefs:
                for role, expected_prims in sense.selectional_prefs.items():
                    if role in syntactic_context:
                        # Check if context word matches expected primitives
                        # This would need actual primitive checking
                        score += 0.3
                        reasons.append(f"selectional fit ({role})")

            # 4. Context vector similarity (if available)
            if context_vectors and sense.vector.nnz > 0:
                avg_sim = np.mean([
                    sense.vector.cosine(cv) for cv in context_vectors
                    if cv.nnz > 0
                ])
                if avg_sim > 0.3:
                    score += avg_sim
                    reasons.append(f"context similarity ({avg_sim:.2f})")

            sense_scores.append((sense, score, ", ".join(reasons) or "default"))

        # Sort by score
        sense_scores.sort(key=lambda x: -x[1])

        best_sense, best_score, best_reason = sense_scores[0]
        alternatives = [(s, sc) for s, sc, _ in sense_scores[1:]]

        # Compute confidence based on score gap
        if len(sense_scores) > 1:
            second_score = sense_scores[1][1]
            gap = best_score - second_score
            confidence = min(1.0, 0.5 + gap * 0.5)
        else:
            confidence = 1.0

        return SenseSelectionResult(
            selected_sense=best_sense,
            confidence=confidence,
            alternatives=alternatives,
            reasoning=best_reason
        )

    def disambiguate_sentence(
        self,
        words: List[Tuple[str, str]],  # (word, pos) pairs
    ) -> Dict[int, SenseSelectionResult]:
        """
        Disambiguate all words in a sentence.

        Uses iterative refinement: first pass gives rough senses,
        then refine based on selected senses.

        Args:
            words: List of (word, pos) tuples

        Returns:
            Dict mapping word index to sense selection result
        """
        # First pass: use only surface context
        context_words = [w for w, _ in words]
        results = {}

        for i, (word, pos) in enumerate(words):
            other_words = [w for j, (w, _) in enumerate(words) if j != i]
            result = self.select_sense(
                word=word,
                pos=pos,
                context_words=other_words
            )
            results[i] = result

        # Could do second pass using selected sense vectors as context
        # for refinement, but keeping simple for now

        return results


# Singleton instance
_selector = None


def get_sense_selector(lexicon: Lexicon = None) -> SenseSelector:
    """Get or create the sense selector singleton."""
    global _selector
    if _selector is None:
        _selector = SenseSelector(lexicon)
    return _selector
