# RohanVoice compatibility consumer, version 2

`scripts/rohan_voice.py` is a separately versioned nearest-centroid recognizer.
It consumes a bounded legacy feature projection of GSE. It is not the complete
source-agnostic read/compare instrument now owned by SquishOS.

`scripts/voice_profile.py` is retired to an explicit migration stub. Its command
prints the replacement read/compare routes and exits 2; its old Python `profile`
raises `RetiredProfileError`. It no longer imports personal-wiki or produces an
incomplete profile under the former name. This retirement follows verification
of the replacement read and compare entry points.

The dense-vector/cosine option and `authentic_similarity` output are removed.
The feature layout keeps ordered bank proportions, selected primitive presence,
and the existing first/second-person and framing markers, under the new identity
`gse.rohan-voice-features/2`. Words use the actual `NativeNLP` lemma and shared
first-ID lexical lookup. Distinct lexical senses are not merged by an independent
SQL query. The projection records primes/no-primes/no-row/unread populations and
refuses classification features when their lexical observations are unavailable.
It retains its legacy eligibility rule of alphabetic source tokens of length at
least three; this limited projection does not claim the full instrument's every-word
coverage. The old style-feature names remain explicit legacy formulas.

## Explicit source and holdout manifest

Fit requires one named manifest. There is no default private corpus, corpus scan,
filename-based label map, or fallback `authored` label. Every source record must
declare its exact byte hash, label and split:

```json
{
  "schema": "gse.rohan-voice-sources/2",
  "sources": [
    {"path": "authored-train.txt", "label": "authored", "split": "train", "sha256": "<exact source SHA-256>", "group": "authored-source-a", "selection": {"method": "human_review"}},
    {"path": "authored-holdout.txt", "label": "authored", "split": "holdout", "sha256": "<exact source SHA-256>", "group": "authored-source-b", "selection": {"method": "human_review"}},
    {"path": "llm-train.txt", "label": "llm", "split": "train", "sha256": "<exact source SHA-256>", "group": "control-source-a", "selection": {"method": "unfiltered"}},
    {"path": "llm-holdout.txt", "label": "llm", "split": "holdout", "sha256": "<exact source SHA-256>", "group": "control-source-b", "selection": {"method": "unfiltered"}}
  ]
}
```

Paths resolve relative to the manifest. Supported labels are `authored`,
`personal`, and `llm`. At least two declared classes are required, with a training
and heldout observation for each. UTF-8 decoding is strict. Duplicate source paths,
duplicate content, source-hash changes, malformed labels/splits, missing holdouts
and unread features refuse fitting before replacing any artifact. Label decisions
come from the manifest's author; the recognizer does not infer source authorship.

Every source must declare an independence `group` and selection evidence. Paths
and distinct hashes alone do not establish independence. Related excerpts stay
in one group, and a group cannot occur in both train and holdout. Missing groups
return `independence_groups_required`; missing selection evidence is refused.
Selection methods are `human_review`, `unfiltered`, or `recognizer`. The last
requires the selecting artifact's `artifact_sha256`; those selected sources may
train but cannot serve as independent holdout. Reused groups, duplicated content
and selection/evaluation overlap refuse fitting before feature extraction.
These are declared source groups, not an independently verified authorship claim.

Training statistics and centroids consume only `train` records. Holdouts receive
per-class `identified`, `wrong`, and `abstained` counts. No holdout success is
invented when examples are absent, and no single accuracy number replaces those
class reports. The artifact stores source identities without copying their prose.

Both fitting and successful recognition expose an `evaluation` receipt containing
the retained per-class holdout counts, declared groups and selection policy.
Its `heldout` state is conditional on those supplied independence declarations.
A malformed or overlapping stored source manifest requires refitting instead of
retaining a fabricated grade.

```sh
.venv/bin/python scripts/rohan_voice.py --fit /path/to/manifest.json --model /path/to/model.v2.json
.venv/bin/python scripts/rohan_voice.py /path/to/input.txt --model /path/to/model.v2.json
```

The default new artifact is `data/voice/model.v2.json`. Source and output paths
cannot collide. Persistence uses a flushed temporary file and atomic replacement.
No refit of the user's private corpus is performed by this migration.

## Artifact identity and recognition

Artifacts carry `gse.rohan-voice/2`, the complete feature layout/policy, source and
manifest hashes, actual feature-producer code hashes, selected lexicon hash,
NLTK version and WordNet resource hash. Runtime `GSE_REPO`/`GSE_LEXICON` changes
select and identify the resources actually consumed. Model output and prose
documentation do not affect feature identity. Code or resource changes require
refitting; old `model.json` artifacts are never relabeled as current.

`recognize(text, model_path=None)` returns `refit_required` for missing, legacy,
malformed or stale artifacts. A current artifact returns `identified` or
`abstained`; an exact centroid tie abstains. Empty/unread feature populations keep
their own states. Distances are Euclidean in the versioned standardized feature
space. Compatibility `scores` are normalized `exp(-distance)` weights, explicitly
not calibrated probabilities; `is_rohan` is their authored-plus-personal sum and
does not establish authorship. The complete voice reader may report the optional
recognizer unavailable without failing the core reading.
