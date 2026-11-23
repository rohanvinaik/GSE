# Lexicon continuation after the grounded comparison

## Source projection revision

WordNet's exact sense `state.v.01` defines expression in words. Its ancestry supports SAY in explicit expression senses such as `answer.v.01` (verbal reaction) and `articulate.v.05` (clear expression). Three descendant definitions expose a gap in the same inheritance mechanism.

| Exact sense | Own definitional content | Source disposition |
| --- | --- | --- |
| `bridle.v.03` | A horse responds to reins | Withdraw inherited SAY |
| `rent.v.04` | A party holds goods or services under a lease | Withdraw inherited SAY |
| `summarize.v.02` | A text or other object is a summary of something | Withdraw inherited SAY |

The correction applies to the exact stored sense and source definition, including spellings whose evidence attests that sense. The underlying WordNet observations stay available for replay. No sign for the reopened SAY domain follows from the withdrawal. The reclosure preview changed SAY on 20 entries and kept the positive sign on 31 entries for the three expression controls. Other descendants of the ancestry are eligible for their own review.

## Scope for a new BODY implication

The first new rule candidates ask whether an exact definition of a geometric form establishes BODY orthogonality. The native SOMETHING sign gives the proposed premise. The scope warrant comes from the role of the shape in the definition. In each reviewed scope, the relevant form is specified by geometry and applies independently of anatomical structure.

The plane-figure scope includes angles, sides, curves, geometric contours, and the conventional heart-shaped glyph. The geometric sense `heart.n.07` is a held-out question. The organ sense `heart.n.02` already has an independently supported BODY=+1 and remains outside the proposed scope. Diagram-specific definitions, arbitrary objects classified by resemblance, and the anomalous ellipsoid branch stay outside this warrant.

The polyhedron scope covers solids and the higher-dimensional analogue of a cube. A face here is a geometric boundary. The scope excludes the object sense `quadrate.n.01`, whose definition gives an approximation to a cube.

Stage both proposals with relational semantics and use only independently reviewed, disjoint target questions to audit the selected family. Record any failed audit as a typed challenge and retain the proposed rule for scope revision. The whole candidate must replay after an admitted revision.

## Wiktionary person-genus projection

A single native noun definition of the form “a person who …” or “a person that …” identifies a person as its genus. The relative clause supplies the differentiating property. The native parser can therefore supply SOMEONE=+1 for this exact construction. The projection supplies one coordinate. It retains the other supported domains from the ordinary resolver.

The rule requires a single native gloss and declines native references, coordination, and separately punctuated alternatives. One exact sense of *receiver* begins with a person gloss and has a second gloss allowing a company. That contrast motivates the single-gloss requirement. The narrower rule also leaves predicate coordination for a separate syntax review.

The four bounded audit questions used the exact *critic*, *investor*, *student*, and *survivor* definitions. The model returned SOMEONE=+1 on all four. The *student* example coordinates two predicates and stays outside the admitted source pattern. The other three provide held-out checks inside the scope. The source witness is still the exact definition. [Typed audit](wiktionary-person-audit.json)

The stage and apply commands are in `scripts/revise_lexicon_wiktionary_person.py`. The stage is read-only. The apply command recomputes the exact source proofs and domain changes on a replayed successor, requires agreement with the stage, refreshes dependent native discovery, and runs full replay before installing a separate candidate snapshot.

## Wiktionary anatomical genus preview

The preview uses the candidate from the duration catalogue replay. Its source cohort consists of exact Wiktionary noun observations with the native `anatomy` topic and a single gloss. The native GSE parser checks a definite or indefinite article, optional adjectival or adverbial modifiers, and a noun in the declared set of anatomical genus heads. The first screen records 63 witnesses among 925 anatomy noun records.

