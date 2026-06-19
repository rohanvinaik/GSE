#!/usr/bin/env python3
"""
GSE Encoder API.

Encodes natural language to HDC vectors with full operation trace.
Produces JSON-serializable traces for verification and debugging.

Key feature: Dynamic syntactic role assignment from spaCy dependency parsing.
This ensures that argument order matters (dog as subject vs dog as object).
"""

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gse.api.errors import OOVError, PrimitiveError
from gse.api.parse_repair import verbs_to_promote
from gse.api.trace import (
    ClauseSpan,
    OperationTrace,
    OperatorTrace,
    TokenTrace,
)
from gse.symbolic.tiers import is_clause_linking
from gse.vectors_v2 import (
    SparseVector,
    bind,
    bundle,
    create_basis,
    create_sentence_basis,
    permute,
)

# Dynamic syntactic role mappings from spaCy dependency labels
# Based on Universal Dependencies schema - see sentence_parser.py for full docs
DEP_TO_SYNTACTIC = {
    # Core arguments (Bank 0: CORE_STRUCTURE)
    "nsubj": "SYN_SUBJ",
    "nsubjpass": "SYN_SUBJ",
    "csubj": "SYN_SUBJ",
    "csubjpass": "SYN_SUBJ",
    "agent": "SYN_SUBJ",

    "ROOT": "SYN_PRED",
    "root": "SYN_PRED",

    "dobj": "SYN_OBJ",
    "obj": "SYN_OBJ",
    "iobj": "SYN_OBJ",
    "pobj": "SYN_OBJ",

    "attr": "SYN_COMPL",
    "acomp": "SYN_COMPL",
    "xcomp": "SYN_COMPL",
    "ccomp": "SYN_COMPL",
    "oprd": "SYN_COMPL",

    # Modifiers (Bank 1: MODIFICATION)
    "amod": "SYN_ADJ_MOD",
    "nmod": "SYN_ADJ_MOD",
    "nn": "SYN_ADJ_MOD",
    "compound": "SYN_ADJ_MOD",

    "advmod": "SYN_ADV_MOD",
    "npadvmod": "SYN_ADV_MOD",
    "neg": "SYN_ADV_MOD",

    "det": "SYN_DET",
    "predet": "SYN_DET",
    "poss": "SYN_DET",
}

# TAM (Tense-Aspect-Mood) from morphological features
MORPH_TO_TAM = {
    "Tense=Past": "SYN_TENSE_PAST",
    "Tense=Pres": "SYN_TENSE_PRES",
    "Aspect=Perf": "SYN_ASPECT_PERF",
    "Aspect=Prog": "SYN_ASPECT_PROG",
}


