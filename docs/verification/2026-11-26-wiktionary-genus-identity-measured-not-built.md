# Wiktionary genus identity: measured, not built (2026-11-26)

Question: can the approved WordNet identity roots reach Wiktionary noun definitions through each gloss's genus
(the head noun before its first qualifier), writing identity only when every WordNet noun sense of the genus
projects the same identity (`WordNetHierarchyParser.to_primitives_for_definition`)?

Measured over the live release: 130,773 Wiktionary noun definitions; 24,844 would gain identity (37,482 new
cells, 0 collisions with stored values; 56,193 have an ambiguous or unknown genus, 44,848 no article).

Not built. The head is often misread from free text: "A rough or violent event" -> rough; "a person born outside
of Japan" -> outside; "The gene encoding for lysyl oxidase" -> encoding; "A winding or spiral staircase" ->
winding. Reading a genus off free text is the gloss composition removed earlier, and zero collisions on
definitions this thin is not evidence. The approved Wiktionary projections (a literal "A person who/that ...",
named anatomical genera) stay the only genus rules.
