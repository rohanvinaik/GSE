#!/usr/bin/env python3
"""
LLM-Based Conflict Resolver for Wiktionary Primitives

Uses local LLMs to resolve conflicts between Wiktionary primitive assignments
and external NLP databases (NRC, USAS, ConceptNet, Sensorimotor).

Strategy:
1. Load conflicts from audit report (highest-frequency words first)
2. For each conflict, present the LLM with:
   - The word and its definition (from Wiktionary)
   - Current Wiktionary primitive value
   - External source value(s) with their reasoning
3. LLM decides the correct value based on semantic reasoning
4. Apply corrections to the database

Usage:
    python scripts/llm_conflict_resolver.py --primitive GOOD --limit 100
    python scripts/llm_conflict_resolver.py --primitive THINK --batch-size 20
    python scripts/llm_conflict_resolver.py --all-primitives --limit 500
"""

import argparse
import json
import logging
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
EXTERNAL_DIR = DATA_DIR / "external"
WIKT_DB = EXTERNAL_DIR / "wiktionary" / "wiktionary_primitives.db"
AUDIT_REPORT = DATA_DIR / "audit_results" / "audit_report.json"
CORRECTIONS_LOG = DATA_DIR / "audit_results" / "llm_corrections.jsonl"

# LLM Configuration
DEFAULT_MODEL = "qwen2.5:14b"  # Good balance of speed and quality
OLLAMA_URL = "http://localhost:11434/api/generate"

# Primitives in order of conflict count (from audit)
PRIMITIVES_BY_CONFLICT = [
    "GOOD",
    "THINK",
    "CAN",
    "FEEL",
    "MUST",
    "BODY",
    "SAME",
    "LIKE",
    "PART",
    "WHERE",
    "HEAR",
    "SEE",
    "PEOPLE",
    "TOUCH",
    "SAY",
    "DO",
    "SOMEONE",
    "MOVE",
    "WANT",
]

# External source descriptions for LLM context
SOURCE_DESCRIPTIONS = {
    "nrc_emotion": "NRC Emotion Lexicon - crowdsourced emotion associations (anger, joy, fear, etc.)",
    "nrc_vad": "NRC VAD - Valence (positive/negative), Arousal (calm/excited), Dominance (submissive/dominant)",
    "usas": "USAS Semantic Tagger - Lancaster University semantic categories",
    "sensorimotor": "Lancaster Sensorimotor Norms - empirical ratings of sensory/motor associations",
    "conceptnet": "ConceptNet - commonsense knowledge graph with semantic relations",
    "concreteness": "Brysbaert Concreteness Ratings - abstract vs concrete word ratings",
}

# Primitive explanations for LLM
PRIMITIVE_EXPLANATIONS = {
    "GOOD": "Positive evaluation/valence (+1) vs negative evaluation (-1). Words like 'happy', 'beautiful' are GOOD=+1; 'sad', 'ugly' are GOOD=-1.",
    "THINK": "Mental/cognitive activity (+1) or lack thereof (-1). 'Intelligent', 'reason' are THINK=+1; 'dull', 'mindless' are THINK=-1.",
    "CAN": "Ability/capability (+1) or inability (-1). 'Capable', 'skilled' are CAN=+1; 'incompetent', 'unable' are CAN=-1.",
    "FEEL": "Emotional/sensory experience (+1). 'Joy', 'pain', 'anger' involve FEEL=+1.",
    "BODY": "Physical/bodily involvement (+1). 'Hand', 'run', 'eat' involve BODY=+1.",
    "TOUCH": "Tactile/haptic involvement (+1). 'Grasp', 'soft', 'poke' involve TOUCH=+1.",
    "HEAR": "Auditory involvement (+1). 'Listen', 'loud', 'music' involve HEAR=+1.",
    "SEE": "Visual involvement (+1). 'Look', 'bright', 'picture' involve SEE=+1.",
    "MUST": "Obligation/necessity (+1). 'Required', 'mandatory' involve MUST=+1.",
    "WANT": "Desire/volition (+1). 'Desire', 'wish', 'crave' involve WANT=+1.",
    "SAME": "Similarity/identity (+1) or difference (-1). 'Identical', 'alike' are SAME=+1.",
    "LIKE": "Resemblance/comparison (+1). Metaphorical or simile usage.",
    "MAYBE": "Uncertainty/possibility (+1). Evaluative adjectives often have MAYBE=+1.",
}


