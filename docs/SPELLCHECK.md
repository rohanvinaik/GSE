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
# or just the validity list / its compact bloom:
python -m gse.curation.build_wordlist                   # downloads dump -> .txt + .bloom
python -m gse.curation.build_wordlist --bloom-only      # rebuild .bloom from existing .txt
```

Without the validity wordlist the corrector still works — it just falls back to the core
lexicon + WordNet, so modern/technical terms (`refactor`, `json`, …) are recognized less
broadly. The runtime loads the compact **bloom** (`data/wordlist_wiktionary.bloom`, a few
MB) when present, not the 52MB text set.

**Keyboard-HDC recovery layer (optional).** An orthogonal error model (`gse/nlp/hdc_speller.py`)
recovers the far, length-preserving multi-key slips edit-distance abstains on (`ecifentky →
evidently`). It needs a cached common-word lexicon (gitignored, rebuildable):

```bash
python -m gse.curation.build_hdc_speller               # encodes ~12k words -> data/hdc_speller.npz
```

If the cache is absent the layer simply no-ops (the corrector degrades to edit-distance only).
It fires **only on the abstain-residue** — tokens that don't ground *and* edit-distance gave
up on — behind the same grounding + shape gates, so the destruction bound is preserved.

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
pytest tests/test_spellcheck.py tests/test_hdc_speller.py   # behavioral tests (edit-distance + HDC)
python scripts/adversarial_destruction.py         # measured "never makes a right word wrong" bound
python scripts/hdc_destruction.py                 # same bound, for the keyboard-HDC layer (0.00000%)
```
