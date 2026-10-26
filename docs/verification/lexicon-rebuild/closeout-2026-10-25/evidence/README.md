# Evidence for the revised rule review and emotion draft

Each script writes one complete JSON file (no sampling). Run from the repository root:

```sh
d=docs/verification/lexicon-rebuild/closeout-2026-10-25/evidence
for s in emotion_population fn_index_audit problem_lu_effect row11_reach join_contract_counts source_rule_reach template_fields; do
  uv run python "$d/$s.py" "$d/$s.json"
done
```

`template_fields` reads `emotion_population.json`, so it runs last.

| Output | What it shows |
|---|---|
| `emotion_population.json` | The 159 readings rows 19–21 would reach (77 adjectives, 30 verbs, 52 nouns), with every USAS tag and FrameNet frame. Nearly all "bank leads" are other senses of the same spelling. |
| `fn_index_audit.json` | FrameNet's `luIndex.xml`, which the adapter reads, omits exactly its 59 units marked Problem. |
| `problem_lu_effect.json` | Reading those 59 would add *annoyed, irritated, shocked* to row 19 and *enjoyment* to row 21; nothing else changes. |
| `row11_reach.json` | The 20 gate words row 11 gives FEEL, and which carry no USAS emotion tag on the verb. |
| `source_rule_reach.json` | Rows 6–8 computed by the builder's own `source_matches`: 38, 28 and 35 words (39 matches for row 6). |
| `join_contract_counts.json` | The revised join: which pairs certify, which go to the discriminator, which stop joining. |
| `definition_classes.json` | The must-not search over the readings' FrameNet definitions, classified by hand; no definition text is copied. |
| `template_fields.json` | The eight reading classes, with every population word's class, and the cells rows 19–26 fix for each: 40 open fields for the Fear adjectives with CAUSE fixed (option A), 41 with CAUSE open (option B), more without 3b. It explains why an open field is unproven rather than uncertain. It projects 13 published explications as gold (Wierzbicka 1999 and 1990b, primary, checked against the page images), with the GSE projection choices the gold depends on, and checks each against its class's fixed cells with a named code. The fixed cells came from the same explications, so this is not a held-out test. It also lists the controls for the typed GOOD field and which control words are in the slice. |
| `nsm_sources.json` | Citations, DOIs or ISBNs, the sha256 of each copy of record, and the pages quoted for every NSM source in `NSM_RESOLUTIONS.md`. No full text is committed; the copies are in `data/external/references/` (git-ignored). |

Primary sources read whole for this revision:
- the FrameNet frames Emotion_directed, Experiencer_focus, Fear, Emotions_by_possibility, Emotions_by_stimulus, Desirability, Size and Dimension;
- VerbNet `admire-31.2`;
- the [USAS guide](https://ucrel.lancs.ac.uk/usas/usas_guide.pdf);
- the NSM sources listed in `nsm_sources.json`, including the works Rohan supplied (F141):
  - Wierzbicka 1990b, whole;
  - Wierzbicka 1999, chapter 2 and chapter 1 §9;
  - Goddard & Wierzbicka 2014, §§3.1–3.3 and 5.7–5.8.

An independent falsification pass by Codex over those texts and the previous revision found nothing the revision does not now address.

An earlier extraction of the [NSM chart v20](https://nsm-approach.net/wp-content/uploads/2022/05/Chart-of-NSM-Semantic-Primes_English_v20_May-2022.pdf) lacked its logical-concept and intensifier boxes. The text of the copy of record has them, and `NSM_RESOLUTIONS.md` quotes from it.
