#!/usr/bin/env python3
"""
Multi-Model Semantic Audit (V5 - Continuous)

Long-running CONTINUOUS background audit using 3 small local models for
consensus-based error detection. AUDIT ONLY - generates report, no database modifications.

Models used (small, fast for continuous background processing):
- smollm:1.7b (very fast, efficient)
- granite3-moe:1b (IBM's mixture-of-experts, tiny)
- gemma2:2b (Google's efficient model)

Agreement Protocol:
- 3/3 agree → HIGH priority (unanimous - fix this)
- 2/3 agree → MEDIUM priority (likely issue)
- 1/3 or split → NEEDS_ANALYSIS (deeper semantic review needed)

Usage:
    python scripts/multi_model_audit.py --db data/lexicon.db --output data/multi_model_audit

    # Run in background (CONTINUOUS mode):
    nohup python scripts/multi_model_audit.py --continuous > /tmp/audit_v5.log 2>&1 &
"""

import argparse
import json
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

MODELS = ["smollm:1.7b", "granite3-moe:1b", "gemma2:2b"]

# Semantic primitive categories for focused checks
EXPERIENCER_PRIMITIVES = {"FEEL", "THINK", "KNOW", "WANT", "SEE", "HEAR"}
AGENT_PRIMITIVES = {"DO", "SAY", "MOVE", "MAKE"}
BIPOLAR_PAIRS = [
    ("GOOD", "BAD"), ("BIG", "SMALL"), ("ALIVE", "DEAD"),
    ("BEFORE", "AFTER"), ("INSIDE", "OUTSIDE"), ("WITH", "WITHOUT"),
    ("TRUE", "FALSE"), ("FAR", "NEAR"), ("SAME", "OTHER"),
]

# Function words that should have minimal primitives
FUNCTION_WORDS = {
    'the', 'of', 'and', 'to', 'a', 'in', 'is', 'that', 'for', 'it',
    'with', 'as', 'on', 'at', 'by', 'from', 'or', 'an', 'be', 'this',
    'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'not',
    'but', 'if', 'which', 'their', 'so', 'what', 'when', 'into', 'than',
    'its', 'any', 'no', 'do', 'how', 'up', 'out', 'just', 'about'
}

# Modifier hierarchy - now loaded from external ground truth
# Fallback dictionary for when ground truth isn't available
MODIFIER_HIERARCHY_FALLBACK = {
    "barely": ("INTENSITY", -2), "hardly": ("INTENSITY", -2),
    "slightly": ("INTENSITY", -1), "somewhat": ("INTENSITY", -1),
    "fairly": ("INTENSITY", 0), "rather": ("INTENSITY", 0),
    "quite": ("INTENSITY", 1), "very": ("INTENSITY", 1), "highly": ("INTENSITY", 1),
    "extremely": ("INTENSITY", 2), "incredibly": ("INTENSITY", 2),
    "none": ("QUANTITY", -3), "few": ("QUANTITY", -2), "some": ("QUANTITY", -1),
    "several": ("QUANTITY", 0), "more": ("QUANTITY", 1), "many": ("QUANTITY", 2),
    "all": ("QUANTITY", 3), "impossible": ("CERTAINTY", -3),
    "unlikely": ("CERTAINTY", -2), "possible": ("CERTAINTY", 0),
    "likely": ("CERTAINTY", 2), "certain": ("CERTAINTY", 3),
}

# Try to load external ground truth
try:
    from scripts.load_intensity_ground_truth import get_modifier_ground_truth
    _GROUND_TRUTH = get_modifier_ground_truth()
    MODIFIER_HIERARCHY = {
        word: (entry.hierarchy_type, entry.level)
        for word, entry in _GROUND_TRUTH.modifiers.items()
    }
    logger.info(f"Loaded {len(MODIFIER_HIERARCHY)} modifiers from external ground truth")
except ImportError:
    MODIFIER_HIERARCHY = MODIFIER_HIERARCHY_FALLBACK
    logger.warning("Using fallback modifier hierarchy (external ground truth not available)")


# ============================================================================
# Ollama Client (Minimal)
# ============================================================================

import requests


