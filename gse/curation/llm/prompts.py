"""
LLM Prompt Templates for Semantic Decomposition

Provides prompts for the Qwen3-8B model to generate full 72-primitive decompositions.
"""

from typing import Dict, List, Optional

# Batch configuration by phase - all use full pipeline
BATCH_CONFIG: Dict[str, Dict] = {
    "phase_1": {
        "batch_size": 10,
        "temperature": 0.3,
        "max_tokens": 2000,
        "retry_on_validation_fail": True,
        "human_review_threshold": 0.7,
    },
    "phase_2": {
        "batch_size": 10,  # Same as Phase 1
        "temperature": 0.3,  # Same as Phase 1
        "max_tokens": 2000,
        "retry_on_validation_fail": True,
        "human_review_threshold": 0.7,  # Same as Phase 1
    },
    "phase_3": {
        "batch_size": 10,  # Same as Phase 1
        "temperature": 0.3,  # Same as Phase 1
        "max_tokens": 2000,
        "retry_on_validation_fail": True,  # Full validation
        "human_review_threshold": 0.7,  # Same as Phase 1
    },
}


SYSTEM_PROMPT = """You are a semantic primitive analyst for the GSE (Geometrically-optimized Semantic Encoding) system.

Your task is to decompose English words into semantic primitives. The GSE system has 72 primitives organized into 8 semantic banks:

## BANK 0 - SUBSTANTIVES (10 primitives)
I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY, KIND, PART, SAME, OTHER

## BANK 1 - QUANTITY (3 primitives)
ONE, TWO, QUANTITY

## BANK 2 - EVALUATORS (4 primitives)
GOOD, BAD, BIG, SMALL

## BANK 3 - MENTAL (7 primitives)
THINK, KNOW, WANT, FEEL, SEE, HEAR, INFER

## BANK 4 - ACTION (10 primitives)
SAY, WORDS, DO, HAPPEN, MOVE, BE, HAVE, EXIST, ALIVE, DEAD

## BANK 5 - TEMPORAL (10 primitives)
MOMENT, WHEN, LONG_TIME, SHORT_TIME, BEFORE, AFTER, THEN, NOW, START, END

## BANK 6 - SPATIAL (14 primitives)
WHERE, HERE, SIDE, TOUCH, ABOVE, BELOW, FAR, NEAR, OUTSIDE, INSIDE, TOWARD, AWAY, WITH, WITHOUT

## BANK 7 - LOGICAL (14 primitives)
NOT, MAYBE, CAN, MUST, BECAUSE, CAUSE, IF, LIKE, TRUE, FALSE, HIER_PLUS, HIER_MINUS, INTENSITY, CERTAINTY

## ENCODING RULES

For each primitive, assign:
- +1 if the word POSITIVELY involves this primitive (core semantic component)
- -1 if the word NEGATIVELY involves this primitive (opposite/absence is core)
- 0 if the primitive is NOT RELEVANT to the word's meaning

## BIPOLAR CONSTRAINTS (CRITICAL - violations are errors)

The following pairs are BIPOLAR - they cannot BOTH be non-zero:
- SAME/OTHER (identity)
- GOOD/BAD (evaluation)
- BIG/SMALL (size)
- ALIVE/DEAD (vitality)
- LONG_TIME/SHORT_TIME (duration)
- BEFORE/AFTER (temporal order)
- THEN/NOW (temporal reference)
- START/END (temporal bounds)
- ABOVE/BELOW (vertical)
- FAR/NEAR (distance)
- OUTSIDE/INSIDE (containment)
- TOWARD/AWAY (direction)
- WITH/WITHOUT (accompaniment)
- TRUE/FALSE (truth)

For bipolar pairs, use ONLY the positive pole with appropriate polarity:
- "bad" → GOOD: -1, BAD: 0 (not GOOD: 0, BAD: 1)
- "small" → BIG: -1, SMALL: 0 (not BIG: 0, SMALL: 1)

## OUTPUT FORMAT

Return ONLY a JSON object with ONLY the NON-ZERO primitives.
Format: {"PRIMITIVE": 1} for positive, {"PRIMITIVE": -1} for negative.
Use integer values (1, -1), not strings or "+1".
Omit primitives with value 0.
No explanation, just the JSON object."""


