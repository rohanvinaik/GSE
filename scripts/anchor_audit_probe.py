"""W2 measurement probe: run the real story corpus through GSE's resolve (the same
encode_document_utterances -> resolve_document call gse_emit_narrative makes) and
collect grounding.ANCHOR_AUDIT after every story — the per-proper-noun anchor-coherence
score distribution the abstain-on-mismatch gate must be calibrated from.

Output: one JSON per story on stdout {story, audit: {lemma: [[leaf, score], ...]}}.
"""

import glob
import json
import sys

from gse.api import GSEEncoder
from gse.discourse.profile import split_sentences
from gse.discourse.speech import encode_document_utterances
from gse.symbolic import GenealogyStore, grounding, resolve_document

# The measured corpus = every story that has an artifact beside it (the curated set the
# engine actually ran), not the full 1600-file accumulation.
STORIES = sorted(
    a.replace(".artifact.json", ".story.txt") for a in glob.glob("/Users/rohanvinaik/Genesis/stories/*.artifact.json")
)

enc = GSEEncoder()
store = GenealogyStore()

for path in STORIES:
    raw = open(path).read()
    lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.startswith("GENRE:")]
    text = " ".join(lines)
    try:
        sentences = split_sentences(text)
        trees = encode_document_utterances(enc, sentences)
        # raw_text = the corroboration substrate (the gate's own scoring; matches the pipeline)
        resolve_document(trees, store, genre="NARRATIVE", raw_text=raw)
        audit = {k: v for k, v in grounding.ANCHOR_AUDIT.items()}
    except Exception as e:
        audit = {"__error__": repr(e)}
    sys.stdout.write(json.dumps({"story": path.split("/")[-1], "audit": audit}) + "\n")
    sys.stdout.flush()