class GSEEncoder:
    """
    Encode natural language to HDC vectors with full operation trace.

    Usage:
        encoder = GSEEncoder()
        trace = encoder.encode("The dog is cuter than the cat")
        print(trace.to_json())

    Strict Mode:
        encoder = GSEEncoder(strict=True)
        # Raises OOVError for unknown words instead of silent fallback

    Fallback Behavior (default, strict=False):
        - OOV words: Return empty primitives, contribute zero to vector
        - Invalid primitives: Skip silently
        - Failed operators: Return None for operator result
    """

    def __init__(self, db_path: str = "data/lexicon.db", strict: bool = False):
        """
        Initialize encoder with bases and database.

        Args:
            db_path: Path to lexicon database
            strict: If True, raise exceptions for OOV words and errors.
                    If False (default), use graceful fallbacks.
        """
        self.db_path = Path(db_path)
        self.strict = strict

        # Load HDC bases
        self.word_basis = create_basis()
        self.sent_basis = create_sentence_basis()

        # Load spaCy (lazy import — keeps gse.api importable in test/analysis
        # environments that don't have spacy installed)
        import spacy
        self.nlp = spacy.load("en_core_web_sm")

        # Database connection
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def encode(self, text: str) -> OperationTrace:
        """
        Encode text to HDC vector with full operation trace.

        Args:
            text: Input text (sentence)

        Returns:
            OperationTrace with all encoding steps
        """
        # 1. Tokenize
        doc = self.nlp(text)

        # 1b. Upstream parse repair: spaCy mistags some verbs as nouns
        #     ("Macbeth murders Duncan"). Promote buried verbs to POS=VERB so the
        #     position-based EVENT synthesis downstream finds a predicate.
        promote_to_verb = verbs_to_promote(doc)

        # 2. Process each token
        token_traces: List[TokenTrace] = []
        token_vectors: List[Tuple[int, SparseVector, Dict]] = []
        operator_indices: List[int] = []

        for i, tok in enumerate(doc):
            # Lexicon lookup (static primitives from database)
            word_prims, sent_prims, comp_meta = self._lookup_lexeme(tok.lemma_.lower())

            # DYNAMIC: Replace core syntactic role primitives based on dependency parsing
            # This ensures argument order matters (dog as SUBJ vs dog as OBJ)
            # The dynamic primitives OVERRIDE static ones for core roles
            dynamic_sent_prims = self._extract_dynamic_primitives(tok)

            # Remove static core role primitives - dynamic parsing is authoritative
            core_roles = {"SYN_SUBJ", "SYN_OBJ", "SYN_PRED", "SYN_COMPL"}
            sent_prims = {k: v for k, v in sent_prims.items() if k not in core_roles}
            sent_prims = {**sent_prims, **dynamic_sent_prims}

            # Encode vectors
            word_vec = self._encode_word_primitives(word_prims)
            sent_vec = self._encode_sent_primitives(sent_prims)

            # Compose: word_full = bundle([word_vec, sent_vec])
            # Using bundle() instead of bind() to preserve both signals
            # (bind() destroys signal when word-scale and sent-scale are orthogonal)
            if word_vec.nnz > 0 and sent_vec.nnz > 0:
                full_vec = bundle([word_vec, sent_vec])
            elif word_vec.nnz > 0:
                full_vec = word_vec
            elif sent_vec.nnz > 0:
                full_vec = sent_vec
            else:
                full_vec = SparseVector.zeros(self.word_basis.dimension)

            # Create token trace
            is_operator = bool(comp_meta.get("comp_primitive"))
            token_trace = TokenTrace(
                token=tok.text,
                lemma=tok.lemma_.lower(),
                pos=("VERB" if i in promote_to_verb else tok.pos_),
                position=i,
                word_primitives=word_prims,
                sent_primitives=sent_prims,
                word_vec_nnz=word_vec.nnz,
                sent_vec_nnz=sent_vec.nnz,
                full_vec_nnz=full_vec.nnz,
                is_operator=is_operator,
                comp_primitive=comp_meta.get("comp_primitive"),
                comp_operation=comp_meta.get("comp_operation"),
                comp_arity=comp_meta.get("comp_arity", 0),
            )
            token_traces.append(token_trace)
            token_vectors.append((i, full_vec, comp_meta))

            if is_operator:
                operator_indices.append(i)

        # 3. Plan clauses (sequential because/so splits + embedded relative
        #    clauses), then resolve operators within their innermost clause.
        n_tokens = len(token_vectors)
        op_meta = [
            (op_idx, token_vectors[op_idx][2].get("comp_operation"))
            for op_idx in operator_indices
        ]
        sequential = self._segment_clauses(n_tokens, op_meta)
        embedded = self._detect_embedded_clauses(doc)

        # An embedded clause forces clause planning even without a sequential
        # boundary: synthesize a single implicit main clause to hang it on.
        if embedded and not sequential:
            sequential = [(0, 0, n_tokens)]

        # Unify into planned spans: (clause_id, start, end, kind, parent_id,
        # attaches_to). Sequential clauses keep ids [0..k); embedded follow.
        planned: List[Tuple[int, int, int, str, Optional[int], Optional[int]]] = [
            (cid, s, e, "sequential", None, None) for cid, s, e in sequential
        ]
        next_id = len(sequential)
        gap_roles: Dict[int, Optional[str]] = {}  # clause_id → relativizer gap role
        for s, e, kind, attaches, gap_role in embedded:
            parent = next(
                (cid for cid, ps, pe, k, _, _ in planned
                 if k == "sequential" and ps <= attaches < pe),
                0,
            )
            # A complement whose clause sits in a *different* sequential clause
            # than its matrix verb is really a so/because-linked clause (spaCy
            # tags the consequence verb as ccomp); the clause-linker owns it.
            if kind == "complement":
                span_clause = next(
                    (cid for cid, ps, pe, k, _, _ in planned
                     if k == "sequential" and ps <= s < pe),
                    parent,
                )
                if span_clause != parent:
                    continue
            planned.append((next_id, s, e, kind, parent, attaches))
            gap_roles[next_id] = gap_role
            next_id += 1

        def _innermost_of(pos: int) -> Optional[tuple]:
            """Smallest planned span containing pos (embedded beats parent)."""
            best = None
            for span in planned:
                _, s, e, _, _, _ = span
                if s <= pos < e and (best is None or (e - s) < (best[2] - best[1])):
                    best = span
            return best

        def _sequential_of(pos: int) -> Optional[Tuple[int, int, int]]:
            for cid, s, e in sequential:
                if s <= pos < e:
                    return (cid, s, e)
            return None

        # Token positions inside any embedded clause — kept out of a parent
        # operator's arguments (but an operator inside the embedded clause keeps
        # its own tokens).
        embedded_tokens_by_clause: Dict[int, set] = {
            cid: set(range(s, e))
            for cid, s, e, k, _, _ in planned if k != "sequential"
        }
        all_embedded_tokens = set().union(
            *embedded_tokens_by_clause.values()
        ) if embedded_tokens_by_clause else set()

        operator_traces: List[OperatorTrace] = []
        operator_results: List[SparseVector] = []
        op_trace_index: Dict[int, int] = {}  # op_idx → index in operator_traces
        op_clause: Dict[int, int] = {}        # op_idx → innermost clause_id

        for op_idx in operator_indices:
            _, _, comp_meta = token_vectors[op_idx]
            operation = comp_meta.get("comp_operation")
            arg1_range: Optional[Tuple[int, int]] = None
            arg2_range: Optional[Tuple[int, int]] = None

            if planned and operation and is_clause_linking(operation):
                # Operands are the sequential clauses left/right of the
                # connective — whole clauses, not raw token spans.
                left = _sequential_of(op_idx - 1)
                right = _sequential_of(op_idx + 1)
                if left:
                    arg1_range = (left[1], left[2])
                if right:
                    arg2_range = (right[1], right[2])
            this_clause_id: Optional[int] = None
            if planned:
                inner = _innermost_of(op_idx)
                if inner:
                    this_clause_id = inner[0]
            if planned and not (operation and is_clause_linking(operation)):
                # Within-clause operator: restrict args to its innermost clause
                # (so a THAN inside a relative clause stays inside it).
                c = _innermost_of(op_idx)
                if c:
                    op_clause[op_idx] = c[0]
                    arg1_range = (c[1], op_idx)
                    arg2_range = (op_idx + 1, c[2])

            # Keep embedded-clause tokens out of this operator's args, except
            # the operator's own embedded clause.
            excluded = set(all_embedded_tokens)
            if this_clause_id in embedded_tokens_by_clause:
                excluded -= embedded_tokens_by_clause[this_clause_id]

            op_trace, result_vec = self._resolve_operator(
                op_idx, comp_meta, token_vectors, token_traces,
                arg1_range, arg2_range, excluded,
            )
            if op_trace:
                op_trace_index[op_idx] = len(operator_traces)
                operator_traces.append(op_trace)
                if result_vec and result_vec.nnz > 0:
                    operator_results.append(result_vec)

        # Build the clause spans for the trace (only when actually planned).
        clauses: List[ClauseSpan] = []
        for cid, s, e, kind, parent_id, attaches in planned:
            within = [
                op_trace_index[oi]
                for oi in operator_indices
                if oi in op_trace_index
                and op_clause.get(oi) == cid
            ]
            clauses.append(
                ClauseSpan(
                    clause_id=cid, token_start=s, token_end=e,
                    operator_indices=within, kind=kind,
                    parent_id=parent_id, attaches_to_token=attaches,
                    gap_role=gap_roles.get(cid),
                )
            )

        # 4. Position encoding + bundling
        components: List[SparseVector] = []

        for i, (pos, full_vec, _) in enumerate(token_vectors):
            if full_vec.nnz > 0:
                # Apply positional permutation
                positioned = permute(full_vec, shift=pos * 100)
                components.append(positioned)

        # Add operator results
        components.extend(operator_results)

        # Bundle all components
        if components:
            sentence_vec = bundle(components)
        else:
            sentence_vec = SparseVector.zeros(self.word_basis.dimension)

        # 5. Compute primitive activations
        word_activations = self._compute_primitive_activations(
            sentence_vec, self.word_basis
        )
        sent_activations = self._compute_primitive_activations(
            sentence_vec, self.sent_basis
        )

        # 6. Compute vector hash
        vector_hash = self._hash_vector(sentence_vec)

        # 7. Create trace
        trace = OperationTrace(
            input_text=text,
            tokens=token_traces,
            operators=operator_traces,
            final_nnz=sentence_vec.nnz,
            sparsity=sentence_vec.sparsity,
            word_primitive_activations=word_activations,
            sent_primitive_activations=sent_activations,
            vector_hash=vector_hash,
            clauses=clauses,
        )
        trace.vector = sentence_vec

        return trace

    def encode_batch(self, texts: List[str]) -> List[OperationTrace]:
        """Batch encoding."""
        return [self.encode(t) for t in texts]

    def _extract_dynamic_primitives(self, tok) -> Dict[str, int]:
        """
        Extract dynamic syntactic primitives from spaCy token.

        This is the key to argument-order sensitivity. By binding word vectors
        with their syntactic roles (SUBJ vs OBJ), we ensure that:
        - "The dog is cuter than the cat" ≠ "The cat is cuter than the dog"

        The formal semantics basis: CCG/Montague-style function application
        where syntactic position determines semantic role.
        """
        primitives = {}

        # Map dependency label to syntactic primitive
        if tok.dep_ in DEP_TO_SYNTACTIC:
            syn_prim = DEP_TO_SYNTACTIC[tok.dep_]
            primitives[syn_prim] = 1

        # Extract TAM (Tense-Aspect-Mood) from morphology
        morph_str = str(tok.morph)
        for morph_feat, tam_prim in MORPH_TO_TAM.items():
            if morph_feat in morph_str and tam_prim:
                primitives[tam_prim] = 1

        return primitives

    def _lookup_lexeme(self, lemma: str) -> Tuple[Dict[str, int], Dict[str, int], Dict]:
        """
        Look up word-scale and sentence-scale primitives for a lemma.

        Fallback behavior (strict=False): Returns ({}, {}, {}) for OOV words
        Strict behavior (strict=True): Raises OOVError for OOV words
        """
        # Get lexeme ID and compositional metadata
        self.cursor.execute("""
            SELECT id, comp_primitive, comp_arity, comp_operation
            FROM lexemes WHERE lemma = ? LIMIT 1
        """, (lemma,))
        row = self.cursor.fetchone()

        if not row:
            if self.strict:
                raise OOVError(lemma)
            return {}, {}, {}  # Graceful fallback: OOV word contributes nothing

        lexeme_id, comp_prim, comp_arity, comp_op = row
        comp_meta = {
            "comp_primitive": comp_prim,
            "comp_arity": comp_arity or 0,
            "comp_operation": comp_op,
        } if comp_prim else {}

        # Get word-scale primitives
        self.cursor.execute("""
            SELECT primitive, value FROM primitive_values
            WHERE lexeme_id = ? AND value != 0
        """, (lexeme_id,))
        word_prims = {row[0]: row[1] for row in self.cursor.fetchall()}

        # Get sentence-scale primitives
        self.cursor.execute("""
            SELECT primitive, value FROM sentence_primitive_values
            WHERE lexeme_id = ? AND value != 0
        """, (lexeme_id,))
        sent_prims = {row[0]: row[1] for row in self.cursor.fetchall()}

        return word_prims, sent_prims, comp_meta

    def _encode_word_primitives(self, primitives: Dict[str, int]) -> SparseVector:
        """
        Encode word-scale primitives into a vector.

        Fallback behavior: Returns zero vector for empty primitives,
                          skips invalid primitives silently.
        Strict behavior: Raises PrimitiveError for invalid primitives.
        """
        if not primitives:
            return SparseVector.zeros(self.word_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.word_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)
            elif self.strict:
                raise PrimitiveError(prim)
            # else: silently skip invalid primitive (graceful fallback)

        if not components:
            return SparseVector.zeros(self.word_basis.dimension)

        return bundle(components)

    def _encode_sent_primitives(self, primitives: Dict[str, int]) -> SparseVector:
        """
        Encode sentence-scale primitives into a vector.

        Fallback behavior: Returns zero vector for empty primitives,
                          skips invalid primitives silently.
        Strict behavior: Raises PrimitiveError for invalid primitives.
        """
        if not primitives:
            return SparseVector.zeros(self.sent_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.sent_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)
            elif self.strict:
                raise PrimitiveError(prim)
            # else: silently skip invalid primitive (graceful fallback)

        if not components:
            return SparseVector.zeros(self.sent_basis.dimension)

        return bundle(components)

    def _segment_clauses(
        self,
        n_tokens: int,
        op_meta: List[Tuple[int, Optional[str]]],
    ) -> List[Tuple[int, int, int]]:
        """Partition the token stream into clause spans at clause boundaries.

        ``op_meta`` is ``[(op_idx, operation), ...]`` for every operator token.
        A clause-linking operator (CONSEQUENCE, CAUSAL_SOURCE, …) is a boundary:
        the connective token belongs to no clause, and the tokens on either side
        form separate clauses.

        Returns an ordered list of ``(clause_id, token_start, token_end)`` with
        ``token_end`` exclusive, or ``[]`` when there is no clause-linking
        operator (a single implicit clause — the existing single-clause path
        handles it unchanged). M1 segments on clause-linking operators only;
        clause punctuation is deferred to a later milestone.
        """
        boundaries = sorted(
            idx for idx, operation in op_meta
            if operation and is_clause_linking(operation)
        )
        if not boundaries:
            return []

        spans: List[Tuple[int, int, int]] = []
        clause_id = 0
        start = 0
        for b in boundaries:
            spans.append((clause_id, start, b))
            clause_id += 1
            start = b + 1  # skip the connective token itself
        spans.append((clause_id, start, n_tokens))
        return spans

    def _detect_embedded_clauses(
        self, doc,
    ) -> List[Tuple[int, int, str, int, Optional[str]]]:
        """Find embedded clauses that nest inside a parent span.

        Unlike because/so (which split the stream sequentially), relative
        clauses (spaCy ``relcl``) and control complements (``xcomp`` with a
        ``to`` particle) hang off a token *inside* a parent clause. Returns
        ``(token_start, token_end, kind, attaches_to_token, gap_role)`` per
        embedded clause, where ``attaches_to_token`` is the antecedent (relative)
        or controlling verb (control), and ``gap_role`` is the relativizer's gap
        ("subject"/"object", else None). See docs/COMPLEX_SENTENCE_DESIGN.md §M2.
        """
        embedded: List[Tuple[int, int, str, int, Optional[str]]] = []
        for tok in doc:
            if tok.dep_ == "relcl":
                sub = sorted(c.i for c in tok.subtree)
                if sub:
                    # The relativizer is the gap-filling child of the relcl verb;
                    # its dep tells us whether the antecedent is subject or object.
                    relzr = next(
                        (c for c in tok.children
                         if c.pos_ == "PRON"
                         and c.lemma_.lower() in {"who", "whom", "which", "that", "whose"}),
                        None,
                    )
                    gap_role: Optional[str] = None
                    if relzr is not None:
                        if relzr.lemma_.lower() == "whom":
                            gap_role = "object"  # accusative — unambiguous
                        elif relzr.dep_ in ("dobj", "obj", "pobj"):
                            gap_role = "object"
                        elif relzr.dep_ in ("nsubj", "nsubjpass"):
                            # spaCy mistags object relatives ("whom/that X verbed")
                            # as nsubj; a real subject sibling means the relativizer
                            # is actually the object gap.
                            other_subject = any(
                                c.i != relzr.i and c.dep_ in ("nsubj", "nsubjpass")
                                for c in tok.children
                            )
                            gap_role = "object" if other_subject else "subject"
                    embedded.append((sub[0], sub[-1] + 1, "relative", tok.head.i, gap_role))
            elif tok.dep_ == "xcomp" and any(
                c.dep_ == "aux" and c.lemma_ == "to" for c in tok.children
            ):
                # Infinitival control complement. Controller = the matrix verb's
                # object (object control) else its subject (subject control).
                sub = sorted(c.i for c in tok.subtree)
                head = tok.head
                controller = next(
                    (c.i for c in head.children if c.dep_ in ("dobj", "obj")), None
                )
                if controller is None:
                    controller = next(
                        (c.i for c in head.children
                         if c.dep_ in ("nsubj", "nsubjpass")), None
                    )
                if sub and controller is not None:
                    embedded.append((sub[0], sub[-1] + 1, "control", controller, None))
            elif tok.dep_ == "ccomp":
                # Clausal complement ("X predicted that Y verbs Z"): a full
                # proposition that becomes the reporting verb's patient.
                sub = sorted(c.i for c in tok.subtree)
                if sub:
                    embedded.append((sub[0], sub[-1] + 1, "complement", tok.head.i, None))
        return embedded

    def _resolve_operator(
        self,
        op_idx: int,
        comp_meta: Dict,
        token_vectors: List[Tuple[int, SparseVector, Dict]],
        token_traces: List[TokenTrace],
        arg1_range: Optional[Tuple[int, int]] = None,
        arg2_range: Optional[Tuple[int, int]] = None,
        excluded_tokens: Optional[set] = None,
    ) -> Tuple[Optional[OperatorTrace], Optional[SparseVector]]:
        """Resolve a compositional operator.

        ``arg1_range`` / ``arg2_range`` are half-open ``[start, end)`` token
        windows the two arguments are gathered from. They default to the whole
        sentence — ``[0, op_idx)`` and ``[op_idx+1, n)`` — which reproduces the
        original clause-blind behavior exactly. Clause segmentation passes
        narrower windows so a within-clause operator can't reach across a
        clause boundary, and a clause-linking operator takes whole clauses as
        its two operands. ``excluded_tokens`` are positions to skip entirely —
        used to keep an embedded clause's tokens (e.g. a relative clause) out of
        the parent operator's arguments. See
        ``docs/COMPLEX_SENTENCE_DESIGN.md`` §3.
        """
        primitive = comp_meta.get("comp_primitive")
        operation = comp_meta.get("comp_operation")
        arity = comp_meta.get("comp_arity", 0)

        if not primitive or not operation:
            return None, None

        n = len(token_vectors)
        a1s, a1e = arg1_range if arg1_range is not None else (0, op_idx)
        a2s, a2e = arg2_range if arg2_range is not None else (op_idx + 1, n)
        excluded = excluded_tokens or set()

        # Find arguments within their windows.
        # For binary operators: arg1 is the left window, arg2 the right.
        arg1_tokens = []
        arg2_tokens = []
        arg1_lemmas = []
        arg2_lemmas = []
        arg1_vecs = []
        arg2_vecs = []

        for i, (pos, vec, _) in enumerate(token_vectors):
            if i == op_idx or i in excluded:
                continue

            trace = token_traces[i]
            if vec.nnz > 0 and not trace.is_operator:
                if a1s <= i < a1e:
                    arg1_tokens.append(i)
                    arg1_lemmas.append(trace.lemma)
                    arg1_vecs.append(vec)
                elif a2s <= i < a2e:
                    arg2_tokens.append(i)
                    arg2_lemmas.append(trace.lemma)
                    arg2_vecs.append(vec)

        # Apply operation
        result_vec = None
        if operation == "SET_DIFF" and arg1_vecs and arg2_vecs:
            # SET_DIFF with DIRECTIONAL ENCODING
            # This ensures argument order matters in the HDC vector
            #
            # Original: bind(arg1, negate(arg2)) - loses direction
            # New: Use different permutation shifts to encode arg1 vs arg2 position
            # - arg1 (comparee) gets positive shift
            # - arg2 (standard) gets negative shift (negate + different shift)
            #
            # This creates a slight but measurable difference when arguments swap
            arg1_bundled = bundle(arg1_vecs) if len(arg1_vecs) > 1 else arg1_vecs[0]
            arg2_bundled = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]

            # SET_DIFF: bind(bundle(arg1), negate(bundle(arg2)))
            # This encodes the semantic content of the comparison.
            # Argument order is captured in the OperationTrace, not the vector.
            result_vec = bind(arg1_bundled, arg2_bundled.negate())

        elif operation in ["DEGREE_QUERY", "TYPE_QUERY", "SET_RESTRICT", "SCALAR_EXTREME"]:
            # Unary operators: mark the scope
            if arg2_vecs:
                result_vec = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]

        elif operation in ["CONTRAST", "CONSEQUENCE", "CAUSAL_SOURCE", "BIND_EQ", "CARD_LOWER"]:
            # Binary operators: combine both arguments
            if arg1_vecs and arg2_vecs:
                arg1_bundled = bundle(arg1_vecs) if len(arg1_vecs) > 1 else arg1_vecs[0]
                arg2_bundled = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]
                result_vec = bind(arg1_bundled, arg2_bundled)

        op_trace = OperatorTrace(
            primitive=primitive,
            operation=operation,
            position=op_idx,
            arity=arity,
            arg1_tokens=arg1_tokens,
            arg2_tokens=arg2_tokens,
            arg1_lemmas=arg1_lemmas,
            arg2_lemmas=arg2_lemmas,
            result_nnz=result_vec.nnz if result_vec else 0,
        )

        return op_trace, result_vec

    def _compute_primitive_activations(
        self,
        vector: SparseVector,
        basis: Any,
    ) -> Dict[str, float]:
        """Compute cosine similarity to each primitive in basis."""
        activations = {}

        for prim_name, prim_vec in basis.primitives.items():
            cos = vector.cosine(prim_vec)
            if abs(cos) > 0.01:  # Only include non-trivial activations
                activations[prim_name] = round(cos, 4)

        return activations

    def _hash_vector(self, vector: SparseVector) -> str:
        """Compute hash of vector for reproducibility verification."""
        # Create deterministic representation
        data = f"{sorted(vector.positive_indices.tolist())}{sorted(vector.negative_indices.tolist())}"
        return f"sha256:{hashlib.sha256(data.encode()).hexdigest()[:16]}"

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