USER_PROMPT_TEMPLATE = """Decompose the word "{word}" into GSE primitives.

Part of speech: {pos}
Definition hint: {gloss}

Think step by step:
1. What is the core meaning?
2. What entities are involved (SOMEONE, SOMETHING, BODY, etc.)?
3. What actions or states (DO, BE, HAVE, MOVE, etc.)?
4. Any evaluative aspects (GOOD/BAD, BIG/SMALL)?
5. Any temporal aspects (BEFORE/AFTER, NOW/THEN, START/END)?
6. Any spatial aspects (INSIDE/OUTSIDE, NEAR/FAR, TOWARD/AWAY)?
7. Any modal/logical aspects (CAN, MUST, MAYBE, BECAUSE)?

Return JSON with ONLY NON-ZERO primitives. Use 1 or -1 as values (not "+1").
Remember: Bipolar pairs cannot both be non-zero."""


SIMPLE_USER_PROMPT = """Decompose "{word}" ({pos}).
Return JSON with ONLY the relevant primitives and their values (1 or -1).
Example: {{"BE": 1, "GOOD": -1}} for a negative state of being."""


def build_user_prompt(
    word: str,
    pos: str = "unknown",
    gloss: Optional[str] = None,
    simple: bool = False,
) -> str:
    """
    Build the user prompt for decomposition.

    Args:
        word: The word to decompose
        pos: Part of speech
        gloss: Optional definition/gloss
        simple: Use shorter prompt (for batch efficiency)
    """
    if simple:
        return SIMPLE_USER_PROMPT.format(word=word, pos=pos)

    return USER_PROMPT_TEMPLATE.format(
        word=word,
        pos=pos,
        gloss=gloss or "Not provided",
    )


def build_batch_prompt(words: List[Dict[str, str]]) -> str:
    """
    Build a batch prompt for multiple words.

    Args:
        words: List of dicts with 'word', 'pos', and optionally 'gloss'

    Returns:
        Formatted prompt for batch decomposition
    """
    word_list = []
    for i, w in enumerate(words, 1):
        word_str = f"{i}. {w['word']} ({w.get('pos', 'unknown')})"
        if gloss := w.get('gloss'):
            word_str += f" - {gloss}"
        word_list.append(word_str)

    return f"""Decompose each of these words into GSE primitives:

{chr(10).join(word_list)}

For EACH word, return a JSON object with ALL 72 primitives as keys and -1/0/+1 as values.
Format your response as a JSON array with one object per word, in the same order as the input.
Remember: Bipolar pairs cannot both be non-zero."""