@dataclass
class Conflict:
    """A conflict between Wiktionary and external source."""

    word: str
    primitive: str
    wikt_value: int
    source: str
    source_value: int
    conflict_type: str  # "missing_in_wikt" or "value_mismatch"
    frequency_rank: int = 0
    definition: str = ""


@dataclass
class Resolution:
    """LLM resolution of a conflict."""

    word: str
    primitive: str
    old_value: int
    new_value: int
    confidence: str  # "high", "medium", "low"
    reasoning: str
    source_agreement: List[str]
    model: str
    timestamp: str


def query_ollama(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 120) -> str:
    """Query local Ollama model."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistency
                    "num_predict": 200,
                },
            },
            timeout=timeout,
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            logger.error(f"Ollama error: {response.status_code}")
            return f"ERROR:{response.status_code}"
    except Exception as e:
        logger.error(f"Ollama exception: {e}")
        return f"ERROR:{e}"


def load_conflicts(primitive: str = None, limit: int = None) -> List[Conflict]:
    """Load conflicts from audit report, optionally filtered by primitive."""
    if not AUDIT_REPORT.exists():
        logger.error(f"Audit report not found: {AUDIT_REPORT}")
        return []

    with open(AUDIT_REPORT, "r") as f:
        report = json.load(f)

    conflicts = []
    for item in report.get("sample_conflicts", []):
        if primitive and item["primitive"] != primitive:
            continue

        conflicts.append(
            Conflict(
                word=item["word"],
                primitive=item["primitive"],
                wikt_value=item["wikt_value"],
                source=item["source"],
                source_value=item["source_value"],
                conflict_type=item["type"],
                frequency_rank=item.get("frequency_rank", 0),
            )
        )

    # Sort by frequency rank (most common words first)
    conflicts.sort(key=lambda c: c.frequency_rank)

    if limit:
        conflicts = conflicts[:limit]

    return conflicts


def load_all_conflicts_for_primitive(primitive: str) -> List[Conflict]:
    """Load ALL conflicts for a specific primitive from the database comparison."""
    conflicts = []

    # Connect to Wiktionary DB
    wikt_conn = sqlite3.connect(str(WIKT_DB))

    # Load external source data and compare
    # This is more thorough than the sample_conflicts in the audit report

    # Load NRC VAD for GOOD/CAN conflicts
    if primitive in ("GOOD", "CAN"):
        nrc_vad_path = EXTERNAL_DIR / "nrc_vad.txt"
        if nrc_vad_path.exists():
            with open(nrc_vad_path, "r") as f:
                next(f)  # Skip header
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) != 4:
                        continue
                    word, valence, arousal, dominance = parts
                    word = word.lower()

                    try:
                        v = float(valence)
                        d = float(dominance)

                        # Check GOOD conflicts (valence)
                        if primitive == "GOOD":
                            if v >= 0.3:
                                expected = 1
                            elif v <= -0.3:
                                expected = -1
                            else:
                                continue

                            # Get current Wiktionary value
                            cursor = wikt_conn.execute(
                                """
                                SELECT value FROM word_primitives
                                WHERE word = ? AND primitive = 'GOOD'
                                LIMIT 1
                            """,
                                (word,),
                            )
                            row = cursor.fetchone()
                            current = row[0] if row else 0

                            if current != expected:
                                conflicts.append(
                                    Conflict(
                                        word=word,
                                        primitive="GOOD",
                                        wikt_value=current,
                                        source="nrc_vad",
                                        source_value=expected,
                                        conflict_type="value_mismatch" if current != 0 else "missing_in_wikt",
                                    )
                                )

                        # Check CAN conflicts (dominance)
                        elif primitive == "CAN":
                            if d >= 0.3:
                                expected = 1
                            elif d <= -0.3:
                                expected = -1
                            else:
                                continue

                            cursor = wikt_conn.execute(
                                """
                                SELECT value FROM word_primitives
                                WHERE word = ? AND primitive = 'CAN'
                                LIMIT 1
                            """,
                                (word,),
                            )
                            row = cursor.fetchone()
                            current = row[0] if row else 0

                            if current != expected:
                                conflicts.append(
                                    Conflict(
                                        word=word,
                                        primitive="CAN",
                                        wikt_value=current,
                                        source="nrc_vad",
                                        source_value=expected,
                                        conflict_type="value_mismatch" if current != 0 else "missing_in_wikt",
                                    )
                                )
                    except ValueError:
                        continue

    wikt_conn.close()

    # Remove duplicates
    seen = set()
    unique_conflicts = []
    for c in conflicts:
        key = (c.word, c.primitive)
        if key not in seen:
            seen.add(key)
            unique_conflicts.append(c)

    logger.info(f"Loaded {len(unique_conflicts)} conflicts for {primitive}")
    return unique_conflicts


def get_word_definition(word: str, conn: sqlite3.Connection) -> str:
    """Get the definition of a word from Wiktionary DB."""
    # Try to get from definitions table if it exists
    try:
        cursor = conn.execute(
            """
            SELECT definition FROM definitions
            WHERE word = ? LIMIT 1
        """,
            (word,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    return ""


def get_word_context(word: str, conn: sqlite3.Connection) -> Dict:
    """Get full context for a word from the database."""
    context = {"word": word, "primitives": {}, "sources": []}

    # Get all primitive assignments
    cursor = conn.execute(
        """
        SELECT primitive, value, source, confidence
        FROM word_primitives
        WHERE word = ?
    """,
        (word,),
    )

    for prim, val, source, conf in cursor:
        if prim not in context["primitives"]:
            context["primitives"][prim] = []
        context["primitives"][prim].append({"value": val, "source": source, "confidence": conf})
        if source not in context["sources"]:
            context["sources"].append(source)

    return context


def build_resolution_prompt(conflict: Conflict, context: Dict) -> str:
    """Build prompt for LLM to resolve a conflict."""

    prim_explanation = PRIMITIVE_EXPLANATIONS.get(conflict.primitive, f"Primitive {conflict.primitive}")

    source_desc = SOURCE_DESCRIPTIONS.get(conflict.source, f"External NLP database: {conflict.source}")

    # Get all current assignments for this primitive
    current_assignments = context["primitives"].get(conflict.primitive, [])
    current_str = (
        ", ".join([f"{a['value']} (from {a['source']}, conf={a['confidence']:.2f})" for a in current_assignments[:5]])
        if current_assignments
        else "not assigned"
    )

    prompt = f"""You are a semantic analyst resolving a conflict in primitive assignment.

