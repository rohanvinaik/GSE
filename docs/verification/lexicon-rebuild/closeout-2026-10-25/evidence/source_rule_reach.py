"""Words each adjectival source rule reaches, computed by the builder's own source_matches.

Every USAS lemma (keyed as the builder keys words) with an A5.1, N3.2 or E4.1 alternative in any
row is offered to build.source_matches with the full rulebook, admitted or not. Complete lists.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.build import source_matches  # noqa: E402
from gse.lexicon_builder.registry import load_rulebook  # noqa: E402
from gse.lexicon_builder.sources import NativeSources, word_key  # noqa: E402


def main() -> int:
    words = set()
    with open("data/external/usas/semantic_lexicon_en.tsv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if any(re.match(r"(A5\.1|N3\.2|E4\.1)", t) for t in row["semantic_tags"].split()):
                words.add(word_key(row["lemma"]))
    sources = NativeSources(sorted(words), Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    reach: dict[str, set] = defaultdict(set)
    rows: dict[str, list] = defaultdict(list)
    for word in sorted(words):
        for m in source_matches(sources.for_word(word), book):
            reach[m["rule"]["rule_id"]].add(word)
            rows[m["rule"]["rule_id"]].append({"word": word, "tag": m["tag"], "frames": sorted({f["frame"] for f in m["frames"]})})
    report = {
        "candidate_words": len(words),
        "rule_ids": {r["rule_id"]: {"category": r["category"], "frames": r["frames"], "pos": r["pos"]} for r in book["source_rules"]},
        "distinct_words": {k: len(v) for k, v in sorted(reach.items())},
        "matches": {k: v for k, v in sorted(rows.items())},
    }
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
