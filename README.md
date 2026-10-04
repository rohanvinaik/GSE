# GSE — Geometric Semantic Encoding

**Encode meaning as geometry, built from a closed set of universal primitives — where antonyms come out exactly opposite by construction, not because a model learned it.**

`8,192-dim sparse ternary · 8 NSM banks · 62 universal primitives · antonyms exactly −1.0 by construction · no learned embedding · deterministic`

An embedding is a learned black box. It is dense and opaque. It is confident about everything you hand it, including nonsense. GSE is the opposite. It builds a sentence's meaning from a fixed, universal basis. Because the basis is fixed, the geometry means something you can read:

```
$ gse compare

  happy / good        +0.71     synonyms — close
  good / bad          −1.00     antonyms — exactly opposite
  big / small         −1.00
  fast / slow         −1.00
  dog / philosophy     0.00     unrelated — orthogonal

  "John loves Mary" / "Mary loves John"    0.35     role reversal, detected
```

The antonyms are not *near* −1. They are −1.00, every time, because a primitive and its opposite are constructed as exact negations of each other — the score is a fact about the encoding, not a number a model happened to settle on. And "John loves Mary" is not the same vector as "Mary loves John," because the roles are bound, not bagged. Nothing here was trained.

---

## Meaning as geometry, from the atoms of language

Underneath GSE is the **Natural Semantic Metalanguage** — Anna Wierzbicka's finding that every human language shares the same small set of irreducible concepts, the ones you cannot define without circularity: `I`, `YOU`, `GOOD`, `BAD`, `THINK`, `KNOW`, `DO`, `HAPPEN`, `NOT`, `BECAUSE`, and about fifty more. GSE takes those **62 primitives** as an orthonormal basis. Every word is encoded as its decomposition into them. Meaning is not learned from a corpus. It is *composed* from a basis that predates the corpus.

The vectors are **8,192-dimensional, sparse, and ternary** — every coordinate is −1, 0, or +1 — laid out across **8 semantic banks**, one per primitive family:

| Bank | Family | Primitives |
|---|---|---|
| 0 | Substantives | `I` `YOU` `SOMEONE` `SOMETHING` |
| 1 | Determiners | `THIS` `SAME` `ONE` `ALL` `MUCH` |
| 2 | Evaluators | `GOOD` `BAD` `BIG` `SMALL` |
| 3 | Mental | `THINK` `KNOW` `WANT` `FEEL` |
| 4 | Action | `DO` `HAPPEN` `MOVE` `LIVE` `DIE` |
| 5 | Temporal | `WHEN` `NOW` `BEFORE` `AFTER` |
| 6 | Spatial | `WHERE` `HERE` `ABOVE` `BELOW` |
| 7 | Logical | `NOT` `MAYBE` `CAN` `BECAUSE` |

A word is placed by its primitive decomposition. A sentence is built from its words, by binding and bundling up the dependency parse. Structure survives into the geometry. `NOT` inverts, so `good` and `bad` land as exact negatives. Roles are bound to their fillers, so swapping subject and object moves the vector. The 15,909-word lexicon carries the decompositions. The 30 semantic roles carry the structure.

## Auditable to the primitive

Because the geometry is composed, not fit, every claim it makes is inspectable. A vector is sparse, so you can read which banks fired and which primitives placed it. The composition is checked with a **Merkle tree**, so a representation is verifiable the way a commit is. And the pipeline **abstains** rather than guess: a coherence pass flags the anomalies — an animacy violation, an impossible sparsity, an inconsistency — instead of returning a confident vector over a sentence it could not parse. A meaningful zero is a typed answer, not a hole. There is no temperature, and no learned weight anywhere in the path — run it twice, get the same vector.

## Use it

```python
from gse import GSEPipeline

gse = GSEPipeline()
gse.encode_sentence("The committee approved the proposal.")   # → a sparse ternary vector
gse.compute_similarity("The dog runs.", "The cat runs.")      # → 0.94, + per-bank breakdown
```

The similarity carries a `bank_similarities` breakdown, so a match is never a single opaque number — you can see *which* families of meaning agree. Same from the CLI: `python -m gse.cli compare "big" "small"`.

## The layer everything else reasons over

GSE is the substrate for the rest of the stack. A reasoner is only as auditable as the meaning it runs on. [Regenesis](https://github.com/rohanvinaik/Regenesis) derives story implications over GSE's roles, confidence, and provenance. The chess, career, and pitch engines — [Yami](https://github.com/rohanvinaik/Yami), CareerForge, StartupForge — recognize Forms in GSE-parsed text. The voice profiler reads a document's primitive-bank signature straight off it. Each one abstains exactly where GSE abstains, and carries provenance exactly because GSE does.

## Status

Deterministic, GSE-native, no JVM. 40/40 unit tests passing. Validated on the semantic relationships it is built to guarantee — synonyms cluster, unrelated pairs sit near zero, and primitive antonyms register exactly −1.0 (8/8, by construction). The theory (the NSM basis, the ternary composition, the constraint cascade that resolves a reading by elimination) is in [`docs/`](docs/); the semantic-role and lexicon layers are built and measured.

---

MIT — Rohan Vinaik. Meaning composed from a basis, not fit to a corpus.