WORD: "{conflict.word}"

PRIMITIVE: {conflict.primitive}
{prim_explanation}

CONFLICT:
- Current Wiktionary assignment: {conflict.primitive}={conflict.wikt_value}
  (Sources: {current_str})
- External database ({conflict.source}) says: {conflict.primitive}={conflict.source_value}
  ({source_desc})

TASK: Determine the correct value for {conflict.primitive} for the word "{conflict.word}".

Think step by step:
1. What does "{conflict.word}" mean?
2. Does it have positive or negative connotations for {conflict.primitive}?
3. Which source is more likely correct?

Answer with EXACTLY this format:
VALUE: [+1, -1, or 0]
CONFIDENCE: [high, medium, or low]
REASONING: [one sentence explanation]"""

    return prompt


def parse_resolution(response: str, conflict: Conflict) -> Optional[Resolution]:
    """Parse LLM response into a Resolution object."""
    try:
        # Extract VALUE - handle both "VALUE: -1" and "VALUE: [-1]"
        value_match = re.search(r"VALUE:\s*\[?([-+]?[01])\]?", response)
        if not value_match:
            logger.debug(f"No VALUE match in: {response[:100]}")
            return None
        new_value = int(value_match.group(1))

        # Extract CONFIDENCE - handle brackets
        conf_match = re.search(r"CONFIDENCE:\s*\[?(high|medium|low)\]?", response, re.I)
        confidence = conf_match.group(1).lower() if conf_match else "medium"

        # Extract REASONING - handle brackets and multiline
        reason_match = re.search(r"REASONING:\s*\[?([^\]\n]+)", response)
        reasoning = reason_match.group(1).strip() if reason_match else "No reasoning provided"

        return Resolution(
            word=conflict.word,
            primitive=conflict.primitive,
            old_value=conflict.wikt_value,
            new_value=new_value,
            confidence=confidence,
            reasoning=reasoning,
            source_agreement=[conflict.source] if new_value == conflict.source_value else [],
            model=DEFAULT_MODEL,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to parse resolution: {e}")
        return None


def apply_resolution(resolution: Resolution, conn: sqlite3.Connection, dry_run: bool = False):
    """Apply a resolution to the database."""
    if dry_run:
        logger.info(
            f"[DRY RUN] Would update {resolution.word}.{resolution.primitive}: "
            f"{resolution.old_value} → {resolution.new_value}"
        )
        return

    # Update existing entries
    conn.execute(
        """
        UPDATE word_primitives
        SET value = ?, confidence = ?, source = ?
        WHERE word = ? AND primitive = ?
    """,
        (
            resolution.new_value,
            0.85 if resolution.confidence == "high" else 0.7 if resolution.confidence == "medium" else 0.5,
            f"llm_correction:{DEFAULT_MODEL}",
            resolution.word,
            resolution.primitive,
        ),
    )

    # If no rows updated, insert new entry
    if conn.total_changes == 0:
        conn.execute(
            """
            INSERT INTO word_primitives (word, pos, primitive, value, confidence, source)
            VALUES (?, NULL, ?, ?, ?, ?)
        """,
            (
                resolution.word,
                resolution.primitive,
                resolution.new_value,
                0.85 if resolution.confidence == "high" else 0.7,
                f"llm_correction:{DEFAULT_MODEL}",
            ),
        )


def log_resolution(resolution: Resolution):
    """Log resolution to JSONL file for audit trail."""
    CORRECTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CORRECTIONS_LOG, "a") as f:
        f.write(
            json.dumps(
                {
                    "word": resolution.word,
                    "primitive": resolution.primitive,
                    "old_value": resolution.old_value,
                    "new_value": resolution.new_value,
                    "confidence": resolution.confidence,
                    "reasoning": resolution.reasoning,
                    "model": resolution.model,
                    "timestamp": resolution.timestamp,
                }
            )
            + "\n"
        )


class ConflictResolver:
    """Main class for resolving conflicts using LLM."""

    def __init__(self, model: str = DEFAULT_MODEL, dry_run: bool = False):
        self.model = model
        self.dry_run = dry_run
        self.conn = sqlite3.connect(str(WIKT_DB))
        self.stats = defaultdict(int)
        self.resolutions: List[Resolution] = []

    def resolve_conflicts(self, conflicts: List[Conflict], batch_size: int = 10, sleep_between: float = 0.5):
        """Resolve a list of conflicts using LLM."""
        logger.info(f"Resolving {len(conflicts)} conflicts using {self.model}...")

        for i, conflict in enumerate(conflicts):
            # Get word context
            context = get_word_context(conflict.word, self.conn)

            # Build prompt
            prompt = build_resolution_prompt(conflict, context)

            # Query LLM
            response = query_ollama(prompt, model=self.model)
            self.stats["queries"] += 1

            if response.startswith("ERROR"):
                logger.warning(f"LLM error for {conflict.word}: {response}")
                self.stats["errors"] += 1
                continue

            # Parse resolution
            resolution = parse_resolution(response, conflict)
            if not resolution:
                logger.warning(f"Failed to parse resolution for {conflict.word}")
                self.stats["parse_errors"] += 1
                continue

            # Only apply if value changed
            if resolution.new_value != conflict.wikt_value:
                apply_resolution(resolution, self.conn, self.dry_run)
                log_resolution(resolution)
                self.resolutions.append(resolution)
                self.stats["corrections"] += 1

                logger.info(
                    f"[{i + 1}/{len(conflicts)}] {conflict.word}.{conflict.primitive}: "
                    f"{conflict.wikt_value} → {resolution.new_value} "
                    f"({resolution.confidence})"
                )
            else:
                self.stats["no_change"] += 1
                logger.info(
                    f"[{i + 1}/{len(conflicts)}] {conflict.word}.{conflict.primitive}: keeping {conflict.wikt_value}"
                )

            # Progress logging
            if (i + 1) % batch_size == 0:
                self.conn.commit()
                logger.info(
                    f"Progress: {i + 1}/{len(conflicts)} | "
                    f"Corrections: {self.stats['corrections']} | "
                    f"No change: {self.stats['no_change']}"
                )

            time.sleep(sleep_between)

        # Final commit
        self.conn.commit()

    def get_summary(self) -> Dict:
        """Get summary statistics."""
        return {
            "total_queries": self.stats["queries"],
            "corrections_made": self.stats["corrections"],
            "no_change_needed": self.stats["no_change"],
            "errors": self.stats["errors"],
            "parse_errors": self.stats["parse_errors"],
            "resolutions": [
                {
                    "word": r.word,
                    "primitive": r.primitive,
                    "old": r.old_value,
                    "new": r.new_value,
                    "confidence": r.confidence,
                }
                for r in self.resolutions
            ],
        }

    def close(self):
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="LLM-Based Conflict Resolver")
    parser.add_argument("--primitive", type=str, help="Specific primitive to resolve (e.g., GOOD)")
    parser.add_argument("--all-primitives", action="store_true", help="Process all primitives in order")
    parser.add_argument("--limit", type=int, default=100, help="Max conflicts to process per primitive")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model to use")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually modify database")
    parser.add_argument("--batch-size", type=int, default=10, help="Commit frequency")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep between queries")

    args = parser.parse_args()

    # Determine which primitives to process
    if args.primitive:
        primitives = [args.primitive.upper()]
    elif args.all_primitives:
        primitives = PRIMITIVES_BY_CONFLICT
    else:
        primitives = [PRIMITIVES_BY_CONFLICT[0]]  # Default to GOOD

    print("=" * 60)
    print("LLM CONFLICT RESOLVER")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Primitives: {', '.join(primitives)}")
    print(f"Limit per primitive: {args.limit}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)

    resolver = ConflictResolver(model=args.model, dry_run=args.dry_run)

    try:
        for primitive in primitives:
            print(f"\n>>> Processing {primitive} conflicts...")

            # Load conflicts for this primitive
            conflicts = load_conflicts(primitive=primitive, limit=args.limit)

            if not conflicts:
                logger.info(f"No conflicts found for {primitive} in audit report")
                continue

            resolver.resolve_conflicts(conflicts, batch_size=args.batch_size, sleep_between=args.sleep)

            print(f"<<< {primitive} complete: {resolver.stats['corrections']} corrections")

        # Print summary
        summary = resolver.get_summary()
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total queries: {summary['total_queries']}")
        print(f"Corrections made: {summary['corrections_made']}")
        print(f"No change needed: {summary['no_change_needed']}")
        print(f"Errors: {summary['errors']}")

        if summary["resolutions"]:
            print("\nSample corrections:")
            for r in summary["resolutions"][:10]:
                print(f"  {r['word']}.{r['primitive']}: {r['old']} → {r['new']} ({r['confidence']})")

    finally:
        resolver.close()

    print(f"\nCorrections logged to: {CORRECTIONS_LOG}")


if __name__ == "__main__":
    main()