def query_model(model: str, prompt: str, timeout: int = 60) -> str:
    """Query a local Ollama model."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 50}
            },
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return f"ERROR:{response.status_code}"
    except Exception as e:
        return f"ERROR:{e}"


# ============================================================================
# Audit Checks
# ============================================================================

@dataclass
class AuditIssue:
    word: str
    check_type: str
    description: str
    current_value: str
    model_votes: Dict[str, str] = field(default_factory=dict)
    agreement_level: str = "unknown"  # "unanimous", "majority", "split"
    priority: str = "low"  # "high", "medium", "low", "review"


def get_concise_prompt(word: str, primitives: Dict[str, int], check_type: str) -> str:
    """Generate a concise prompt for semantic validation."""

    active = [f"{k}={v}" for k, v in primitives.items() if v != 0]
    active_str = ", ".join(active[:10]) if active else "none"

    if check_type == "experiencer":
        return f"""Word: "{word}"
Active primitives: {active_str}

This word has FEEL=1 (subjective experience). Does "{word}" require a conscious experiencer (human/animal)?
Answer only: YES or NO"""

    elif check_type == "function_word":
        return f"""Word: "{word}"
Active primitives: {active_str}

"{word}" is a function/grammatical word. Should it have semantic content primitives?
Answer only: YES or NO"""

    elif check_type == "agent":
        return f"""Word: "{word}"
Active primitives: {active_str}

This word has DO=1 or SAY=1 (action). Does "{word}" require an agent who performs it?
Answer only: YES or NO"""

    elif check_type == "alive":
        return f"""Word: "{word}"
Active primitives: {active_str}

This word has ALIVE=1. Is "{word}" a living thing or does it involve being alive?
Answer only: YES or NO"""

    elif check_type == "body":
        return f"""Word: "{word}"
Active primitives: {active_str}

This word has BODY=1. Does "{word}" involve physical body or bodily action?
Answer only: YES or NO"""

    elif check_type == "say_words":
        return f"""Word: "{word}"
Active primitives: {active_str}

This word has SAY=1 (communication). Does "{word}" involve using words/language to communicate?
Answer only: YES or NO"""

    elif check_type == "general":
        return f"""Word: "{word}"
Active primitives: {active_str}

Are these semantic primitives reasonable for the word "{word}"?
Answer only: YES, NO, or PARTIAL"""

    elif check_type == "modifier_hierarchy":
        return f"""Word: "{word}"
Current encoding: {active_str}

This word is an intensity/quantity/certainty modifier.
GSE uses hierarchical stacking: base primitive + HIER_PLUS/HIER_MINUS markers.

Example correct encodings:
- "very" = INTENSITY=1, HIER_PLUS=1 (one step above neutral)
- "extremely" = INTENSITY=1, HIER_PLUS=2 (two steps above)
- "barely" = INTENSITY=1, HIER_MINUS=2 (two steps below)
- "many" = QUANTITY=1, HIER_PLUS=2

