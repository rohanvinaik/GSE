# Research packets, 2026-10-25

Facts gathered by sub-agents for the work after the first checkpoint (F160). They state what the sources say, with locations; they decide nothing. The hash of every packet file is in `SHA256SUMS.json`.

| Packet | What it holds | Used for |
|---|---|---|
| `noun-facts/` | For 33 nouns (box, dog, cat, teacher, person, child, crowd, family, team, group, hand, arm, finger, head, glove, wheel, handle, door, kind, type, species, category, idea, love, freedom, truth, time, place, house, water, body, part, people): the builder's native records, USAS tags with their `semtags.txt` labels, FrameNet noun lexical units with frame definitions, frame elements, core types, incorporated elements and semantic types, and WordNet 3.0 lexicographer classes. `source_manifest` holds each source's path and hash. | The noun head contract (F160). |
| `nsm-prime-facts/` | For the 41 remaining NSM-mapped primes: their chart box lines and quoted statements from G12, LFH22 and GW2014 (with page and line), how the sources separate the primes GSE merges (SAME/OTHER, the two BE primes, HAVE and PART, THERE IS), and where VERY and MORE combine. `meta` records what was read and what was not. | Examining the remaining primes (F160). |
| `adaptation-facts/` | For the GSE-adaptation coordinates (QUANTITY, INFER, ALIVE, THEN, START, OUTSIDE, TOWARD, WITH, MUST, CAUSE, TRUE, HIER±, INTENSITY, CERTAINTY) and NUMBER: every statement in the code, rulebook, foundation, design, founder record and Rohan's papers, quoted with file and line and tagged by speaker, plus 27 contradictions set side by side with no verdict. The worktree changed while it was read (CAUSE above all); `source_snapshot` records each cited file's size and time. | Written GSE definitions before those coordinates are examined (F160). |

The scripts that produced each packet are beside it. The sources themselves are in `data/external` and `data/external/references` (git-ignored).
