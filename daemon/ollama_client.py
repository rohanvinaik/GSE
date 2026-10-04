"""
Ollama Client

Synchronous Ollama client for the audit daemon.
Used as fallback when external sources don't provide constraints.
"""

import logging
import re
from typing import Optional, Dict

logger = logging.getLogger(__name__)


# Primitive descriptions for prompting
PRIMITIVE_DESCRIPTIONS = {
    # Substantives
    "I": "first person, self-reference",
    "YOU": "second person, addressee",
    "SOMEONE": "person, human being",
    "SOMETHING": "thing, object, entity",
    "PEOPLE": "multiple persons, group",
    "BODY": "physical body, corporeal",
    "KIND": "type, category, class",
    "PART": "component, portion",

    # Mental
    "THINK": "cognitive process, reasoning",
    "KNOW": "knowledge, awareness, certainty",
    "WANT": "desire, wish, intention",
    "FEEL": "emotion, sensation, experience",
    "SEE": "visual perception",
    "HEAR": "auditory perception",
    "TOUCH": "tactile perception",
    "BELIEVE": "acceptance as true",
    "INFER": "deduction, reasoning",

    # Evaluators
    "GOOD": "positive, beneficial, desirable",
    "BAD": "negative, harmful, undesirable",
    "BIG": "large, great in size",
    "SMALL": "little, diminutive",

    # Action
    "DO": "action, agency, performance",
    "HAPPEN": "event, occurrence",
    "MOVE": "motion, locomotion",
    "SAY": "speech, utterance",
    "WORDS": "verbal expression, language",
    "HAVE": "possession, ownership",
    "BE": "existence, state",
    "EXIST": "existence, being",
    "ALIVE": "living, animate",
    "DEAD": "not alive, deceased",
    "START": "beginning, inception",
    "END": "termination, conclusion",
    "CAUSE": "causation, bringing about",

    # Temporal
    "WHEN": "time reference",
    "NOW": "present moment",
    "BEFORE": "prior, earlier",
    "AFTER": "later, subsequent",
    "LONG_TIME": "extended duration",
    "SHORT_TIME": "brief duration",
    "MOMENT": "instant, brief time",

    # Spatial
    "WHERE": "location reference",
    "HERE": "proximate location",
    "ABOVE": "higher position",
    "BELOW": "lower position",
    "FAR": "distant",
    "NEAR": "close, proximate",
    "INSIDE": "within, internal",
    "OUTSIDE": "external, exterior",
    "TOWARD": "direction approaching",
    "AWAY": "direction departing",
    "WITH": "accompaniment, together",
    "WITHOUT": "absence, lacking",

    # Logical
    "NOT": "negation",
    "MAYBE": "possibility, uncertainty",
    "CAN": "ability, capability",
    "MUST": "necessity, obligation",
    "BECAUSE": "reason, cause",
    "IF": "condition",
    "LIKE": "similarity, resemblance",
    "TRUE": "verity, accuracy",
    "FALSE": "untruth, inaccuracy",
    "INTENSITY": "degree, strength",
    "CERTAINTY": "confidence level",
}


