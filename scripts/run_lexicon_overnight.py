"""Continue the lexicon build unattended, on API credit (Rohan, 2026-11-25).

One Claude Code session, billed to the Anthropic API key and never the subscription, works through the
remaining work packages in ``openspec/changes/lexicon-symbolic-foundation/tasks.md`` the way the
interactive session did: write a rule as code, rebuild with ``scripts/build_word_senses.py``, run the
checks, commit what passes. The model writes code only. Every lexicon value is computed by the build
from the sources and admitted rules, and ``tests/test_lexicon_every_value_has_a_warrant.py`` throws
out any value without a warrant.

The key reaches Claude Code through its ``apiKeyHelper`` (SquishOS's reader of the operator's store),
so it is never in the agent's environment or in any file here. The session may not publish, may not
edit the release, the pinned builder modules, the runtime, or the guard tests, and may not read the
key store. Its final report and cost go to a gitignored file under ``data/``.

    .venv/bin/python scripts/run_lexicon_overnight.py --check     # a cents-sized call: key and billing
    nohup caffeinate -i .venv/bin/python scripts/run_lexicon_overnight.py > /tmp/lexicon-overnight.log 2>&1 &
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RELEASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-022.db"
CANDIDATE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-022-word-senses.db"
PINS = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint/postwriter-validation.json"
KEY_READER = Path.home() / "Projects/SquishOS/ops/agents/bin/anthropic-consult"
KEY_STORE_DIR = Path.home() / "tools"
MODEL = "claude-opus-5-5"
BUDGET_USD = 25.0
PACKAGES = ("WP-0", "WP-3", "WP-2", "WP-1", "WP-5")

ALLOWED_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "Edit",
    "Write",
    "Bash(.venv/bin/python:*)",
    "Bash(.venv/bin/lint-imports:*)",
    "Bash(uvx ruff@0.16.10:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(git add:*)",
    "Bash(git commit:*)",
    "Bash(git push:*)",
    "Bash(git restore:*)",
    "Bash(openspec:*)",
    "Bash(ls:*)",
    "Bash(wc:*)",
]
PROTECTED = [
    "data/**",
    "docs/readings/**",
    "GSE/api/**",
    "GSE/symbolic/**",
    "GSE/nlp/**",
    ".claude/**",
    "AGENTS.md",
    "CLAUDE.md",
    "pyproject.toml",
    "uv.lock",
    "scripts/lexicon_coherence.py",
    "scripts/run_lexicon_overnight.py",
    "scripts/compare_word_senses.py",
    "tests/test_lexicon_word_sense_acceptance.py",
    "tests/test_lexicon_no_new_model_values.py",
    "tests/test_lexicon_every_value_has_a_warrant.py",
]
DENIED_COMMANDS = [
    "Bash(git add -A:*)",
    "Bash(git add .:*)",
    "Bash(git add --all:*)",
    "Bash(git commit -a:*)",
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "advisor",
]

TASK = f"""Continue GSE's lexicon build: work packages {", ".join(PACKAGES)}, in that order, as written in
openspec/changes/lexicon-symbolic-foundation/tasks.md. Follow the brief exactly."""

BRIEF = """\
# Brief: continuing GSE's lexicon build, unattended, for Rohan (the owner)

You continue work an interactive session did today. Work as it did: read the code, write the change,
rebuild, run the checks, commit what passes, record what you measured. Nobody is watching tonight.

## The thesis (Rohan's; it governs everything)
The lexicon is built by a symbolic, deterministic process: a script computes every bank value from the
NLP sources (WordNet, VerbNet, Wiktionary, the rating lexicons) and from admitted rules. That is why it
is cheap, why it can cover the whole lexicon, and why it can be inspected. "If some addition doesn't
have a rule behind it or a direct warrant from the underlying NLP data sources we have, then it gets
tossed." Unknown is not zero: a bank no source or rule settles stays open.

