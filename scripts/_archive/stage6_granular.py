#!/usr/bin/env python3
"""
Stage 6: Granular Traversal Audit

Executors: smollm:1.7b, granite3-moe:1b, gemma2:2b
Focus: Deeper layers, less-common entries (frequency rank > 5000)
Mode: Slow, entry-by-entry common-sense validation

Runs indefinitely with file-based logging for monitoring.
"""

import sqlite3
import requests
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time

# Configuration
DB_PATH = Path("data/lexicon.db")
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

PROGRESS_LOG = LOG_DIR / "stage6_progress.log"
ISSUES_LOG = LOG_DIR / "stage6_issues.log"
FIXES_LOG = LOG_DIR / "stage6_fixes.log"

MODELS = ["smollm:1.7b", "granite3-moe:1b", "gemma2:2b"]
OLLAMA_URL = "http://localhost:11434/api/generate"

BATCH_SIZE = 20  # Smaller batches for more frequent logging


def log(msg: str, file: Path = PROGRESS_LOG):
    """Append timestamped message to log file and flush immediately."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    with open(file, 'a') as f:
        f.write(line)
        f.flush()
    print(line.strip())  # Also print to stdout
    sys.stdout.flush()


def get_words_for_audit(db_path: Path, offset: int = 0, limit: int = BATCH_SIZE,
                        min_rank: int = 5000, max_rank: int = 25000) -> List[Dict]:
    """Get words in frequency range for audit."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.id, l.lemma, l.pos, l.component_type,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.frequency_rank > ? AND l.frequency_rank <= ?
          AND l.component_type = 'ATOMIC'
        GROUP BY l.id
        ORDER BY l.frequency_rank
        LIMIT ? OFFSET ?
    """, (min_rank, max_rank, limit, offset))

    words = []
    for row in cursor.fetchall():
        words.append({
            'id': row[0],
            'lemma': row[1],
            'pos': row[2],
            'component_type': row[3],
            'primitives': row[4] or ''
        })

    conn.close()
    return words


def count_words_in_range(db_path: Path, min_rank: int = 5000, max_rank: int = 25000) -> int:
    """Count total words in frequency range."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM lexemes
        WHERE frequency_rank > ? AND frequency_rank <= ?
          AND component_type = 'ATOMIC'
    """, (min_rank, max_rank))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def build_audit_prompt(words: List[Dict]) -> str:
    """Build prompt for batch of words."""
    prompt = """For each word, does the encoding look correct? Reply YES or NO.

"""
    for w in words:
        prompt += f"{w['lemma']}: {w['primitives'] or 'NONE'}\n"

    prompt += """
