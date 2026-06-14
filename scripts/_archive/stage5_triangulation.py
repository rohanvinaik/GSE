#!/usr/bin/env python3
"""
Stage 5: Deep Rule-Guided Audit (Triangulation)

Three parallel sources:
1. NLP databases (NRC-VAD, Lancaster sensorimotor, concreteness)
2. 3 small models (smollm, granite3-moe, gemma2)
3. Qwen 32B common-sense validation

Agreement filtering:
- All 3 agree → HIGH confidence
- 2/3 agree (no NLP coverage) → HIGH confidence
- Disagreement → MANUAL REVIEW queue
"""

import sqlite3
import csv
import json
import requests
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import logging

# Set up logging to both console and file for visibility
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add file handler for progress visibility
PROGRESS_LOG = Path("data/logs/stage5_progress.log")
PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(PROGRESS_LOG, mode='a')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

# Configuration
DB_PATH = Path("data/lexicon.db")
EXTERNAL_DATA = Path("data/external")
OUTPUT_DIR = Path("data/logs")

SMALL_MODELS = ["smollm:1.7b", "granite3-moe:1b", "gemma2:2b"]
LARGE_MODEL = "qwen3:32b"


# ============================================================================
# NLP Database Parsers
# ============================================================================

def load_nrc_vad() -> Dict[str, Dict[str, float]]:
    """Load NRC Valence-Arousal-Dominance lexicon."""
    vad = {}
    path = EXTERNAL_DATA / "nrc_vad.txt"
    if not path.exists():
        logger.warning(f"NRC-VAD not found at {path}")
        return vad

    with open(path, 'r') as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                word = parts[0].lower().strip()
                vad[word] = {
                    'valence': float(parts[1]),
                    'arousal': float(parts[2]),
                    'dominance': float(parts[3])
                }
    logger.info(f"Loaded {len(vad)} words from NRC-VAD")
    return vad


def load_concreteness() -> Dict[str, float]:
    """Load concreteness ratings (1-5 scale)."""
    conc = {}
    path = EXTERNAL_DATA / "concreteness.csv"
    if not path.exists():
        logger.warning(f"Concreteness data not found at {path}")
        return conc

    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['Word'].lower().strip()
            try:
                conc[word] = float(row['Conc.M'])
            except (ValueError, KeyError):
                continue
    logger.info(f"Loaded {len(conc)} words from concreteness data")
    return conc


def load_lancaster_sensorimotor() -> Dict[str, Dict[str, float]]:
    """Load Lancaster Sensorimotor norms."""
    sens = {}
    path = EXTERNAL_DATA / "lancaster_sensorimotor.csv"
    if not path.exists():
        logger.warning(f"Lancaster data not found at {path}")
        return sens

    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['Word'].lower().strip().strip('"')
            sens[word] = {
                'auditory': float(row.get('Auditory.mean', 0) or 0),
                'gustatory': float(row.get('Gustatory.mean', 0) or 0),
                'haptic': float(row.get('Haptic.mean', 0) or 0),
                'visual': float(row.get('Visual.mean', 0) or 0),
                'mouth': float(row.get('Mouth.mean', 0) or 0),
                'hand_arm': float(row.get('Hand_arm.mean', 0) or 0),
            }
    logger.info(f"Loaded {len(sens)} words from Lancaster sensorimotor")
    return sens


# ============================================================================
# NLP to GSE Primitive Mapping
# ============================================================================