## Hard rules
1. No model decides a value. You write rules as code; the build computes the values. Never call a
   model or API from code, never hand-type a value, never put a list of words with values in code
   (a rule is a few lines over source data). tests/test_lexicon_every_value_has_a_warrant.py fails a
   literal list of more than 25 strings and any value whose warrant is not a source or admitted rule.
2. The release is read-only. Never change definition_states, lexemes, or the 'relations' key of
   builder_metadata in any database. The replay of the release must stay valid.
3. A coherence rule you admit (WP-3) is stored in the candidate's builder_metadata under the key
   'word_sense_rules': a JSON list of relations in the same shape as the release's 'relations'
   entries, each with "rule_id" (prefix "coherence:"), "approved": true, and an "admission" record:
   {"conditional_probability", "min_partition_support", "held_out_drift", "counterexamples"}. Only
   rules meeting the policy (>= 0.85, >= 40 per partition, <= 0.1) are admitted. The sense closure
   applies the release's relations plus these. scripts/build_word_senses.py writes the key.
   Admission must be recomputable by a committed command: `.venv/bin/python scripts/word_sense_coherence.py
   --admitted` prints a JSON list of the admitted rule_ids, measured on the population of sense cores
   closed under the release's relations only (never under word_sense_rules: measured after they apply,
   every rule scores 100%). The launcher reruns it and compares it with what you stored.
6. Never destroy a correct value. The launcher compares every word's reading with the published
   lexicon and reports filled, changed and removed values by warrant: "changed" should be 0, and a
   removal is only acceptable where a package deliberately withdraws a main sense (WP-0).
4. Files you may change: GSE/curation/lexicon_builder/source_agreement.py, word_senses.py, new modules
   GSE/curation/lexicon_builder/word_sense_*.py, GSE/lexicon/senses.py, scripts/build_word_senses.py,
   new scripts scripts/word_sense_*.py, tests/test_lexicon_source_agreement.py,
   tests/test_lexicon_senses_reader.py, new tests tests/test_lexicon_*.py, and the change's design.md
   and tasks.md. Everything else is off limits: the other lexicon_builder modules are pinned by
   Rohan's checkpoint, GSE/symbolic/lexical_grounding.py belongs to Rohan's other session (WP-4 is
   not yours), and you never publish or touch data/lexicon_active.json.
7. A decision that is Rohan's (a semantic judgment no rule or source settles): do not make it. Write
   the question under the package in tasks.md and move on.

## Per package
1. Read the package in tasks.md and the design's "Founder correction" section, and the code you change.
2. Implement it, with unit tests for the rule.
3. Rebuild and check (GSE_SENSE_CANDIDATE is already set in your environment). The full rebuild takes
   about 5 minutes: give that Bash call a timeout of 600000 ms.
     .venv/bin/python scripts/build_word_senses.py --all
     .venv/bin/python scripts/build_word_senses.py --verify 300          (0 mismatches)
     .venv/bin/python -m pytest -q -p no:randomly tests/test_lexicon_source_agreement.py \\
         tests/test_lexicon_senses_reader.py tests/test_lexicon_word_sense_acceptance.py \\
         tests/test_lexicon_no_new_model_values.py tests/test_lexicon_every_value_has_a_warrant.py <your new tests>
     uvx ruff@0.16.10 check <changed .py> ; uvx ruff@0.16.10 format --check <changed .py> ; .venv/bin/lint-imports
