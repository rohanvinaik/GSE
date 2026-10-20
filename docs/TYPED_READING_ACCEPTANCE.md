# Located reading acceptance receipt

This receipt preserves the original nine-file consumer snapshot. The implementation is applied; the subsequent 13-file dependency projection is recorded in `verification/typed-reading-2026-10-20/final-dependency-projection.json`, with canonical equality and current reference hashes. Earlier hashes and CLI observations below remain historical. It makes no authored interpretation of the private passages and no semantic-quality verdict. Historical readings remain separate.

## Bound identities

GSE Python source SHA-256: `b4510b6b8ec1b3b0c3ac173d7a954e6968cf59a93785fd84027a63ea15366b2a`.

Probe SHA-256: `45e09a91f0f5e60ac3779a7a3451cd77cb1ced69b500d7cd071088dc355b5140`.

The nine consumer file hashes are preserved in `integrity.json` and `projection-manifest.json`. Each immutable raw Reading retains its original producer receipt; consumer hashes were attached only to copied inputs for profile/reference projection.

## Whole retained sources

| Source | Original UTF-8 SHA-256 | Source sentences | Read utterances | Claims: supported / unresolved / unsupported | Local origins: read / unread | Graph nodes / edges |
|---|---|---:|---:|---|---|---|
| founder | `87ed0af2dba6ff193357122a3cc125f86abfbedbad7a38fc517f489df16a2869` | 436 | 696 | 127 / 154 / 1044 | 1877 / 2 | 273 / 311 |
| winston | `a8b714fd88dff0eb07a8d0155192c2909adb373b54286de2ef334fcb0d9f6873` | 540 | 553 | 278 / 158 / 865 | 2014 / 0 | 391 / 551 |

Both whole-source runs terminated `complete`, retained ordered initial/final provenance, and had zero transport errors. Healing resources and WordNet receipts reported `read`. The founder source has one explicit empty attribution-only sentence. Its independent mention channel is partial: `s56:u2` at `[agent]` and `s378:u0` at `[left,right,agent]` have `source_head_trace_mismatch`; the primary utterance readings remain available.

## Controls

| Complete control | Contradictions | Near misses | Semantic refrain groups | Earlier derivable claims | Cross-sentence pointers |
|---|---:|---:|---:|---|---|
| A trout is a fish. A whale is not a fish. A whale is a fish. | 1 | 1 | 0 | 0 / 3 | 0 / 6 |
| Alice trusts Bob. Bob does not trust Alice. | 0 | 0 | 0 | 0 / 2 | 0 / 4 |
| Alice might trust Bob. Alice does not trust Bob. | 0 | 0 | 0 | 0 / 1 | 0 / 4 |
| Alice murdered Bob. Alice killed Bob. | 0 | 0 | 0 | 0 / 2 | 0 / 4 |
| The guard hurt the prisoner. The guard injured the prisoner. The guard wounded the prisoner. | 0 | 0 | 1 | 2 / 3 | 0 / 6 |
| If Rex barks, Mike leaves. Rex barks. Mike leaves. | 0 | 0 | 0 | 1 / 2 | 0 / 4 |
| Mike leaves. If Rex barks, Mike leaves. Rex barks. | 0 | 0 | 0 | 0 / 2 | 0 / 4 |
| If Rex barks, Mike leaves. Rex barks and Julia sleeps. Mike leaves. | 0 | 0 | 0 | 1 / 2 | 0 / 5 |
| A woman smiled. [paragraph break] She ran. | 0 | 0 | 0 | 0 / 2 | 1 / 2 |

The compound-premise derivation cites `s0:u0:c0` and atomic premise `s1:u0:c1`, rather than the conjunction container. The supported synonym control uses the selected lexical primitive projection; the murder/kill control retains different projections and receives no semantic recurrence. These are bounded shared claim-key decisions, not assertions about unrestricted paraphrase.

## Public entry points and stored references

Four real CLI invocations exercised `read` and `compare`, each in raw and default-healed mode, with `--by paragraph --timeout 900 --json`. Inputs were complete retained founder paragraphs `p1` and `p2`, with source spans `[660,1308)` and `[1310,2600)`. Their source identity is the founder SHA above. Comparison labels represent two different retained passages, not an authored revision. All four exited zero; all six constituent reports completed with zero transport errors, current producer/consumer identities, 59 metric rows and valid Reading/Profile schemas. Stderr contained only the CLI next-action hint. Default healing applied one edit to `p1` and two edits to `p2`, preserving original hashes and recording distinct measured hashes.

Strict schema validation covered all eleven saved Readings and Profiles, both rebuilt References, and sentence/paragraph/section/line views of the trout/whale and cross-paragraph controls. Independent integrity checks verified source byte hashes, exact sentence/word spans, manifest ownership, claim IDs, prior-only derivation sources and prior certified mention receipts.

The staged `his` and `winston` references were rebuilt from these existing raw Readings without another GSE read, using domain `explanatory_prose`, register `retained_source`, and size 500. Both retain `no_band / missing_independent_partitions`; no partition manifest was manufactured. These historical staging versions were applied and subsequently replaced by the dependency-only projections; all fields except consumer identity remained equal.

| Reference | Saved UTF-8 bytes | SHA-256 |
|---|---:|---|
| his | 94315116 | `0e5b285239c2c585dfac2d9bf96abdd03f2da50141fa22941b5b95fd36ca7ade` |
| winston | 66401923 | `7707a95244163b42ba8d168ed2ce858c45a1571cd651259bac127bcf076f62d2` |

## Evidence locations

Private full Readings, Profiles, CLI outputs and source selections remain beneath staged SquishOS `data/voice/acceptance-traces/final-origins/`. Text-free receipts are `manifest.json`, `integrity.json`, `projection-manifest.json`, `public-summary.json`, and `cli/manifest.json`. Formal schemas and adversarial fixtures are mirrored under `openspec/changes/archive/2026-10-20-preserve-typed-prose-readings/contracts/voice-reading-1/`.

The test and mutation gate owners retain their independent certificates. This receipt does not replace those gates or certify unsupported/unresolved channels.