@dataclass
class NLPSignals:
    """Signals derived from NLP databases."""
    word: str
    # From NRC-VAD
    valence: Optional[float] = None  # -1 to 1
    arousal: Optional[float] = None  # -1 to 1
    # From concreteness
    concreteness: Optional[float] = None  # 1-5
    # From Lancaster
    auditory: Optional[float] = None
    gustatory: Optional[float] = None
    haptic: Optional[float] = None
    visual: Optional[float] = None
    mouth: Optional[float] = None
    hand_arm: Optional[float] = None

    def suggests_feel(self) -> Optional[bool]:
        """Does NLP data suggest FEEL=1?"""
        if self.valence is not None:
            # High absolute valence suggests emotional content
            if abs(self.valence) > 0.3:
                return True
        return None

    def suggests_good(self) -> Optional[int]:
        """Does NLP data suggest GOOD=1 or BAD=1?"""
        if self.valence is not None:
            if self.valence > 0.3:
                return 1  # GOOD
            elif self.valence < -0.3:
                return -1  # BAD
        return None

    def suggests_body(self) -> Optional[bool]:
        """Does NLP data suggest BODY=1?"""
        if self.haptic is not None and self.hand_arm is not None:
            if self.haptic > 2.0 or self.hand_arm > 2.0:
                return True
        return None

    def suggests_see(self) -> Optional[bool]:
        """Does NLP data suggest SEE=1?"""
        if self.visual is not None:
            if self.visual > 3.0:
                return True
        return None

    def suggests_hear(self) -> Optional[bool]:
        """Does NLP data suggest HEAR=1?"""
        if self.auditory is not None:
            if self.auditory > 3.0:
                return True
        return None


def get_nlp_signals(word: str, vad: Dict, conc: Dict, sens: Dict) -> NLPSignals:
    """Get all NLP signals for a word."""
    signals = NLPSignals(word=word)

    word_lower = word.lower()

    if word_lower in vad:
        signals.valence = vad[word_lower]['valence']
        signals.arousal = vad[word_lower]['arousal']

    if word_lower in conc:
        signals.concreteness = conc[word_lower]

    if word_lower in sens:
        s = sens[word_lower]
        signals.auditory = s.get('auditory')
        signals.gustatory = s.get('gustatory')
        signals.haptic = s.get('haptic')
        signals.visual = s.get('visual')
        signals.mouth = s.get('mouth')
        signals.hand_arm = s.get('hand_arm')

    return signals


# ============================================================================
# Model Queries
# ============================================================================

def query_model(model: str, prompt: str, timeout: int = 30) -> str:
    """Query a local Ollama model."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 30}
            },
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return f"ERROR:{response.status_code}"
    except Exception as e:
        return f"ERROR:{e}"


def parse_yes_no(response: str) -> Optional[bool]:
    """Parse YES/NO response."""
    response = response.upper()[:50]
    if "YES" in response:
        return True
    if "NO" in response:
        return False
    return None


def query_3_models(word: str, primitive: str, current_value: int) -> Dict[str, Optional[bool]]:
    """Query 3 small models about a primitive assignment."""
    prompt = f"""Word: "{word}"
Current: {primitive}={current_value}

Is {primitive}={current_value} correct for "{word}"?
Answer only: YES or NO"""

    results = {}
    for model in SMALL_MODELS:
        response = query_model(model, prompt)
        results[model] = parse_yes_no(response)

    return results


def query_qwen(word: str, primitives: Dict[str, int], check_description: str) -> Optional[bool]:
    """Query Qwen 32B for common-sense validation."""
    active = [f"{k}={v}" for k, v in primitives.items() if v != 0][:8]
    active_str = ", ".join(active) if active else "none"

    prompt = f"""/no_think
Word: "{word}"
Primitives: {active_str}

{check_description}

