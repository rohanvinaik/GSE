# NLTK advisory source triage

Read-only source inspection. No dependency, source, test or waiver changes were made. This record does not declare the audit finding a false positive.

## Follow-up: an available newer release is verified

The subsequent official-latest check found **NLTK 3.10.4** on [PyPI](https://pypi.org/project/nltk/) and [GitHub Releases](https://github.com/nltk/nltk/releases/tag/v3.10.4), published October 21, 2026. Both PyPI release files are not yanked. The complete release body and all six named methods at that tag were read. This establishes an available newer release; the older advisory's empty patched-version field must not be used to conclude that none exists.

| Named API | Guard observed in the v3.10.4 tagged method |
|---|---|
| TransitionParser.train | pathsec_open before model write |
| TransitionParser.parse | pathsec_open before model read |
| AveragedPerceptron.save/load | validate_tool_path and pathsec_open |
| PerceptronTagger.save_to_json | validate_tool_dir before creation, constrained names, guarded write branches |
| save_maxent_params | ensure_private_dir and pathsec_open |

The [tagged parser](https://github.com/nltk/nltk/blob/v3.10.4/nltk/parse/transitionparser.py), [tagger](https://github.com/nltk/nltk/blob/v3.10.4/nltk/tag/perceptron.py), and [maxent](https://github.com/nltk/nltk/blob/v3.10.4/nltk/classify/maxent.py) supply concrete source evidence of the relevant containment changes. This is upgrade evidence, not a false-positive classification of the original 3.10.3 finding. The original range contradiction and 3.10.3 inspection below are retained as history. Compatibility verification and actual dependency changes belong to the lead's separate task.

## Version evidence remains contradictory

The [maintainer advisory GHSA-8mgp-746c-j5xp](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp), alias CVE-2026-81726, reports `<=3.10.3` affected and no patched version. It names `TransitionParser.train`, `TransitionParser.parse`, `AveragedPerceptron.save`, `AveragedPerceptron.load`, `PerceptronTagger.save_to_json` and `save_maxent_params`. The stated preconditions combine enforced path security with untrusted model import/export paths. Its reproduced versions are 3.9.4 and v3.10.0-rc2.

The [OSV record](https://osv.dev/vulnerability/PYSEC-2026-3740) and its [PyPA source YAML](https://github.com/pypa/advisory-database/blob/main/vulns/nltk/PYSEC-2026-3740.yaml) have inconsistent fields: prose includes 3.10.3, while the ecosystem event marks 3.10.3 fixed and the explicit affected list ends at 3.10.2. That contradiction does not establish that the locked release is repaired.

## Tagged implementation and release changes

Complete affected methods and their imports were read at both v3.10.0-rc2 and v3.10.3. In the [v3.10.3 transition parser](https://github.com/nltk/nltk/blob/v3.10.3/nltk/parse/transitionparser.py), training writes its supplied model filename through unqualified `open`; parsing reads its supplied model filename the same way before allowlisted unpickling. The [perceptron module](https://github.com/nltk/nltk/blob/v3.10.3/nltk/tag/perceptron.py) retains unqualified `open` in `AveragedPerceptron.save/load`. The [maxent parameter saver](https://github.com/nltk/nltk/blob/v3.10.3/nltk/classify/maxent.py) retains direct writes to its supplied directory; that whole module has the same SHA256 in the two inspected tags. These observations give no basis to dismiss the package-level finding as a false positive.

The [v3.10.3 release notes](https://github.com/nltk/nltk/releases/tag/v3.10.3) include substantial security hardening. The complete [483c5fe patch](https://github.com/nltk/nltk/commit/483c5fe650542ceaa2b45e8565f72e878834376f) hardens pathsec's POSIX write handling against symlink races and hardens predictable perceptron save locations. Its added tests cover resource-name traversal, pathsec symlink/hardlink handling and the perceptron shared-temp case. Those are concrete changes under a broader advisory umbrella, not evidence that every named raw-model-path method acquired a pathsec wrapper.

The complete four-commit [PR #3744 patch](https://github.com/nltk/nltk/pull/3744) adds an AST guard over corpus/data modules, stabilizes cross-platform tests, and adjusts perceptron saves for Windows. The tagged `save_to_json` uses a pinned private-directory descriptor with O_NOFOLLOW on POSIX and a separate Windows branch. This narrower hardening should not be silently equated with a general model-path containment fix.

## Local production scope

The builder's Python modules have no direct NLTK imports. The complete `NativeSources` implementation reads CSV/text tables and FrameNet/VerbNet XML using the standard library; the `nltk_root` argument names a data directory, not an NLTK model API.

The complete `NativeNLP` class and its helpers were read. Its NLTK import is `nltk.corpus.wordnet`, and its direct WordNet calls are `wn.synsets` and `wn.morphy`. Its invoked degree-morphology helper also uses WordNet lookups. The inspected modules contain no named references to the affected parser/tagger/model-persistence APIs and do not accept model import/export paths through these entry points.

Thus no call to the named vulnerable APIs was identified in these inspected builder/NativeNLP paths. This is a scoped static source finding, not a blanket claim about every optional GSE feature, dependency, deployment or dynamically supplied extension.

Source URLs, full downloaded-file SHA256 values, method locations/AST fingerprints and the exact local import/call inventory are in [nltk-advisory-source-scope.json](nltk-advisory-source-scope.json). Upstream sources and complete patches were downloaded into `/private/tmp/gse-nltk-advisory-20261025/` for inspection. The initial sandbox DNS refusal was retried with required network escalation. No exploit was executed.

## MCP CVE-2026-59951: primary source and scope

The [maintainer advisory GHSA-84m7-p3x7-pcfv](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-84m7-p3x7-pcfv) covers unbounded retained sessions in stateful Streamable HTTP servers. It lists affected ranges `>=1.8.0,<1.30.0` and `>=2.0.0,<2.2.0`, repaired by 1.30.0 and 2.2.0. The exposure requires a reachable stateful Streamable HTTP endpoint; the advisory explicitly excludes stdio, SSE, and supported stateless HTTP operation. Authentication limits who can create sessions, not their count. The described repairs add idle expiry, session limits and cleanup on session termination. This is the specific MCP advisory corresponding to the audit ID; it is separate from the WebSocket Host/Origin advisory CVE-2026-59950.
