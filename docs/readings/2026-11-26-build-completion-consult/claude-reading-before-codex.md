# My reading, written before Codex's (2026-11-26)

## What Rohan has said he wants
- A complete lexicon: every definition's 56 banks decided (+-1, explicit 0, silence), "not 1-2 banks per word"
  (11-25 07:15, 07:22 "Lexicon no have stuff / Me want stuff").
- Built symbolically: sources + rules + constraint propagation, inspectable; the model only on a bounded typed tail
  (F066/F078: choose among the few surviving options; F148: tail = disagreement with NSM per word/bank/rule).
- SSL-driven: each teaching collapses the space through propagation; dH/dt = -(N_ext + N_ind + C(H)); hubs first by
  kappa; structural amplification (F067 "each selection exponentially collapses the state space").
- Coherence (senses = equal load-bearing encodings), significance weighting (true / conditional / exception tiers;
  conditional rules from stable cross-dataset coherence, F101/F108), negative specification (confident zeros are core;
  orthogonal -> 0 at 17:56), positive identity, NSM research as the definitional source extended to the language,
  sub-kind propagation, no statistics deciding a value, no gloss parsing.

## What exists
- Live senses6: ~8-9% of the 22.5M definition cells decided; senses carry 149,883 nonzero values over 110,678
  senses (~1.4 per sense); NSM agreement 50 agree / 7 / 305 missing on 35 explications.
- Pieces built today, each covering 10^3-10^5 cells: four-state engine, F088 reading, primes/function words,
  valency zeros (measurement only), NSM molecule inheritance (4,464 sense cells), sub-kind inheritance (63,638 def
  cells), clause selection.
- The SSL controller from Nov 13-24 is in code (completion, residual, model_protocol, reviewed_patterns, discovery,
  epoch, specification; contract gse.ssl-construction/2, SSL-01..11), but I have been working beside it, rule by
  rule, instead of running it; today I also deleted its checkpoint and teaching databases with the stale copies.

## What is actually required (my reading)
- One joint constraint network over all ~22.5M (definition, bank) cells, propagated corpus-wide in one pass
  (vectorised bitset domains, seconds per round), coupling: intra-definition bank laws and admitted conditional
  rules; inter-definition structure (IS-A defaults, synonymy equality, antonym sign flip, derivation by POS pair,
  entailment); source projections; sense coherence; type applicability (orthogonal -> 0).
- The SSL loop at that scale: mine candidate rules over the whole population in a declared rule language
  (conjunctions of bank signs, source fields and type guards -> a target sign/zero), gate by significance weighting
  (spine-confirmed, plurality retained, kappa > 0) and negative specification (zeros only from warranted censors),
  admit hubs first by kappa, propagate jointly, record counterexamples as guard refinements/exceptions, repeat until
  kappa -> 0.
- Teaching for what rules cannot reach: questions chosen by expected closure (one answer -> thousands of cells
  through admitted rules), at the TYPE level where possible (type x bank applicability, one answer per type
  propagated to every member), answered by NSM gold or the bounded model; each answer re-enters as a premise and a
  rule candidate. Measure joint bits each round.
- My failure: working word-by-word and rule-by-rule at 10^3-10^5 cells, with per-definition SQL solves that take
  minutes, instead of running the population-scale loop the contract already specifies.