Reply format (one per line):
word: YES
word: NO
"""
    return prompt


def query_model(model: str, prompt: str, timeout: int = 60) -> Optional[str]:
    """Query a single model via Ollama API."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            log(f"  ERROR: {model} returned status {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        log(f"  TIMEOUT: {model} exceeded {timeout}s")
        return None
    except Exception as e:
        log(f"  ERROR: {model} - {e}")
        return None


def parse_model_response(response: str) -> Dict[str, Dict]:
    """Parse model response into word -> issue mapping."""
    results = {}
    if not response:
        return results

    # First try to find patterns like "**word (pos):** ... **ISSUE:**" or "**word:** ... **OK:**"
    # Split by word headers
    word_sections = re.split(r'\*\*(\w+)\s*\([^)]+\):\s*', response)

    # Process sections (alternating: text, word, text, word, ...)
    for i in range(1, len(word_sections), 2):
        if i + 1 < len(word_sections):
            word = word_sections[i].lower()
            section = word_sections[i + 1]

            if re.search(r'\*\*ISSUE[:\*]', section, re.IGNORECASE) or 'ISSUE' in section.upper():
                results[word] = {'status': 'ISSUE', 'detail': section[:100]}
            elif re.search(r'\*\*OK[:\*]', section, re.IGNORECASE) or section.strip().startswith('OK'):
                results[word] = {'status': 'OK'}

    # Also try line-by-line parsing for simpler formats
    for line in response.strip().split('\n'):
        line = line.strip()
        if not line or ':' not in line:
            continue

        # Clean up numbered lists and backticks: "1. `word: OK`" -> "word: OK"
        line = re.sub(r'^\d+\.\s*', '', line)  # Remove "1. "
        line = re.sub(r'\*+', '', line)  # Remove asterisks
        line = line.strip('`* ')  # Remove backticks, spaces

        # Parse "word: YES/NO" or "word: OK/WRONG/ISSUE"
        match = re.match(r'^(\w+)(?:\s*\([^)]+\))?:\s*(YES|NO|OK|ISSUE.*|WRONG.*)$', line, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            status = match.group(2).strip().upper()

            if status in ('YES', 'OK'):
                results[word] = {'status': 'OK'}
            else:
                results[word] = {'status': 'ISSUE', 'detail': 'flagged'}

    return results


def run_batch_audit(words: List[Dict]) -> Dict[str, Dict]:
    """Run audit on batch using all 3 models."""
    prompt = build_audit_prompt(words)

    all_results = {}

    for model in MODELS:
        model_short = model.split(':')[0]
        log(f"    Querying {model}...")

        response = query_model(model, prompt)
        parsed = parse_model_response(response)

        # Debug: log parse results
        issues_found = sum(1 for r in parsed.values() if r.get('status') == 'ISSUE')
        oks_found = sum(1 for r in parsed.values() if r.get('status') == 'OK')
        log(f"      → Parsed: {issues_found} ISSUE, {oks_found} OK, {len(parsed)} total")

        for word, result in parsed.items():
            if word not in all_results:
                all_results[word] = {'models': {}}
            all_results[word]['models'][model_short] = result

    return all_results


def aggregate_issues(batch_results: Dict[str, Dict], words: List[Dict]) -> List[Dict]:
    """Aggregate model results and identify issues."""
    issues = []

    word_lookup = {w['lemma'].lower(): w for w in words}

    for word, data in batch_results.items():
        models = data.get('models', {})

        # Count issues
        issue_count = sum(1 for m in models.values() if m.get('status') == 'ISSUE')

        if issue_count >= 1:  # Log any issue
            # Priority based on agreement level
            if issue_count == 3:
                priority = 'HIGH'
            elif issue_count == 2:
                priority = 'MEDIUM'
            else:
                priority = 'LOW'

            # Get issue details
            issue_details = [
                f"{m}: {v.get('detail', 'ISSUE')}"
                for m, v in models.items()
                if v.get('status') == 'ISSUE'
            ]

            word_data = word_lookup.get(word, {})

            issues.append({
                'word': word,
                'lexeme_id': word_data.get('id'),
                'priority': priority,
                'agreement': f"{issue_count}/3",
                'details': issue_details,
                'current_primitives': word_data.get('primitives', '')
            })

    return issues


def apply_high_priority_fixes(issues: List[Dict], db_path: Path) -> int:
    """Apply fixes for high-priority issues (3/3 agreement)."""
    if not issues:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    fixed = 0

    for issue in issues:
        if issue['priority'] != 'HIGH':
            continue

        # Parse the issue detail to extract fix
        # Format: "ISSUE PRIMITIVE=current should be expected - reason"
        for detail in issue['details']:
            match = re.search(r'ISSUE\s+(\w+)=(\d+)\s+should be\s+(\d+)', detail)
            if match and issue['lexeme_id']:
                primitive = match.group(1)
                new_value = int(match.group(3))

                cursor.execute("""
                    UPDATE primitive_values
                    SET value = ?, source = 'fix:stage6'
                    WHERE lexeme_id = ? AND primitive = ?
                """, (new_value, issue['lexeme_id'], primitive))

                if cursor.rowcount > 0:
                    log(f"FIX: {issue['word']} {primitive}→{new_value}", FIXES_LOG)
                    fixed += 1
                break  # One fix per word

    conn.commit()
    conn.close()
    return fixed


def run_continuous_audit(db_path: Path, start_offset: int = 0,
                         min_rank: int = 5000, max_rank: int = 25000,
                         auto_fix: bool = False):
    """Run continuous audit with logging."""

    total_words = count_words_in_range(db_path, min_rank, max_rank)
    log(f"=== STAGE 6 GRANULAR AUDIT STARTED ===")
    log(f"Frequency range: {min_rank} - {max_rank}")
    log(f"Total words to audit: {total_words}")
    log(f"Batch size: {BATCH_SIZE}")
    log(f"Models: {', '.join(MODELS)}")
    log(f"Auto-fix: {auto_fix}")
    log(f"")

    offset = start_offset
    total_issues_found = 0
    total_high = 0
    total_medium = 0
    total_fixed = 0

    while True:
        words = get_words_for_audit(db_path, offset, BATCH_SIZE, min_rank, max_rank)

        if not words:
            log(f"=== AUDIT COMPLETE ===")
            log(f"Total words audited: {offset}")
            log(f"Total issues found: {total_issues_found}")
            log(f"  HIGH priority: {total_high}")
            log(f"  MEDIUM priority: {total_medium}")
            if auto_fix:
                log(f"Total fixes applied: {total_fixed}")
            break

        batch_num = offset // BATCH_SIZE + 1
        total_batches = (total_words + BATCH_SIZE - 1) // BATCH_SIZE

        log(f"[Batch {batch_num}/{total_batches}] Words {offset+1}-{offset+len(words)} / {total_words}")
        log(f"  Words: {', '.join(w['lemma'] for w in words[:5])}{'...' if len(words) > 5 else ''}")

        # Run audit
        batch_results = run_batch_audit(words)

        # Aggregate issues
        issues = aggregate_issues(batch_results, words)

        # Log issues
        high_count = sum(1 for i in issues if i['priority'] == 'HIGH')
        medium_count = sum(1 for i in issues if i['priority'] == 'MEDIUM')
        low_count = sum(1 for i in issues if i['priority'] == 'LOW')

        total_issues_found += len(issues)
        total_high += high_count
        total_medium += medium_count

        log(f"  Results: {len(words)} words, {high_count} HIGH, {medium_count} MED, {low_count} LOW")

        for issue in issues:
            issue_line = f"{issue['word']}: [{issue['priority']}] {issue['agreement']} - {issue['details'][0]}"
            log(issue_line, ISSUES_LOG)

        # Apply fixes if auto-fix enabled
        if auto_fix and high_count > 0:
            fixed = apply_high_priority_fixes(issues, db_path)
            total_fixed += fixed
            if fixed:
                log(f"  Applied {fixed} fixes")

        offset += BATCH_SIZE

        # Small delay between batches
        time.sleep(1)

    return total_issues_found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 6 Granular Audit")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--offset", type=int, default=0, help="Starting offset")
    parser.add_argument("--min-rank", type=int, default=5000, help="Min frequency rank")
    parser.add_argument("--max-rank", type=int, default=25000, help="Max frequency rank")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-apply HIGH priority fixes")
    args = parser.parse_args()

    run_continuous_audit(
        Path(args.db),
        start_offset=args.offset,
        min_rank=args.min_rank,
        max_rank=args.max_rank,
        auto_fix=args.auto_fix
    )
