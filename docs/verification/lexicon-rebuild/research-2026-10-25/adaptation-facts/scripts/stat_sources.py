"""Record the size and modification time of every cited source file (metadata only; no file is opened).

Writes /tmp/gse-subagents/adaptation-facts/parts/50_source_snapshot.json.
"""

import datetime
import json
import os
from pathlib import Path

WORKTREE = Path("/Users/rohanvinaik/Projects/gse/.claude/worktrees/lexicon-builder/gse")
PAPERS = Path("/Users/rohanvinaik/Projects/rohan-vinaik.github.io/papers/Core Documents/GSE")
CHART = Path("/Users/rohanvinaik/Projects/gse/data/external/references/nsm-primes-chart-v20-2022.txt")
OUT = Path("/tmp/gse-subagents/adaptation-facts/parts/50_source_snapshot.json")

relative = [
    "gse/primitives_v2.py",
    "gse/vectors_v2.py",
    "gse/prime_projection.py",
    "gse/scale_definition.py",
    "gse/_archive/primitives.py",
    "gse/lexicon/modifier_hierarchy.py",
    "gse/lexicon/numerals.py",
    "gse/lexicon/function_words.py",
    "gse/lexicon/word_encoding.py",
    "gse/symbolic/modality.py",
    "gse/curation/schema.py",
    "gse/curation/build_clean_closed_class.py",
    "gse/curation/build_clean_operators.py",
    "gse/curation/build_clean_quantifiers.py",
    "gse/curation/constraint_aggregation/mapping_registry.py",
    "gse/curation/validation/hierarchy_validator.py",
    "gse/curation/decomposition/definitional_decomposer.py",
    "gse/curation/llm/prompts.py",
    "docs/NSM_GRAMMAR_MAPPING.md",
    "docs/GSE_EXTENSION_MAP.md",
    "docs/LEXICON_REBUILD.md",
    "docs/LEXICON_STRATEGY_RECONSIDERATION.md",
    "docs/ARCHITECTURE.md",
    "docs/planning/gse_implementation_spec.md",
    "docs/program/START_HERE.md",
    "docs/program/BUILD_SPEC.md",
    "docs/program/GLOSSARY.md",
    "docs/program/LEXICON_CONSTRUCTION_DESIGN.md",
    "docs/program/LEXICON_FOUNDER_WORDS_2026-10-24.md",
    "docs/verification/lexicon-rebuild/closeout-2026-10-25/NSM_RESOLUTIONS.md",
    "docs/verification/lexicon-rebuild/closeout-2026-10-25/RULE_REVIEW.md",
    "docs/verification/lexicon-rebuild/closeout-2026-10-25/EMOTION_SLICE_DRAFT.md",
    "docs/verification/lexicon-rebuild/closeout-2026-10-25/rule_decisions.json",
    "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPORT.md",
    "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md",
    "docs/verification/lexicon-rebuild/research-2026-10-25/README.md",
    "docs/verification/lexicon-rebuild/research-2026-10-25/nsm-prime-facts/parts/very_more_evidence.json",
    "openspec/changes/lexicon-symbolic-foundation/design.md",
    "openspec/changes/lexicon-symbolic-foundation/proposal.md",
    "openspec/changes/lexicon-symbolic-foundation/tasks.md",
    "openspec/changes/lexicon-symbolic-foundation/specs/lexicon-construction/spec.md",
]
builder = [
    "__main__.py",
    "artifact.py",
    "atomics.py",
    "audit.py",
    "bank_laws.json",
    "basis.py",
    "build.py",
    "core.py",
    "coverage.py",
    "fill.py",
    "foundation.json",
    "foundation.py",
    "model.py",
    "native_constraints.py",
    "number.py",
    "perception.py",
    "reading.py",
    "registry.py",
    "sources.py",
    "surprise.py",
    "tail.py",
]
relative.extend("gse/lexicon_builder/" + name for name in builder)
for name in (
    "tier_0_dispatch",
    "source_scope",
    "bipolar_exclusion",
    "verbnet",
    "usas",
    "framenet",
    "propbank",
    "wordnet_hierarchy",
    "conceptnet",
    "wiktionary",
    "nrc_vad",
):
    relative.append("gse/curation/external_sources/%s.py" % name)

absolute = [CHART]
for name in (
    "GSE_V2.md",
    "pronouns_numbers.md",
    "sentence_architecture.md",
    "GSE_HDC_architecture.md",
    "GSE_Novel_Contributions.md",
    "numerical_semantics_theory.md",
):
    absolute.append(PAPERS / name)


def describe(path):
    try:
        info = os.stat(path)
    except OSError as error:
        return {"error": str(error)}
    stamp = datetime.datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {"bytes": info.st_size, "mtime_local": stamp}


files = {}
for item in relative:
    files[item] = describe(WORKTREE / item)
for path in absolute:
    files[str(path)] = describe(path)

snapshot = {
    "captured_local": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "method": "os.stat on each path; no file content is read by this script",
    "paths_relative_to": str(WORKTREE),
    "files": files,
}
OUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("captured", snapshot["captured_local"], "for", len(files), "files")
errors = [k for k, v in files.items() if "error" in v]
print("errors:", errors)
