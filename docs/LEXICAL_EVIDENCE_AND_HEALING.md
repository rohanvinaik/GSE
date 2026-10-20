# Lexical evidence and source-preserving healing

The accepted `preserve-typed-prose-readings` change adds these public surfaces.
These are evidence channels, not substitutes for a successful sentence reading.

## Lexical and frequency facts

`gse.lexical_evidence.lookup_lexeme(word, db_path=None, pos=None)` opens the
lexicon read-only and returns `primes`, `no_primes`, `no_row`, or `unread`.
The selected row, all candidate rows, primitive rows, source metadata, resource
hash and selection policy remain inspectable. A row with no active primes is
an observed zero lexeme, not a missing word. The runtime data uses normalized
lowercase lemmas and its lemma index; selection defaults to ascending row ID,
matching the encoder. An explicit `pos` request prefers that POS over generic
rows, a separately declared policy. Neither policy resolves word senses.

`FrequencyDatabase.evidence(word, applicable=True)` exposes the named
`david47k_rank` separately from `local_rank`. Its states are `ranked`,
`unranked`, `not_applicable`, and `unread`. A local rank never substitutes for a
missing general-English rank. This evidence API neither uses the legacy
maximum-rank fallback nor creates an absent database. Existing weighting APIs
retain their compatibility behavior.

The spelling lexicon's `rarity_evidence(word)` separately returns `unread`,
`not_rare_tail`, or `rare_tail`. Its combined usage ranks are loaded read-only;
missing/malformed sources never become observed absence and never create a
database. `rare_tail` means a broad-wordlist-only form has no observed combined
rank, licensing a local slot check rather than proving zero usage or a typo.
The legacy `is_rare_tail` Boolean conservatively projects unread to false.
Healing records unread admission as `kept` with `rarity_unread` evidence.

## Optional raw resources

`raw_vad(word, path=None, version=None)` and `raw_concreteness(word, path=None)`
read local files only, returning `measured`, `absent`, or `unread`, with the
resource byte hash and raw values. Acquisition is an explicit separate task;
these functions never invoke a curation parser's downloader.