Is the current encoding correct for "{word}"?
Answer only: YES or NO"""

    return f"Check: {word}"


def parse_response(response: str) -> str:
    """Parse model response to YES/NO/PARTIAL/ERROR."""
    response = response.upper().strip()
    if response.startswith("ERROR"):
        return "ERROR"
    if "YES" in response[:20]:
        return "YES"
    if "NO" in response[:20]:
        return "NO"
    if "PARTIAL" in response[:30]:
        return "PARTIAL"
    return "UNCLEAR"


def compute_agreement(votes: Dict[str, str]) -> Tuple[str, str]:
    """Compute agreement level and priority from model votes."""
    valid_votes = [v for v in votes.values() if v not in ("ERROR", "UNCLEAR")]

    if len(valid_votes) < 2:
        return "insufficient", "review"

    yes_count = sum(1 for v in valid_votes if v == "YES")
    no_count = sum(1 for v in valid_votes if v == "NO")

    if yes_count == len(valid_votes):
        return "unanimous_yes", "low"  # All agree it's correct
    elif no_count == len(valid_votes):
        return "unanimous_no", "high"  # All agree it's wrong
    elif no_count >= 2:
        return "majority_no", "medium"  # Majority says wrong
    elif yes_count >= 2:
        return "majority_yes", "low"  # Majority says correct
    else:
        return "split", "review"  # Disagreement - needs human review


# ============================================================================
# Main Audit Logic
# ============================================================================

class MultiModelAuditor:
    def __init__(self, db_path: str, models: List[str] = MODELS):
        self.db_path = db_path
        self.models = models
        self.conn = sqlite3.connect(db_path)
        self.issues: List[AuditIssue] = []
        self.stats = defaultdict(int)

    def get_word_primitives(self, lexeme_id: int) -> Dict[str, int]:
        """Get all primitives for a word."""
        cursor = self.conn.execute("""
            SELECT primitive, value FROM primitive_values
            WHERE lexeme_id = ?
        """, (lexeme_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}

    def audit_word(self, lexeme_id: int, lemma: str, pos: str, primitives: Dict[str, int]) -> List[AuditIssue]:
        """Run all applicable checks on a word."""
        issues = []
        active = {k: v for k, v in primitives.items() if v != 0}

        # Check 1: Function words with too many primitives
        if lemma.lower() in FUNCTION_WORDS and len(active) > 3:
            issue = self._check_with_models(
                lemma, primitives, "function_word",
                f"Function word with {len(active)} active primitives"
            )
            if issue:
                issues.append(issue)

        # Check 2: FEEL without experiencer
        if primitives.get("FEEL") == 1:
            has_experiencer = (
                primitives.get("SOMEONE") == 1 or
                primitives.get("I") == 1 or
                primitives.get("YOU") == 1
            )
            if not has_experiencer:
                issue = self._check_with_models(
                    lemma, primitives, "experiencer",
                    "FEEL=1 without SOMEONE/I/YOU"
                )
                if issue:
                    issues.append(issue)

        # Check 3: DO/SAY without agent
        if primitives.get("DO") == 1 or primitives.get("SAY") == 1:
            has_agent = primitives.get("SOMEONE") == 1
            if not has_agent:
                issue = self._check_with_models(
                    lemma, primitives, "agent",
                    "DO/SAY=1 without SOMEONE"
                )
                if issue:
                    issues.append(issue)

        # Check 4: ALIVE on non-living things
        if primitives.get("ALIVE") == 1:
            issue = self._check_with_models(
                lemma, primitives, "alive",
                "Has ALIVE=1"
            )
            if issue:
                issues.append(issue)

        # Check 5: Excessive primitives (>25)
        if len(active) > 25:
            issue = self._check_with_models(
                lemma, primitives, "general",
                f"Excessive primitives: {len(active)}"
            )
            if issue:
                issues.append(issue)

        # Check 6: BODY on abstract words (sample check)
        if primitives.get("BODY") == 1 and primitives.get("THINK") == 1:
            issue = self._check_with_models(
                lemma, primitives, "body",
                "Has both BODY=1 and THINK=1"
            )
            if issue:
                issues.append(issue)

        # Check 7: SAY without WORDS
        if primitives.get("SAY") == 1 and primitives.get("WORDS") != 1:
            issue = self._check_with_models(
                lemma, primitives, "say_words",
                "SAY=1 without WORDS=1"
            )
            if issue:
                issues.append(issue)

        # Check 8: Modifier hierarchy encoding
        if lemma.lower() in MODIFIER_HIERARCHY:
            hierarchy_issues = self._check_modifier_hierarchy(lemma, primitives)
            issues.extend(hierarchy_issues)

        return issues

    def _check_modifier_hierarchy(
        self,
        lemma: str,
        primitives: Dict[str, int]
    ) -> List[AuditIssue]:
        """
        Validate modifier hierarchy encoding.

        GSE uses balanced ternary stacking:
        - Base primitive (INTENSITY/QUANTITY/CERTAINTY) always +1
        - Direction via HIER_PLUS or HIER_MINUS markers
        - Level = count of markers
        """
        issues = []
        lemma_lower = lemma.lower()

        if lemma_lower not in MODIFIER_HIERARCHY:
            return issues

        base_type, expected_level = MODIFIER_HIERARCHY[lemma_lower]

        # Get current values
        base_value = primitives.get(base_type, 0)
        hier_plus = primitives.get("HIER_PLUS", 0)
        hier_minus = primitives.get("HIER_MINUS", 0)

        # Check 1: Base primitive should be +1
        if base_value != 1:
            issues.append(AuditIssue(
                word=lemma,
                check_type="modifier_base",
                description=f"{base_type} should be +1, got {base_value}",
                current_value=f"{base_type}={base_value}",
                model_votes={"deterministic": "FAIL"},
                agreement_level="deterministic",
                priority="high"
            ))

        # Check 2: HIER markers match expected level
        if expected_level > 0:
            # Should have HIER_PLUS = level, HIER_MINUS = 0
            if hier_plus != expected_level:
                issues.append(AuditIssue(
                    word=lemma,
                    check_type="modifier_hier_plus",
                    description=f"HIER_PLUS should be {expected_level}, got {hier_plus}",
                    current_value=f"HIER_PLUS={hier_plus}",
                    model_votes={"deterministic": "FAIL"},
                    agreement_level="deterministic",
                    priority="high" if abs(hier_plus - expected_level) > 1 else "medium"
                ))
            if hier_minus != 0:
                issues.append(AuditIssue(
                    word=lemma,
                    check_type="modifier_hier_minus",
                    description=f"HIER_MINUS should be 0 for positive level, got {hier_minus}",
                    current_value=f"HIER_MINUS={hier_minus}",
                    model_votes={"deterministic": "FAIL"},
                    agreement_level="deterministic",
                    priority="medium"
                ))
        elif expected_level < 0:
            # Should have HIER_MINUS = abs(level), HIER_PLUS = 0
            expected_minus = abs(expected_level)
            if hier_minus != expected_minus:
                issues.append(AuditIssue(
                    word=lemma,
                    check_type="modifier_hier_minus",
                    description=f"HIER_MINUS should be {expected_minus}, got {hier_minus}",
                    current_value=f"HIER_MINUS={hier_minus}",
                    model_votes={"deterministic": "FAIL"},
                    agreement_level="deterministic",
                    priority="high" if abs(hier_minus - expected_minus) > 1 else "medium"
                ))
            if hier_plus != 0:
                issues.append(AuditIssue(
                    word=lemma,
                    check_type="modifier_hier_plus",
                    description=f"HIER_PLUS should be 0 for negative level, got {hier_plus}",
                    current_value=f"HIER_PLUS={hier_plus}",
                    model_votes={"deterministic": "FAIL"},
                    agreement_level="deterministic",
                    priority="medium"
                ))
        else:  # expected_level == 0
            # Should have no HIER markers
            if hier_plus != 0 or hier_minus != 0:
                issues.append(AuditIssue(
                    word=lemma,
                    check_type="modifier_hier_neutral",
                    description=f"Level 0 needs no HIER markers, got HIER_PLUS={hier_plus}, HIER_MINUS={hier_minus}",
                    current_value=f"HIER_PLUS={hier_plus}, HIER_MINUS={hier_minus}",
                    model_votes={"deterministic": "FAIL"},
                    agreement_level="deterministic",
                    priority="medium"
                ))

        return issues

    def _check_with_models(
        self,
        word: str,
        primitives: Dict[str, int],
        check_type: str,
        description: str
    ) -> Optional[AuditIssue]:
        """Query all models and compute consensus."""
        prompt = get_concise_prompt(word, primitives, check_type)
        votes = {}

        for model in self.models:
            response = query_model(model, prompt)
            votes[model] = parse_response(response)
            self.stats[f"queries_{model}"] += 1
            time.sleep(0.1)  # Small delay between models

        agreement, priority = compute_agreement(votes)

        # Only create issue if not unanimous YES (i.e., something might be wrong)
        if agreement != "unanimous_yes" and agreement != "majority_yes":
            active = {k: v for k, v in primitives.items() if v != 0}
            return AuditIssue(
                word=word,
                check_type=check_type,
                description=description,
                current_value=str(dict(list(active.items())[:5])),
                model_votes=votes,
                agreement_level=agreement,
                priority=priority
            )

        return None

    def run_audit(self, limit: int = None, start_rank: int = 1) -> List[AuditIssue]:
        """Run full audit on lexicon."""
        cursor = self.conn.execute("""
            SELECT l.id, l.lemma, l.pos, l.frequency_rank
            FROM lexemes l
            WHERE l.frequency_rank >= ?
            ORDER BY l.frequency_rank
        """, (start_rank,))

        words = cursor.fetchall()
        if limit:
            words = words[:limit]

        logger.info(f"Starting multi-model audit of {len(words)} words...")
        logger.info(f"Models: {', '.join(self.models)}")

        start_time = time.time()

        for i, (lex_id, lemma, pos, rank) in enumerate(words):
            primitives = self.get_word_primitives(lex_id)
            word_issues = self.audit_word(lex_id, lemma, pos, primitives)
            self.issues.extend(word_issues)

            self.stats["words_processed"] += 1
            self.stats["issues_found"] += len(word_issues)

            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                high_priority = sum(1 for iss in self.issues if iss.priority == "high")
                logger.info(
                    f"Progress: {i + 1}/{len(words)} ({rate:.2f}/sec) | "
                    f"Issues: {len(self.issues)} (high: {high_priority})"
                )

        logger.info(f"Audit complete. Total issues: {len(self.issues)}")
        return self.issues

    def generate_report(self, output_path: str):
        """Generate markdown report."""
        high = [i for i in self.issues if i.priority == "high"]
        medium = [i for i in self.issues if i.priority == "medium"]
        review = [i for i in self.issues if i.priority == "review"]
        low = [i for i in self.issues if i.priority == "low"]

        report = f"""# Multi-Model Semantic Audit Report (V4)