class OllamaClient:
    """
    Synchronous Ollama client for primitive inference.

    Used as fallback when external NLP sources don't provide constraints.
    Supports multi-model voting for higher confidence.
    """

    def __init__(self, config: dict = None):
        """
        Initialize Ollama client.

        Args:
            config: Ollama configuration dict
        """
        self.config = config or {}
        self.base_url = self.config.get("base_url", "http://localhost:11434")
        self.model = self.config.get("model", "qwen2.5:3b")
        self.models = self.config.get("models", [self.model])
        self.timeout = self.config.get("timeout", 120)
        self.temperature = self.config.get("temperature", 0.1)
        self.num_predict = self.config.get("num_predict", 20)
        self.use_voting = self.config.get("use_voting", False)
        self.min_agreement = self.config.get("min_agreement", 2)
        self._available = None

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        if self._available is not None:
            return self._available

        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            self._available = response.status_code == 200
        except:
            self._available = False

        return self._available

    def _query_single_model(
        self,
        model: str,
        lemma: str,
        pos: str,
        primitive: str,
        definition: str = "",
    ) -> Optional[int]:
        """Query a single model for a primitive value."""
        try:
            import requests
        except ImportError:
            return None

        prim_desc = PRIMITIVE_DESCRIPTIONS.get(primitive, "semantic property")

        prompt = f"""For the word "{lemma}" ({pos}), determine if the semantic primitive "{primitive}" applies.

{primitive} means: {prim_desc}
{f"Definition: {definition}" if definition else ""}

Answer with ONLY one of these:
- "1" if {primitive} strongly applies to "{lemma}"
- "0" if {primitive} is neutral or not applicable
- "-1" if the opposite of {primitive} applies
- "?" if you are uncertain

Your answer (just the number or ?):"""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.num_predict,
                    }
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            text = response.json().get("response", "").strip()

            # Parse response
            if text.startswith("?"):
                return None

            # Look for first number
            match = re.search(r'-?1|0', text[:10])
            if match:
                return int(match.group())

            return None

        except Exception as e:
            logger.debug(f"Ollama query failed for {lemma}/{primitive} with {model}: {e}")
            return None

    def query_primitive_with_context(
        self,
        lemma: str,
        pos: str,
        primitive: str,
        definition: str = "",
        source_context: str = "",
    ) -> Optional[int]:
        """
        Query LLM to assign a primitive value, informed by external source data.

        The LLM acts as a TRANSLATION LAYER:
        - It receives data from external sources (VerbNet, NRC-VAD, etc.)
        - It interprets what these sources say about the word
        - It assigns a GSE primitive value that doesn't conflict with sources

        Args:
            lemma: The word
            pos: Part of speech
            primitive: The primitive to evaluate
            definition: Definition of the word
            source_context: Formatted external source data

        Returns:
            +1, 0, -1, or None if uncertain
        """
        if not self.is_available():
            return None

        prim_desc = PRIMITIVE_DESCRIPTIONS.get(primitive, "semantic property")

        # Build context-informed prompt
        prompt = f"""You are translating external NLP database information into GSE semantic primitives.

Word: "{lemma}" ({pos})
{f"Definition: {definition}" if definition else ""}

External source data for this word:
{source_context if source_context else "(no external data available)"}

Based on the external source data above, assign a value for the primitive "{primitive}".
{primitive} means: {prim_desc}

RULES:
- Your assignment must NOT conflict with what the external sources indicate
- If sources suggest this primitive applies, assign 1
- If sources suggest the opposite, assign -1
- If sources are neutral or don't mention it, assign 0
- If you're uncertain, respond with ?

Answer with ONLY: 1, 0, -1, or ?"""

        try:
            import requests
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.num_predict,
                    }
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            text = response.json().get("response", "").strip()

            if text.startswith("?"):
                return None

            match = re.search(r'-?1|0', text[:10])
            if match:
                return int(match.group())

            return None

        except Exception as e:
            logger.debug(f"Ollama query failed for {lemma}/{primitive}: {e}")
            return None

    def query_primitive(
        self,
        lemma: str,
        pos: str,
        primitive: str,
        definition: str = "",
    ) -> Optional[int]:
        """
        Query Ollama to infer a primitive value.

        If use_voting is enabled, queries multiple models and returns
        the majority vote if enough models agree.

        Args:
            lemma: The word
            pos: Part of speech
            primitive: The primitive to evaluate
            definition: Definition of the word (if available)

        Returns:
            +1, 0, -1, or None if uncertain
        """
        if not self.is_available():
            logger.debug("Ollama not available")
            return None

        if self.use_voting and len(self.models) > 1:
            return self._query_with_voting(lemma, pos, primitive, definition)
        else:
            return self._query_single_model(self.model, lemma, pos, primitive, definition)

    def _query_with_voting(
        self,
        lemma: str,
        pos: str,
        primitive: str,
        definition: str = "",
    ) -> Optional[int]:
        """
        Query multiple models and return majority vote.

        Args:
            lemma: The word
            pos: Part of speech
            primitive: The primitive to evaluate
            definition: Definition of the word

        Returns:
            +1, 0, -1, or None if no consensus
        """
        votes = {}
        model_responses = {}

        for model in self.models:
            result = self._query_single_model(model, lemma, pos, primitive, definition)
            model_responses[model] = result
            if result is not None:
                votes[result] = votes.get(result, 0) + 1

        logger.debug(f"Multi-model votes for {lemma}/{primitive}: {model_responses}")

        if not votes:
            return None

        # Find majority
        max_votes = max(votes.values())
        if max_votes >= self.min_agreement:
            # Return the value with most votes
            for value, count in votes.items():
                if count == max_votes:
                    logger.info(f"Multi-model consensus for {lemma}/{primitive}: {value} ({max_votes}/{len(self.models)} models)")
                    return value

        logger.debug(f"No consensus for {lemma}/{primitive}: {votes}")
        return None

    def query_primitives_batch(
        self,
        lemma: str,
        pos: str,
        primitives: list,
        definition: str = "",
    ) -> Dict[str, Optional[int]]:
        """
        Query multiple primitives at once (more efficient).

        Args:
            lemma: The word
            pos: Part of speech
            primitives: List of primitives to evaluate
            definition: Definition of the word

        Returns:
            Dict of primitive -> value (or None)
        """
        results = {}
        for prim in primitives:
            results[prim] = self.query_primitive(lemma, pos, prim, definition)
        return results


# Convenience function for testing
def test_ollama():
    """Test Ollama client."""
    from daemon.config import OLLAMA_CONFIG

    client = OllamaClient(OLLAMA_CONFIG)

    print(f"Ollama available: {client.is_available()}")

    if client.is_available():
        test_cases = [
            ("run", "verb", "MOVE"),
            ("happy", "adj", "GOOD"),
            ("think", "verb", "THINK"),
            ("dog", "noun", "ALIVE"),
        ]

        for lemma, pos, primitive in test_cases:
            result = client.query_primitive(lemma, pos, primitive)
            print(f"{lemma}.{primitive} = {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_ollama()
