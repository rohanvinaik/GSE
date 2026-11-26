# Consultation: the rebuild of the lexicon (2026-11-26, late)

Rohan: "Use the codex API consult. Then ... throw everything in the trash and start over, full new openspec plan and
everything." GPT-6.2 Sol at medium effort over the OpenAI API (key read at runtime from the operator store, never
printed). The prompt held his 175 GSE prompts (2026-11-23..26) and all 160 founder-word sections verbatim, his
TrialLedger founding words and theory of the case, Data Geometry (Part I; patterns 6, 7, 10, 14, 16), Significance
Weighting (sections 4-7b, 10-16.7), the SSL paper (thesis to the completeness equation), Negative Specification
(abstract; regions; automation boundary; censors), sparse-wiki (sections 1-1.4) and the current state. No NSM
reference text was sent. Claude's reading was written before the answer was opened
(`claude-reading-before-codex.md`). Usage: `codex-metadata.json` (79,740 input and 6,742 output tokens).

Where Codex and Rohan's words differ, his words govern. One difference is settled by him already: Codex suggests
reusing bounded old components (the arc-consistency kernel, `ledger.py`); Rohan ordered everything thrown away and,
on 2026-11-24 01:06, rejected "a 'lexicon builder' that's just a wrapper that uses code from the older one". The
rebuild therefore writes those mechanisms afresh from his documents; the source parsers (AGENTS.md design
constraint), the raw data, the records and the live lexicon stay.
