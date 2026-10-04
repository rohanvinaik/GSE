# SymbolicSpellCheck — setup & usage

A deterministic, symbolic spell-corrector: it auto-applies corrections it is confident of
and **surfaces ranked suggestions** otherwise — ordinary spell-check workflow, but every
suggestion is symbolically derived (a real word, edit-close, grounded), not a statistical
guess. It **never alters a token it recognizes as valid** (words, jargon, acronyms, names,
code, contractions). Failures are confined to *non-recovery*, never *destruction*.

Vision / rationale: `../../resume/Communication/vision/SymbolicSpellCheck_vision.md`
(architecture: `docs/ARCHITECTURE.md` §Layer 5.5).

## Setup

The corrector runs out of the box on the committed data (the CC-BY-SA misspellings table
and the project allowlist). For **full jargon coverage** it also wants the large validity
wordlist, which is gitignored (rebuildable). On a fresh clone, build it once:

```bash
python -m gse.curation.build_spellcheck_data            # fetches Wiktionary + builds all data
# or just the validity list / its compact trie:
python -m gse.curation.build_wordlist                   # downloads dump -> .txt + .marisa
python -m gse.curation.build_wordlist --trie-only       # rebuild .marisa from existing .txt
```

Without the validity wordlist the corrector still works — it just falls back to the core
lexicon + WordNet, so modern/technical terms (`refactor`, `json`, …) are recognized less
broadly. The runtime loads the compact EXACT **marisa-trie**
(`data/wordlist_wiktionary.marisa`, ~12MB, mmap) when present, not the 52MB text set.
(marisa over a bloom filter: bloom false positives would let a non-word pass the grounding
gate, breaking "every suggestion is a real word" — exactness matters.)

**Keyboard-HDC recovery layer (optional).** An orthogonal error model (`gse/nlp/hdc_speller.py`)
recovers the far, length-preserving multi-key slips edit-distance abstains on (`ecifentky →
evidently`). It needs a cached common-word lexicon (gitignored, rebuildable):

```bash
python -m gse.curation.build_hdc_speller               # encodes ~12k words -> data/hdc_speller.npz
```

If the cache is absent the layer simply no-ops (the corrector degrades to edit-distance only).
It fires **only on the abstain-residue** — tokens that don't ground *and* edit-distance gave
up on — behind the same grounding + shape gates, so the destruction bound is preserved.

**Entity leg (optional): proper-noun correction, alias-free.** Names get their own instance
of the same structural law (`gse/nlp/spellcheck_entity.py`): the SAME keyboard-weighted edit
generators, a grounding gate over `data/spell_entities.db` — an entity-name dictionary derived
purely from **canonical labels + their name-part tokens** (`gse.curation.build_spell_entities`,
reads `data/genealogy.db`) — a PageRank-percentile prior through the same
`edit_cost + λ·log10(rank)` score, and the referent's semantic-anchor bag ∩ document context
as a parameter-free confirmation. Wikipedia's redirect table (826K rows, including its
collated misspelling-redirects) is **never read at correction time** — it serves only as the
held-out eval corpus (`scripts/eval_entity_leg.py`). Measured on that in-reach slice:
**38% committed-correct / 2.7% committed-wrong / 80.5% recovered-or-offered**, pure structure.
Two gates carry the safety: a token that grounds as a name — including rare-but-real names
(`Shakespear` → Richmond Shakespear; `Melbourn`, Cambridgeshire) — is never touched; and an
entity commit must **beat or agree with the surface's word-space reading in the shared noisy
channel** (so a sole obscure entity name cannot out-commit a plausible ordinary word:
`Aadvark` offers `aardvark`, never commits `ardvar`). A name-like token that grounds only in
the rare multilingual validity tail (`Bosina`) gets entity neighbours **offered, never
auto-applied**. Honest edge, same class as the word leg's: a real name absent from every
substrate (4.7M Wiktionary titles + 127K entity names + WordNet + allowlist) that sits one
edit from a prominent entity would be rewritten (`Bosnja` → Bosnia); the mitigation is
`spell_learn`, exactly as for jargon. Absent `spell_entities.db` the leg no-ops.

```bash
python -m gse.curation.build_spell_entities            # genealogy.db labels -> data/spell_entities.db
```

## Usage

**Python API** (`gse/nlp/spellcheck.py`):

```python
from gse.nlp.spellcheck import correct, suggest
correct("recieve")          # Correction(committed="receive", …)
correct("GSE")              # committed=None — valid-shaped token, never mangled
suggest("wierd", n=3)       # [weird, wired, wield] ranked, each with its score trace
```

**REPL**:

```bash
python -m gse.nlp.spellcheck_repl                 # interactive
python -m gse.nlp.spellcheck_repl "teh wierd dog" # one-shot
```

**MCP server** (`SymbolicSpellCheck`, tool `spell_suggest(text, n)`):

```bash
pip install -e ".[spellcheck-mcp]"     # installs the `mcp` transport + the console script
gse-spellcheck-mcp                      # runs the stdio server
```

Or register it in your MCP client (command = the repo's Python, args = `-m
gse.mcp.spell_server`, cwd = repo root). Data paths resolve absolutely, so it runs from
any working directory.

## Tests & verification

```bash
pytest tests/test_spellcheck.py tests/test_hdc_speller.py \
       tests/test_spellcheck_entity.py             # behavioral tests (edit-distance + HDC + entity leg)
python scripts/adversarial_destruction.py         # measured "never makes a right word wrong" bound
python scripts/hdc_destruction.py                 # same bound, for the keyboard-HDC layer (0.00000%)
python scripts/eval_entity_leg.py                 # entity leg vs held-out Wikipedia misspelling-redirects
```