Answer only: YES or NO"""

    response = query_model(LARGE_MODEL, prompt, timeout=60)
    return parse_yes_no(response)


# ============================================================================
# Triangulation Logic
# ============================================================================

@dataclass
class TriangulationResult:
    word: str
    primitive: str
    current_value: int
    nlp_signal: Optional[bool] = None  # What NLP suggests
    model_votes: Dict[str, Optional[bool]] = field(default_factory=dict)
    qwen_vote: Optional[bool] = None
    agreement: str = "unknown"  # "high", "medium", "disagree", "no_coverage"
    recommendation: str = "keep"  # "keep", "change", "review"

    def compute_agreement(self):
        """Compute agreement level from all sources."""
        votes = []

        if self.nlp_signal is not None:
            votes.append(("nlp", self.nlp_signal))

        model_yes = sum(1 for v in self.model_votes.values() if v is True)
        model_no = sum(1 for v in self.model_votes.values() if v is False)

        if model_yes >= 2:
            votes.append(("models", True))
        elif model_no >= 2:
            votes.append(("models", False))

        if self.qwen_vote is not None:
            votes.append(("qwen", self.qwen_vote))

        if len(votes) == 0:
            self.agreement = "no_coverage"
            self.recommendation = "review"
        elif all(v[1] == votes[0][1] for v in votes):
            self.agreement = "high"
            self.recommendation = "keep" if votes[0][1] else "change"
        elif len(votes) >= 2 and sum(1 for v in votes if v[1]) >= 2:
            self.agreement = "medium"
            self.recommendation = "keep"
        elif len(votes) >= 2 and sum(1 for v in votes if not v[1]) >= 2:
            self.agreement = "medium"
            self.recommendation = "change"
        else:
            self.agreement = "disagree"
            self.recommendation = "review"


# ============================================================================
# Main Audit
# ============================================================================

def get_words_for_audit(db_path: Path, limit: int = 100) -> List[Tuple[str, Dict[str, int]]]:
    """Get words with their primitive values for auditing."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get a sample of words with active primitives
    cur.execute("""
        SELECT l.lemma, GROUP_CONCAT(pv.primitive || ':' || pv.value)
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE pv.value != 0
        GROUP BY l.id
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))

    words = []
    for lemma, prim_str in cur.fetchall():
        primitives = {}
        for pair in prim_str.split(','):
            if ':' in pair:
                k, v = pair.split(':')
                primitives[k] = int(v)
        words.append((lemma, primitives))

    conn.close()
    return words


def run_triangulation_audit(
    db_path: Path,
    sample_size: int = 50,
    focus_primitives: List[str] = None
) -> List[TriangulationResult]:
    """Run the full triangulation audit."""

    if focus_primitives is None:
        focus_primitives = ["FEEL", "GOOD", "BAD", "BODY", "SEE", "HEAR"]

    # Load NLP databases
    logger.info("Loading NLP databases...")
    vad = load_nrc_vad()
    conc = load_concreteness()
    sens = load_lancaster_sensorimotor()

    # Get words to audit
    logger.info(f"Getting {sample_size} words for audit...")
    words = get_words_for_audit(db_path, sample_size)

    results = []

    for i, (word, primitives) in enumerate(words):
        logger.info(f"[{i+1}/{len(words)}] Auditing: {word}")

        # Get NLP signals
        nlp = get_nlp_signals(word, vad, conc, sens)

        for prim in focus_primitives:
            current = primitives.get(prim, 0)
            if current == 0:
                continue  # Skip inactive primitives

            result = TriangulationResult(word=word, primitive=prim, current_value=current)

            # NLP signal
            if prim == "FEEL":
                result.nlp_signal = nlp.suggests_feel()
            elif prim == "GOOD":
                sugg = nlp.suggests_good()
                result.nlp_signal = (sugg == 1) if sugg is not None else None
            elif prim == "BAD":
                sugg = nlp.suggests_good()
                result.nlp_signal = (sugg == -1) if sugg is not None else None
            elif prim == "BODY":
                result.nlp_signal = nlp.suggests_body()
            elif prim == "SEE":
                result.nlp_signal = nlp.suggests_see()
            elif prim == "HEAR":
                result.nlp_signal = nlp.suggests_hear()

            # 3-model votes
            result.model_votes = query_3_models(word, prim, current)

            # Qwen vote (only if models disagree or NLP conflicts)
            model_agree = all(v is True for v in result.model_votes.values() if v is not None)
            if not model_agree or (result.nlp_signal is not None and result.nlp_signal != model_agree):
                desc = f"Does the word '{word}' have the property {prim}?"
                result.qwen_vote = query_qwen(word, primitives, desc)

            result.compute_agreement()
            results.append(result)

    return results


def write_report(results: List[TriangulationResult], output_path: Path):
    """Write triangulation report."""

    # Categorize results
    high_conf = [r for r in results if r.agreement == "high"]
    medium_conf = [r for r in results if r.agreement == "medium"]
    disagree = [r for r in results if r.agreement == "disagree"]
    no_coverage = [r for r in results if r.agreement == "no_coverage"]

    needs_change = [r for r in results if r.recommendation == "change"]
    needs_review = [r for r in results if r.recommendation == "review"]

    with open(output_path, 'w') as f:
        f.write("# Stage 5: Triangulation Audit Report\n\n")
        f.write(f"Total checks: {len(results)}\n\n")

        f.write("## Agreement Summary\n\n")
        f.write(f"| Level | Count | Percentage |\n")
        f.write(f"|-------|-------|------------|\n")
        f.write(f"| High confidence | {len(high_conf)} | {100*len(high_conf)/len(results):.1f}% |\n")
        f.write(f"| Medium confidence | {len(medium_conf)} | {100*len(medium_conf)/len(results):.1f}% |\n")
        f.write(f"| Disagreement | {len(disagree)} | {100*len(disagree)/len(results):.1f}% |\n")
        f.write(f"| No coverage | {len(no_coverage)} | {100*len(no_coverage)/len(results):.1f}% |\n\n")

        f.write("## Recommendations\n\n")
        f.write(f"- Keep as-is: {len(results) - len(needs_change) - len(needs_review)}\n")
        f.write(f"- Needs change: {len(needs_change)}\n")
        f.write(f"- Needs review: {len(needs_review)}\n\n")

        if needs_change:
            f.write("## Words Needing Change\n\n")
            f.write("| Word | Primitive | Current | NLP | Models | Qwen |\n")
            f.write("|------|-----------|---------|-----|--------|------|\n")
            for r in needs_change:
                model_str = "/".join(str(v)[:1] if v is not None else "?" for v in r.model_votes.values())
                nlp_str = "Y" if r.nlp_signal else ("N" if r.nlp_signal is False else "-")
                qwen_str = "Y" if r.qwen_vote else ("N" if r.qwen_vote is False else "-")
                f.write(f"| {r.word} | {r.primitive} | {r.current_value} | {nlp_str} | {model_str} | {qwen_str} |\n")

        if needs_review:
            f.write("\n## Words Needing Manual Review\n\n")
            f.write("| Word | Primitive | Current | NLP | Models | Qwen |\n")
            f.write("|------|-----------|---------|-----|--------|------|\n")
            for r in needs_review[:30]:  # Limit to first 30
                model_str = "/".join(str(v)[:1] if v is not None else "?" for v in r.model_votes.values())
                nlp_str = "Y" if r.nlp_signal else ("N" if r.nlp_signal is False else "-")
                qwen_str = "Y" if r.qwen_vote else ("N" if r.qwen_vote is False else "-")
                f.write(f"| {r.word} | {r.primitive} | {r.current_value} | {nlp_str} | {model_str} | {qwen_str} |\n")

    logger.info(f"Report written to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5 Triangulation Audit")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--sample", type=int, default=50, help="Sample size")
    parser.add_argument("--output", default="data/stage5_triangulation_report.md", help="Output report path")
    args = parser.parse_args()

    results = run_triangulation_audit(Path(args.db), args.sample)
    write_report(results, Path(args.output))

    # Print summary
    print(f"\n{'='*50}")
    print("STAGE 5 TRIANGULATION COMPLETE")
    print(f"{'='*50}")
    print(f"Total checks: {len(results)}")
    print(f"High confidence: {sum(1 for r in results if r.agreement == 'high')}")
    print(f"Needs change: {sum(1 for r in results if r.recommendation == 'change')}")
    print(f"Needs review: {sum(1 for r in results if r.recommendation == 'review')}")