Generated: {datetime.now().isoformat()}
Models: {', '.join(self.models)}

## Summary

| Metric | Value |
|--------|-------|
| Words audited | {self.stats['words_processed']} |
| Total issues | {len(self.issues)} |
| **HIGH priority** (unanimous agreement - fix) | {len(high)} |
| **MEDIUM priority** (majority agreement) | {len(medium)} |
| **REVIEW** (model disagreement) | {len(review)} |
| Low priority | {len(low)} |

---

## HIGH Priority Issues (All Models Agree - FIX)

These issues have unanimous model agreement that something is wrong.

| Word | Check Type | Description | Model Votes |
|------|------------|-------------|-------------|
"""
        for issue in high[:200]:
            votes_str = ", ".join(f"{m.split(':')[0]}={v}" for m, v in issue.model_votes.items())
            report += f"| {issue.word} | {issue.check_type} | {issue.description} | {votes_str} |\n"

        if len(high) > 200:
            report += f"\n*... and {len(high) - 200} more high priority issues*\n"

        report += """
---

## MEDIUM Priority Issues (Majority Agreement)

| Word | Check Type | Description | Model Votes |
|------|------------|-------------|-------------|
"""
        for issue in medium[:200]:
            votes_str = ", ".join(f"{m.split(':')[0]}={v}" for m, v in issue.model_votes.items())
            report += f"| {issue.word} | {issue.check_type} | {issue.description} | {votes_str} |\n"

        if len(medium) > 200:
            report += f"\n*... and {len(medium) - 200} more medium priority issues*\n"

        report += """