NRC VAD has incompatible release scales: v1 uses 0..1, while v2 uses -1..1.
The supported v1 `Word` and v2 `term` headers declare the format family;
headerless exports require explicit `version="1"` or `"2"`. Unrecognized
headers, conflicting declarations, malformed rows, duplicate words and values
outside the declared scale report unread. The exact subversion of the local
file is not certified by its header. The scale is never inferred from observed
minimum/maximum values. The v2 scale is documented in the author's
[v2 paper, introduction and aggregation section](https://arxiv.org/html/2503.23547v1);
the [resource page](https://saifmohammad.com/WebPages/nrc-vad.html) also retains
its older v1 summary.

Concreteness keeps its 1..5 score, source-supplied known-word statistic and
actual rater count when present (`Total`/`N`). Missing metadata stays null.
`metadata_columns` identifies the original columns: values from
`Percent_known` or `%known` are retained exactly, without inventing their units
or normalizing them. No estimated count is reported as measured.

`structural_epa(signature)` wraps `gse.prime_projection.epa_projection` and
reports silence as absent. It never substitutes lexical VAD. Resource hashes
and immutable parsed tables are cached under path/stat identity; file changes
invalidate dependent resource readings.

## Protected dictionary and semantic review

`gse.curation.personal_dictionary.entries(path=None)` returns typed immutable
entries with `surface`, `kind=term|name`, aliases, optional definition,
`source=confirmed|draft|learned`, review status, and separate semantic status.
`membership` and `identity` return explicit absent/unread evidence. The default
store is `gse/nlp/data/personal_dictionary.json`; an absent historical store
stays absent until learning. The older project allowlist remains a spelling
protection source and is not recast as an authored semantic dictionary.

`learn(entry, path=None, drafts=None)` validates requests and existing stores,
merges duplicate display surfaces deterministically, unions aliases, and
refuses an alias already owned by another entry. Confirmed definitions and
review metadata win conflicts. Definition provenance is carried separately in
`definition_source`: confirming a spelling cannot certify a retained draft
definition. Writes use a process lock, flushed temporary
file and atomic replacement; failed replacement leaves the original intact.
Cache identities change on learning, including aliases. Unicode, multiword
terms and names are supported; digits, markup, control characters and unknown
fields are refused in dictionary entries.

Optional independent decomposition drafts pass through
`validated_concurrence`: each draft and the agreed intersection must satisfy
the word-scale constraints. Disagreement remains visible and a valid result
still requires review. Learning never writes primitives or marks semantic
validation complete. No absent historical drafts or definitions are recreated.

## One healing operation

`gse.nlp.heal.suggest(text, n=5, original_text=None, source_map=None,
dictionary_path=None)` is the reusable operation. It accepts exact decoded text
or strict UTF-8 bytes, preserving CRLF. Invalid UTF-8 is an explicit refusal.
The spelling MCP's `spell_suggest` delegates to this core; `spell_learn`
delegates to `heal.learn`. The core imports no MCP transport.

The standalone `python -m gse.nlp.spellcheck_repl --json "text"` command emits
the same complete result. One quoted argument retains its exact source text;
the interactive presentation renders that result without a separate correction
policy or token reconstruction.

The core preserves the existing word, contextual, entity and keyboard-HDC
legs, behind protection guards. Valid words, typed terms/names/aliases,
non-ASCII forms, digits, units, compounds, code and markup are preserved.
Rare-tail recovery remains restricted to the existing supported predicate
slot/common-target rule. A name candidate needs independent anchor
corroboration or unique ranked word-space confirmation in addition to the
entity leg's commitment. A decisive entity prior alone remains an offer:
Papert must not become Appert. The clear Einstein recovery remains supported.

`heal.resource_provenance()` identifies the actual module-bound spelling
resources, including WordNet version/source, Wiktionary wordlist, usage ranks,
allowlist, misspellings, entity/anchor dictionaries and keyboard-HDC cache.
Call it before reading in a fresh process and again for the final receipt.
Each file retains the process snapshot, current byte identity and cache state.
Already loaded caches are `unverified_cache` if their identity was not observed
before loading; changed bytes behind a loaded cache report `stale` with both
identities. Optional missing sources and unhashed directories remain named.
These caches live for the process; restart after changing their resources.
The protected dictionary retains its separate dynamic invalidation policy.

Each ledger record includes an exact input span, original/replacement text,
original-source span when aligned, leg, evidence, decision and reason. Decisions
are `kept`, `offered`, `applied`, or `refused`. The result identifies input,
original and measured hashes, policy and dictionary identity, and before/after
sentence manifests. Output is produced from exact source slices, never by
joining tokens. `apply_edits` refuses malformed, unaligned, overlapping or
interior-insertion conflicts and preserves every unaffected UTF-8 byte.

For reduced prose, `source_map` is a monotone list of
`{"reduced": [start,end], "original": [start,end]}` retained segments, using
half-open Unicode code-point coordinates. A segment must reproduce the exact
source slice. Edits that cross removed markup, discontinuities or ambiguous
segments are refused. `original_corrected` applies approved edits back to the
original source without changing excluded bytes.

`boundaries(text, apply=False, evidence=None)` offers potential missing stops.
A capital alone never licenses an automatic sentence-count change. Applying
requires an explicit licensed `complete_clause_before_independent_clause`
witness at the gap; both sentence manifests and the located insertion remain
in the ledger. The function does not certify arbitrary clause boundaries.

Compatibility deltas: punctuation/whitespace are no longer normalized by the
MCP, unknown names may now remain offered, and `under` is no longer proposed as
negative `der`. Morphology policy details are recorded in the research brief.