The immediate token after the genus exposes a scope boundary. The preview retains the end of the gloss, a period, comma, or semicolon, a preposition, or the words `that`, `which`, `whose`, `where`, and `with`. It reserves 12 cases for attachment review. For example, *muscle* is a modifier in the gloss for *fasciculation*. The syntactic result and full native gloss are preserved for each case.

The hypothesis supplies BODY=+1 where the exact definition names an anatomical structure by its genus. Reclosing the 51 narrowed cases under the existing noun relation additionally supplies SOMETHING=+1. The stage records 102 provisional singleton domains and zero solver contradictions. Three separate typed BODY questions selected by SUBTLEX counts across distinct heads agreed on the exact organ sense of *heart*, tendon sense of *tail*, and bone sense of *radius*. The audits establish agreement on those cases. The source projection still requires admission through the normal source revision path. [Refinement](wiktionary-anatomy-genus-refinement.json) · [Stage](wiktionary-anatomy-genus-stage.json) · [Typed audit](wiktionary-anatomy-genus-audit.json)

## Anatomical genus review on the active sparse baseline

The admission scope requires a single exact native gloss, noun part of speech, and the native `anatomy` topic. It also excludes native references, figurative tags, and direct coordination at the genus boundary. This last condition reserves *semilunar*, whose gloss offers two coordinated bone names. Attachment tests still reserve the event gloss *muscle twitch* and the resemblance gloss *muscle-like structure*. These are scope abstentions. Each would need its own warrant before it could supply a bank value.

The remaining 50 definitions identify bodily structures through explicit anatomical genera. Each supplies BODY=+1 through its native observation. The existing noun rule supplies SOMETHING=+1 during closure. The active stage reproduces both proposed changes for each retained definition, with all 100 domains moving from the open ternary domain to +1. The scope review identifies all 13 reserved definitions and the exact stage it reviewed. The new release labels exercise additional native senses of *aorta*, *pancreas*, *uterus*, and both anatomical definitions of *deltoid*. [Active stage](wiktionary-anatomy-active-stage.json) · [Scope review](wiktionary-anatomy-active-scope-review.json) · [Release labels](sparse-release-002-gold.json)

Run `scripts.revise_lexicon_wiktionary_anatomy stage` with the current sparse publication receipt. For `apply`, supply the resulting stage, typed audit from that baseline, and a new database path. The revision regenerates the audit questions, recomputes the staged domains in a private snapshot, and runs full replay. Promote the successor with the sparse publisher after comparing its domains with the active baseline and passing runtime checks.

The fresh audit agreed on all three cases. The admitted revision and isolated publication copy replayed all 401,596 records with zero mismatches. The active successor adds 50 BODY values and 50 SOMETHING values. Its 280,661 explicit zeros are preserved, and 22,083,373 lexical cells remain open. [Revision](wiktionary-anatomy-revision.json) · [Publication](sparse-release-002-publication.json) · [Activation verification](sparse-release-002-activation.json)

## Anatomical attachment refinements

The next scope review accounts for the 13 reserved definitions. It admits bounded disjunctions when both alternatives give an anatomical genus. The gloss for *semilunar* gives two bone names, *median* gives a vein or nerve, and *ossicle* explicitly includes osseous structure. In *quadriceps* and *myometrium*, *having* and *forming* modify the muscle head. The exact compounds *nerve tissue*, *nerve ending*, and *muscle fibre* describe anatomical structures or material. The *foreskin* gloss explicitly identifies a fold of skin after its modifiers.

The event head in *fasciculation*, the historical and relational alternative in *heartstrings*, and the resemblance gloss for *myoid* remain open. Their definitions call for separate warrants. The active-stage scan uses the full declared corpus and returns ten supported definitions. The projected BODY cells and the SOMETHING cells obtained by closure all move from the open domain to +1. Exact native assertions already present on the active baseline stay in their original revision. [Stage](wiktionary-anatomy-refinement-active-stage.json) · [Scope review](wiktionary-anatomy-refinement-scope-review.json)