---

## REVIEW Required (Model Disagreement)

These words have split opinions - need deeper semantic analysis.

| Word | Check Type | Description | Model Votes |
|------|------------|-------------|-------------|
"""
        for issue in review[:200]:
            votes_str = ", ".join(f"{m.split(':')[0]}={v}" for m, v in issue.model_votes.items())
            report += f"| {issue.word} | {issue.check_type} | {issue.description} | {votes_str} |\n"

        if len(review) > 200:
            report += f"\n*... and {len(review) - 200} more items needing review*\n"

        report += """
---

## Statistics by Check Type

| Check Type | Total | High | Medium | Review |
|------------|-------|------|--------|--------|
"""
        check_types = defaultdict(lambda: {"total": 0, "high": 0, "medium": 0, "review": 0})
        for issue in self.issues:
            check_types[issue.check_type]["total"] += 1
            check_types[issue.check_type][issue.priority] += 1

        for ct, counts in sorted(check_types.items()):
            report += f"| {ct} | {counts['total']} | {counts['high']} | {counts['medium']} | {counts['review']} |\n"

        report += """
---

## Model Agreement Analysis

| Agreement Type | Count | % |
|----------------|-------|---|
"""
        agreement_counts = defaultdict(int)
        for issue in self.issues:
            agreement_counts[issue.agreement_level] += 1

        for level, count in sorted(agreement_counts.items()):
            pct = (count / len(self.issues) * 100) if self.issues else 0
            report += f"| {level} | {count} | {pct:.1f}% |\n"

        report += f"""
---

## Raw Issues (JSON)

<details>
<summary>Click to expand full issue list</summary>

```json
{json.dumps([{
    'word': i.word,
    'check_type': i.check_type,
    'description': i.description,
    'votes': i.model_votes,
    'agreement': i.agreement_level,
    'priority': i.priority
} for i in self.issues], indent=2)}
```

