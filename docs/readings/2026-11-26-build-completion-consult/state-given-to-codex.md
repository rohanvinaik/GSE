- Live lexicon: sparse-release-022-senses6.db (the only copy). 401,596 definitions (WordNet 155,111; Wiktionary
  246,240; closed class 213; NSM chart 29) over 67,173 lemmas; 56 banks; states +1, -1, 0, silence.
- Decided cells at definition level: the release stores ~506,600 (2.3%). A reviewed four-state closure (head laws
  F144, F067, F088's reading of release relations) decides 1,770,913 (7.9%) but is a measurement, not installed.
  Valency zeros (79,780: non-living things/times/places cannot bear person-typed predicates) are also measurement only.
  Sub-kind inheritance added 63,638 definition cells (derived layer) today.
- Word senses (what the runtime reads): 110,678 senses; 149,883 nonzero values (~1.35 per sense) by warrant: stored
  member values 132,137; lemma-level source agreement 3,280; NSM molecule inheritance 4,464; rule consequences 2,232;
  sub-kind inheritance 7,770.
- Joint specification space (measured on release 021): 32.8M bits (marginal-domain bound 35.0M bits).
- NSM agreement, 35 verified explications of lexicon words: 50 primes agree, 7 contradict, 305 missing, 11 used with
  both signs. Of the remaining content gaps, most have no source vote at all in GSE's sources for that bank.
- Built this week, each covering 10^3-10^5 cells: four-state engine (silence as a state; F088 relation reading);
  72 prime profiles and 37 function words reconstructed from authored claims; valency zeros; NSM molecule
  inheritance ('creatures' explication -> animal.n.01: MOVE, FEEL); sub-kind inheritance over WordNet kind-of,
  synonymy, satellites, entailment, Wiktionary form_of, gated by significance-weighting admissibility (spine value or a
  kind independently states it), admitted by constraint closure, with declared defeaters for WordNet misfilings;
  sentence-level sense selection as a constraint problem; senses = equal load-bearing encodings.
- Withdrawn or refuted after measurement: agent-written type->applicability tables (unverified); hub-explication
  silence inherited by subkinds (NSM subkinds use primes their hub never mentions); felt valence from SentiWordNet
  (a classifier); Wiktionary genus identity read from gloss text; WordNet verb categories as primes.
- The SSL controller from Nov 13-24 exists in code (completion.py, residual.py, model_protocol.py,
  reviewed_patterns.py, discovery.py, grounded_rules.py, epoch.py, specification.py, rule_admission.py,
  rule_migration.py) under contract GSE.ssl-construction/2 (SSL-01..11). Its checkpoint and teaching databases were
  deleted today in a disk cleanup; its code and receipts remain.
- Sources on disk: WordNet, Wiktionary, VerbNet, FrameNet, PropBank, USAS, ConceptNet, SentiWordNet, NRC emotion,
  NRC VAD, Lancaster, concreteness; 248 verified NSM explication records (Goddard 2012/2018, Goddard & Wierzbicka
  2007/2014/2016); the NSM prime chart. Per-definition SQL resolution runs at roughly 30-40 definitions/second.