4. All pass: tick the package in tasks.md with what you measured (at least: assigned nonzero values and
   open banks in word_senses before and after, and the package's own acceptance), then
   `git add <each file by path>`, `git commit -m "<type>: <what, plainly>"`, `git push origin main`.
   No AI attribution and no Co-Authored-By lines in commit messages.
5. A check fails and you cannot fix it inside the package: `git restore` only the files you changed,
   rebuild with --all so the candidate matches the committed code, write under the package in tasks.md
   what failed and why, commit tasks.md, and go on to the next package.

## At the end
Reply with, per package: done or not, the commit, the numbers, and anything Rohan must decide. Plain
words. (The launcher runs the full test suite and the checks again itself after you finish.)
"""


def _settings() -> str:
    helper = (
        f"{ROOT / '.venv/bin/python'} -c "
        f"\"import runpy; k, _ = runpy.run_path('{KEY_READER}')['read_key'](); print(k)\""
    )
    return json.dumps({"apiKeyHelper": helper})


def _denied() -> list[str]:
    pins = json.loads(PINS.read_text())["builder_source_pins"]
    paths = sorted(pins) if isinstance(pins, dict) else sorted(p["path"] for p in pins)
    denied = [f"{tool}({path})" for path in PROTECTED + paths for tool in ("Edit", "Write")]
    return denied + DENIED_COMMANDS + [f"Read(/{KEY_STORE_DIR}/**)"]


def command(prompt: str, budget: float, brief_file: Path) -> list[str]:
    return [
        shutil.which("claude") or "claude",
        "--bare",
        "-p",
        prompt,
        "--model",
        MODEL,
        "--effort",
        "high",
        "--max-budget-usd",
        f"{budget:.2f}",
        "--output-format",
        "json",
        "--settings",
        _settings(),
        "--append-system-prompt-file",
        str(brief_file),
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--disallowedTools",
        *_denied(),
        "--allowedTools",
        *ALLOWED_TOOLS,
    ]


def environment() -> dict[str, str]:
    drop = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY"}
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env["GSE_SENSE_CANDIDATE"] = str(CANDIDATE)
    return env


WORD_SENSE_TESTS = [
    "tests/test_lexicon_source_agreement.py",
    "tests/test_lexicon_senses_reader.py",
    "tests/test_lexicon_word_sense_acceptance.py",
    "tests/test_lexicon_no_new_model_values.py",
    "tests/test_lexicon_every_value_has_a_warrant.py",
]
AFTER_CHECKS = [
    ("replay_sample", [".venv/bin/python", "scripts/build_word_senses.py", "--verify", "300"]),
    ("word_sense_tests", [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:randomly", *WORD_SENSE_TESTS]),
    ("import_contracts", [".venv/bin/lint-imports"]),
    ("full_suite", [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:randomly"]),
]


def _run(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd=ROOT, env=environment(), stdin=subprocess.DEVNULL, capture_output=True, text=True)
    out = (
        proc.stdout
        if proc.returncode == 0 and proc.stdout.lstrip().startswith(("{", "["))
        else proc.stdout + proc.stderr
    )
    return {"exit": proc.returncode, "tail": out if out.lstrip().startswith(("{", "[")) else out[-1500:]}


ALLOWED_FILES = re.compile(
    r"^(GSE/curation/lexicon_builder/(source_agreement|word_senses|word_sense_[a-z_]+)\.py"
    r"|GSE/lexicon/senses\.py"
    r"|scripts/(build_word_senses|word_sense_[a-z_]+)\.py"
    r"|tests/test_lexicon_[a-z_]+\.py"
    r"|openspec/changes/lexicon-symbolic-foundation/(design|tasks)\.md)$"
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _stat(path: Path) -> list[int] | None:
    return [path.stat().st_size, path.stat().st_mtime_ns] if path.exists() else None


def snapshot() -> dict:
    """What must not change overnight: the active pointer, the release and the published copy."""
    from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

    published = resolve_lexicon_path()
    return {
        "head": _git("rev-parse", "HEAD"),
        "pointer_sha256": hashlib.sha256(ACTIVE_POINTER.read_bytes()).hexdigest(),
        "published": str(published),
        "files": {str(p): _stat(p) for p in (RELEASE, published)},
    }


def audit(start: dict) -> dict:
    """Record-only checks the session cannot talk its way past; nothing is undone automatically."""
    from GSE.lexicon_resource import ACTIVE_POINTER

    now = snapshot()
    committed = [f for f in _git("diff", "--name-only", f"{start['head']}..HEAD").splitlines() if f]
    report = {
        "pointer_unchanged": now["pointer_sha256"] == start["pointer_sha256"],
        "release_and_published_unchanged": all(_stat(Path(p)) == s for p, s in start["files"].items()),
        "commits": _git("log", "--format=%h %s", f"{start['head']}..HEAD").splitlines(),
        "files_outside_allowed": [f for f in committed if not ALLOWED_FILES.match(f) or f in PROTECTED],
        "uncommitted": _git("status", "--short").splitlines(),
        "active_pointer": ACTIVE_POINTER.read_text(),
    }
    tally = _run(
        [
            ".venv/bin/python",
            "scripts/compare_word_senses.py",
            "--before",
            start["published"],
            "--after",
            str(CANDIDATE),
        ]
    )
    try:
        report["values_vs_published"] = json.loads(tally["tail"]) if tally["exit"] == 0 else tally
    except json.JSONDecodeError:
        report["values_vs_published"] = tally
    with sqlite3.connect(CANDIDATE.as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT value FROM builder_metadata WHERE key = 'word_sense_rules'").fetchone()
    stored = sorted(rule["rule_id"] for rule in json.loads(row[0])) if row else []
    if stored:
        rerun = _run([".venv/bin/python", "scripts/word_sense_coherence.py", "--admitted"])
        try:
            recomputed = sorted(json.loads(rerun["tail"])) if rerun["exit"] == 0 else None
        except json.JSONDecodeError:
            recomputed = None
        report["admission_recheck"] = {
            "stored": len(stored),
            "recomputed": None if recomputed is None else len(recomputed),
            "match": recomputed == stored,
            "detail": None if recomputed is not None else rerun,
        }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="one tiny call: confirms the key and API billing")
    parser.add_argument("--budget", type=float, default=BUDGET_USD)
    args = parser.parse_args(argv)
    prompt, budget = ("Reply with the single word OK.", 0.25) if args.check else (TASK, args.budget)
    started = datetime.now().isoformat(timespec="seconds")
    start = snapshot()
    with tempfile.TemporaryDirectory(prefix="lexicon-overnight-") as tmp:
        brief = Path(tmp) / "brief.md"
        brief.write_text(BRIEF)
        run = subprocess.run(
            command(prompt, budget, brief),
            cwd=ROOT,
            env=environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    try:
        parsed = json.loads(run.stdout)
    except json.JSONDecodeError:
        parsed = None
    events = parsed if isinstance(parsed, list) else [parsed]
    result = next((e for e in reversed(events) if isinstance(e, dict) and e.get("type") == "result"), None)
    if result is None:
        result = {"is_error": True, "output_tail": (run.stdout + run.stderr)[-3000:]}
    record = {
        "started": started,
        "finished": datetime.now().isoformat(timespec="seconds"),
        "mode": "check" if args.check else "packages",
        "model": MODEL,
        "budget_usd": budget,
        "exit": run.returncode,
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
        "report": result.get("result") or result.get("output_tail"),
    }
    out = ROOT / f"data/lexicon_builder/overnight/{started.replace(':', '')}-{record['mode']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    out.with_suffix(".raw.json").write_text(run.stdout + run.stderr)  # gitignored, for inspection
    if not args.check:  # the same checks, run by this script, not taken from the session's report
        record["checks_after"] = {name: _run(cmd) for name, cmd in AFTER_CHECKS}
        record["audit"] = audit(start)
        out.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({name: r["exit"] for name, r in record["checks_after"].items()}), flush=True)
    print(json.dumps({k: record[k] for k in ("mode", "exit", "cost_usd", "turns", "is_error")}), flush=True)
    print(record["report"], flush=True)
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