</details>
"""

        with open(output_path, 'w') as f:
            f.write(report)

        logger.info(f"Report saved to {output_path}")

    def close(self):
        self.conn.close()


# ============================================================================
# Continuous Mode
# ============================================================================

def run_continuous_audit(
    db_path: str,
    output_dir: str,
    models: List[str],
    batch_size: int = 50,
    sleep_between_passes: int = 300
):
    """
    Run audit continuously in background.
    Loops forever, processing all words then waiting before next pass.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    log_file = os.path.join(output_dir, "audit_log.jsonl")
    pass_count = 0

    print("="*60)
    print("MULTI-MODEL CONTINUOUS AUDIT")
    print("="*60)
    print(f"Models: {', '.join(models)}")
    print(f"Database: {db_path}")
    print(f"Output: {output_dir}")
    print(f"Batch size: {batch_size}")
    print(f"Sleep between passes: {sleep_between_passes}s")
    print()
    print("Running continuously. Press Ctrl+C to stop.")
    print("="*60)

    try:
        while True:
            pass_count += 1
            pass_start = datetime.now()
            logger.info(f"\n=== STARTING PASS {pass_count} at {pass_start.isoformat()} ===")

            auditor = MultiModelAuditor(db_path=db_path, models=models)

            try:
                auditor.run_audit(limit=None, start_rank=1)

                # Save pass report
                report_path = os.path.join(output_dir, f"pass_{pass_count:04d}.md")
                auditor.generate_report(report_path)

                # Append issues to log
                with open(log_file, "a") as f:
                    for issue in auditor.issues:
                        entry = {
                            "pass": pass_count,
                            "timestamp": datetime.now().isoformat(),
                            "word": issue.word,
                            "check_type": issue.check_type,
                            "description": issue.description,
                            "votes": issue.model_votes,
                            "agreement": issue.agreement_level,
                            "priority": issue.priority
                        }
                        f.write(json.dumps(entry) + "\n")

                pass_end = datetime.now()
                elapsed = (pass_end - pass_start).total_seconds()
                high = sum(1 for i in auditor.issues if i.priority == "high")

                logger.info(f"Pass {pass_count} complete in {elapsed:.1f}s")
                logger.info(f"  Issues: {len(auditor.issues)} (HIGH: {high})")
                logger.info(f"  Report: {report_path}")

            finally:
                auditor.close()

            logger.info(f"Sleeping {sleep_between_passes}s before next pass...")
            time.sleep(sleep_between_passes)

    except KeyboardInterrupt:
        logger.info("\nInterrupted. Shutting down gracefully.")
        print(f"\n\nCompleted {pass_count} passes.")
        print(f"Logs: {log_file}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multi-Model Semantic Audit")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--output", default="data/multi_model_audit", help="Output directory/file")
    parser.add_argument("--limit", type=int, help="Limit words to audit")
    parser.add_argument("--start-rank", type=int, default=1, help="Start from frequency rank")
    parser.add_argument("--models", nargs="+", default=MODELS, help="Models to use")
    parser.add_argument("--continuous", action="store_true", help="Run in continuous loop mode")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for continuous mode")
    parser.add_argument("--sleep", type=int, default=300, help="Seconds between passes (continuous mode)")

    args = parser.parse_args()

    if args.continuous:
        run_continuous_audit(
            db_path=args.db,
            output_dir=args.output,
            models=args.models,
            batch_size=args.batch_size,
            sleep_between_passes=args.sleep
        )
    else:
        # Single pass mode
        auditor = MultiModelAuditor(db_path=args.db, models=args.models)

        try:
            auditor.run_audit(limit=args.limit, start_rank=args.start_rank)

            # Append .md if output doesn't have it
            output_path = args.output
            if not output_path.endswith('.md'):
                output_path = output_path + "_report.md"

            auditor.generate_report(output_path)

            print("\n" + "="*60)
            print("MULTI-MODEL AUDIT COMPLETE")
            print("="*60)
            print(f"Words audited: {auditor.stats['words_processed']}")
            print(f"Total issues: {len(auditor.issues)}")
            high = sum(1 for i in auditor.issues if i.priority == "high")
            print(f"HIGH priority: {high}")
            print(f"Report: {output_path}")

        finally:
            auditor.close()


if __name__ == "__main__":
    main()