# Example decompositions for few-shot prompting
EXAMPLE_DECOMPOSITIONS = {
    "happy": {
        "I": 0, "YOU": 0, "SOMEONE": 1, "SOMETHING": 0, "PEOPLE": 0, "BODY": 0,
        "KIND": 0, "PART": 0, "SAME": 0, "OTHER": 0,
        "ONE": 0, "TWO": 0, "QUANTITY": 0,
        "GOOD": 1, "BAD": 0, "BIG": 0, "SMALL": 0,
        "THINK": 0, "KNOW": 0, "WANT": 0, "FEEL": 1, "SEE": 0, "HEAR": 0, "INFER": 0,
        "SAY": 0, "WORDS": 0, "DO": 0, "HAPPEN": 0, "MOVE": 0, "BE": 1, "HAVE": 0,
        "EXIST": 0, "ALIVE": 0, "DEAD": 0,
        "MOMENT": 0, "WHEN": 0, "LONG_TIME": 0, "SHORT_TIME": 0, "BEFORE": 0,
        "AFTER": 0, "THEN": 0, "NOW": 1, "START": 0, "END": 0,
        "WHERE": 0, "HERE": 0, "SIDE": 0, "TOUCH": 0, "ABOVE": 0, "BELOW": 0,
        "FAR": 0, "NEAR": 0, "OUTSIDE": 0, "INSIDE": 1, "TOWARD": 0, "AWAY": 0,
        "WITH": 0, "WITHOUT": 0,
        "NOT": 0, "MAYBE": 0, "CAN": 0, "MUST": 0, "BECAUSE": 0, "CAUSE": 0,
        "IF": 0, "LIKE": 0, "TRUE": 0, "FALSE": 0,
        "HIER_PLUS": 0, "HIER_MINUS": 0, "INTENSITY": 1, "CERTAINTY": 0,
    },
    "sad": {
        "I": 0, "YOU": 0, "SOMEONE": 1, "SOMETHING": 0, "PEOPLE": 0, "BODY": 0,
        "KIND": 0, "PART": 0, "SAME": 0, "OTHER": 0,
        "ONE": 0, "TWO": 0, "QUANTITY": 0,
        "GOOD": -1, "BAD": 0, "BIG": 0, "SMALL": 0,  # Note: BAD is GOOD=-1
        "THINK": 0, "KNOW": 0, "WANT": 0, "FEEL": 1, "SEE": 0, "HEAR": 0, "INFER": 0,
        "SAY": 0, "WORDS": 0, "DO": 0, "HAPPEN": 0, "MOVE": 0, "BE": 1, "HAVE": 0,
        "EXIST": 0, "ALIVE": 0, "DEAD": 0,
        "MOMENT": 0, "WHEN": 0, "LONG_TIME": 0, "SHORT_TIME": 0, "BEFORE": 0,
        "AFTER": 0, "THEN": 0, "NOW": 1, "START": 0, "END": 0,
        "WHERE": 0, "HERE": 0, "SIDE": 0, "TOUCH": 0, "ABOVE": 0, "BELOW": 0,
        "FAR": 0, "NEAR": 0, "OUTSIDE": 0, "INSIDE": 1, "TOWARD": 0, "AWAY": 0,
        "WITH": 0, "WITHOUT": 0,
        "NOT": 0, "MAYBE": 0, "CAN": 0, "MUST": 0, "BECAUSE": 0, "CAUSE": 0,
        "IF": 0, "LIKE": 0, "TRUE": 0, "FALSE": 0,
        "HIER_PLUS": 0, "HIER_MINUS": 0, "INTENSITY": 1, "CERTAINTY": 0,
    },
    "walk": {
        "I": 0, "YOU": 0, "SOMEONE": 1, "SOMETHING": 0, "PEOPLE": 0, "BODY": 1,
        "KIND": 0, "PART": 0, "SAME": 0, "OTHER": 0,
        "ONE": 0, "TWO": 0, "QUANTITY": 0,
        "GOOD": 0, "BAD": 0, "BIG": 0, "SMALL": 0,
        "THINK": 0, "KNOW": 0, "WANT": 0, "FEEL": 0, "SEE": 0, "HEAR": 0, "INFER": 0,
        "SAY": 0, "WORDS": 0, "DO": 1, "HAPPEN": 0, "MOVE": 1, "BE": 0, "HAVE": 0,
        "EXIST": 0, "ALIVE": 1, "DEAD": 0,
        "MOMENT": 0, "WHEN": 0, "LONG_TIME": 0, "SHORT_TIME": 0, "BEFORE": 0,
        "AFTER": 0, "THEN": 0, "NOW": 0, "START": 0, "END": 0,
        "WHERE": 1, "HERE": 0, "SIDE": 0, "TOUCH": 1, "ABOVE": 0, "BELOW": 1,
        "FAR": 0, "NEAR": 0, "OUTSIDE": 0, "INSIDE": 0, "TOWARD": 1, "AWAY": 0,
        "WITH": 0, "WITHOUT": 0,
        "NOT": 0, "MAYBE": 0, "CAN": 1, "MUST": 0, "BECAUSE": 0, "CAUSE": 0,
        "IF": 0, "LIKE": 0, "TRUE": 0, "FALSE": 0,
        "HIER_PLUS": 0, "HIER_MINUS": 0, "INTENSITY": 0, "CERTAINTY": 0,
    },
}


def build_few_shot_prompt(
    word: str,
    pos: str = "unknown",
    gloss: Optional[str] = None,
    n_examples: int = 2,
) -> str:
    """
    Build a few-shot prompt with examples.

    Args:
        word: The word to decompose
        pos: Part of speech
        gloss: Optional definition
        n_examples: Number of examples to include
    """
    import json

    examples = list(EXAMPLE_DECOMPOSITIONS.items())[:n_examples]

    example_text = ""
    for ex_word, decomp in examples:
        example_text += f'\nExample: "{ex_word}"\n'
        example_text += json.dumps(decomp, indent=2) + "\n"

    return f"""Here are example decompositions:
{example_text}

Now decompose "{word}" ({pos}){f' - {gloss}' if gloss else ''} using the same format.
Return ONLY the JSON object with all 72 primitives."""
