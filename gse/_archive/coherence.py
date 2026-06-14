from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set
import numpy as np

from gse.vectors import SparseVector, bind, bundle, D, DIMS_PER_BANK, N_BANKS, SemanticBank
from gse.composer import CompositionResult
from gse.parser import ParsedSentence, Token

@dataclass
class CoherenceResult:
    """Result of coherence checking."""
    passed: bool
    score: float              # 0-1, higher is more coherent
    confidence: float         # Overall confidence
    anomalies: List[str]      # Detected issues
    suggestions: List[str]    # Possible fixes
    bank_analysis: Optional[Dict[str, float]] = None  # Per-bank scores


# =============================================================================
# SELECTIONAL RESTRICTIONS
# =============================================================================
# Define which semantic banks are expected/required for different roles

ROLE_BANK_REQUIREMENTS = {
    # Agents of mental verbs need SUBSTANTIVES bank (animate entities)
    "mental_agent": {
        "required": {SemanticBank.SUBSTANTIVES},
        "preferred": {SemanticBank.MENTAL},
        "forbidden": set(),
    },
    # Agents of physical actions
    "physical_agent": {
        "required": {SemanticBank.SUBSTANTIVES},
        "preferred": {SemanticBank.ACTION},
        "forbidden": set(),
    },
    # Patients can be anything
    "patient": {
        "required": set(),
        "preferred": {SemanticBank.SUBSTANTIVES},
        "forbidden": set(),
    },
    # Locations need spatial semantics
    "location": {
        "required": {SemanticBank.SPATIAL},
        "preferred": set(),
        "forbidden": {SemanticBank.MENTAL},
    },
    # Temporal expressions
    "temporal": {
        "required": {SemanticBank.TEMPORAL},
        "preferred": set(),
        "forbidden": set(),
    },
    # Evaluative predicates
    "evaluative": {
        "required": {SemanticBank.EVALUATORS},
        "preferred": set(),
        "forbidden": set(),
    },
}

# Verbs classified by their selectional requirements
VERB_CLASSES = {
    # Mental verbs require animate agents
    "mental": {
        "verbs": {"think", "know", "believe", "want", "feel", "understand",
                  "remember", "forget", "imagine", "dream", "hope", "fear",
                  "love", "hate", "like", "prefer", "wonder", "doubt"},
        "agent_type": "mental_agent",
        "required_banks": {SemanticBank.MENTAL},
    },
    # Perception verbs
    "perception": {
        "verbs": {"see", "hear", "smell", "taste", "touch", "notice",
                  "observe", "watch", "listen"},
        "agent_type": "mental_agent",
        "required_banks": {SemanticBank.MENTAL},
    },
    # Communication verbs
    "communication": {
        "verbs": {"say", "tell", "speak", "talk", "ask", "answer",
                  "explain", "describe", "announce", "declare"},
        "agent_type": "mental_agent",
        "required_banks": {SemanticBank.ACTION},
    },
    # Motion verbs
    "motion": {
        "verbs": {"go", "come", "run", "walk", "move", "travel",
                  "arrive", "leave", "enter", "exit", "fly", "swim"},
        "agent_type": "physical_agent",
        "required_banks": {SemanticBank.ACTION, SemanticBank.SPATIAL},
    },
    # Transfer verbs
    "transfer": {
        "verbs": {"give", "take", "send", "receive", "bring", "carry",
                  "put", "place", "throw", "catch"},
        "agent_type": "physical_agent",
        "required_banks": {SemanticBank.ACTION},
    },
    # Creation/destruction verbs
    "creation": {
        "verbs": {"make", "create", "build", "destroy", "break",
                  "fix", "repair", "cook", "write", "draw"},
        "agent_type": "physical_agent",
        "required_banks": {SemanticBank.ACTION},
    },
}


class CoherenceChecker:
    """
    Check semantic coherence of composed vectors.

    Coherence checking detects:
    - Selectional restriction violations (e.g., "the rock thinks")
    - Semantic incompatibilities (e.g., "colorless green")
    - Missing required arguments
    - Unusual role fillers
    - Bank-based semantic constraint violations

    In the Hadamard-OTP architecture:
    - Bank 0 (SUBSTANTIVES): dims 0-1023 (animate entities)
    - Bank 1 (DETERMINERS): dims 1024-2047
    - Bank 2 (EVALUATORS): dims 2048-3071 (good/bad, big/small)
    - Bank 3 (MENTAL): dims 3072-4095 (mental predicates)
    - Bank 4 (ACTION): dims 4096-5119 (physical actions)
    - Bank 5 (TEMPORAL): dims 5120-6143
    - Bank 6 (SPATIAL): dims 6144-7167
    - Bank 7 (LOGICAL): dims 7168-8191
    """

    def __init__(self,
                 dimension: int = D,
                 base_threshold: float = 0.3,
                 strict_threshold: float = 0.5):
        self.dimension = dimension
        self.base_threshold = base_threshold
        self.strict_threshold = strict_threshold

        # Build verb lookup
        self.verb_to_class: Dict[str, str] = {}
        for class_name, class_info in VERB_CLASSES.items():
            for verb in class_info["verbs"]:
                self.verb_to_class[verb] = class_name

        # Bank dimension ranges
        self.bank_ranges = {
            bank: range(bank.value * DIMS_PER_BANK, (bank.value + 1) * DIMS_PER_BANK)
            for bank in SemanticBank
        }

        # Legacy dimension indices for backward compatibility
        # These are used by _check_agent_animacy and other methods
        self.animacy_dims = list(range(0, 100))  # First 100 dims of SUBSTANTIVES bank
        self.valence_dims = list(range(2 * DIMS_PER_BANK, 2 * DIMS_PER_BANK + 100))  # Bank 2 (EVALUATORS)
        self.agency_dims = list(range(3 * DIMS_PER_BANK, 3 * DIMS_PER_BANK + 100))  # Bank 3 (MENTAL)
    
    def check(self,
              composition: CompositionResult,
              parsed: ParsedSentence,
              strict: bool = False) -> CoherenceResult:
        """Check coherence of a composed sentence."""

        anomalies = []
        scores = []

        # Check 1: Agent animacy for mental/volitional verbs
        agent_score = self._check_agent_animacy(composition, parsed)
        scores.append(agent_score)
        if agent_score < 0.3:
            anomalies.append(f"Possible animacy violation: agent may be inanimate (score {agent_score:.2f})")

        # Check 2: Overall vector coherence (not too sparse or too dense)
        sparsity_score = self._check_sparsity(composition)
        scores.append(sparsity_score)
        if sparsity_score < 0.3:
            anomalies.append(f"Unusual vector sparsity (score {sparsity_score:.2f})")

        # Check 3: Role filling completeness
        completeness_score = self._check_completeness(composition, parsed)
        scores.append(completeness_score)
        if completeness_score < 0.5:
            anomalies.append(f"Missing expected semantic roles (score {completeness_score:.2f})")

        # Check 4: Internal consistency
        consistency_score = self._check_consistency(composition, parsed)
        scores.append(consistency_score)
        if consistency_score < 0.3:
            anomalies.append(f"Semantic inconsistency detected (score {consistency_score:.2f})")

        # Check 5: Bank-based selectional restrictions (new)
        selectional_score, selectional_anomalies = self._check_selectional_restrictions(
            composition, parsed
        )
        scores.append(selectional_score)
        anomalies.extend(selectional_anomalies)

        # Check 6: Semantic compatibility between modifiers and heads
        compatibility_score, compat_anomalies = self._check_modifier_compatibility(
            composition, parsed
        )
        scores.append(compatibility_score)
        anomalies.extend(compat_anomalies)

        # Overall score
        overall_score = float(np.mean(scores))
        threshold = self.strict_threshold if strict else self.base_threshold
        passed = overall_score >= threshold

        # Generate suggestions
        suggestions = self._generate_suggestions(anomalies, composition, parsed)

        # Bank analysis
        bank_analysis = self._analyze_bank_distribution(composition)

        return CoherenceResult(
            passed=passed,
            score=overall_score,
            confidence=composition.confidence,
            anomalies=anomalies,
            suggestions=suggestions,
            bank_analysis=bank_analysis
        )

    def _get_bank_signal(self, vec: SparseVector, bank: SemanticBank) -> float:
        """Get the magnitude of signal in a specific semantic bank."""
        bank_range = self.bank_ranges[bank]
        dense = vec.to_dense()
        bank_vals = dense[list(bank_range)]
        return float(np.sum(np.abs(bank_vals)))

    def _get_dominant_banks(self, vec: SparseVector, threshold: float = 0.1) -> Set[SemanticBank]:
        """Get banks with significant signal."""
        total_signal = vec.nnz
        if total_signal == 0:
            return set()

        dominant = set()
        for bank in SemanticBank:
            signal = self._get_bank_signal(vec, bank)
            if signal / total_signal > threshold:
                dominant.add(bank)
        return dominant

    def _check_selectional_restrictions(
        self,
        composition: CompositionResult,
        parsed: ParsedSentence
    ) -> Tuple[float, List[str]]:
        """
        Check bank-based selectional restrictions.

        E.g., mental verbs require agents with SUBSTANTIVES bank signal,
        location arguments need SPATIAL bank signal.
        """
        anomalies = []
        scores = []

        # Find the main verb
        main_verb = parsed.tokens[parsed.root_idx]
        verb_lemma = main_verb.lemma.lower()
        verb_class = self.verb_to_class.get(verb_lemma)

        if not verb_class:
            return 1.0, []  # Unknown verb, no specific requirements

        class_info = VERB_CLASSES[verb_class]
        agent_type = class_info["agent_type"]
        requirements = ROLE_BANK_REQUIREMENTS.get(agent_type, {})

        # Find the agent
        agent_idx = None
        for role in parsed.roles:
            if role.role == "agent":
                agent_idx = role.token_idx
                break

        if agent_idx is None:
            # Try to find subject
            for token in parsed.tokens:
                if token.dep in ["nsubj", "nsubjpass"]:
                    agent_idx = token.idx
                    break

        if agent_idx is not None and agent_idx in composition.token_vectors:
            agent_vec = composition.token_vectors[agent_idx]
            agent_banks = self._get_dominant_banks(agent_vec)

            # Check required banks
            required = requirements.get("required", set())
            for req_bank in required:
                if req_bank not in agent_banks:
                    anomalies.append(
                        f"Selectional restriction: '{verb_lemma}' ({verb_class}) expects "
                        f"agent with {req_bank.name} semantics"
                    )
                    scores.append(0.3)
                else:
                    scores.append(1.0)

            # Check forbidden banks
            forbidden = requirements.get("forbidden", set())
            for forb_bank in forbidden:
                if forb_bank in agent_banks:
                    anomalies.append(
                        f"Selectional violation: agent has unexpected {forb_bank.name} semantics"
                    )
                    scores.append(0.2)

        return np.mean(scores) if scores else 1.0, anomalies

    def _check_modifier_compatibility(
        self,
        composition: CompositionResult,
        parsed: ParsedSentence
    ) -> Tuple[float, List[str]]:
        """
        Check semantic compatibility between modifiers and heads.

        E.g., "colorless green" has contradictory evaluators,
        "sleeping wakefulness" has contradictory states.
        """
        anomalies = []
        scores = []

        for token in parsed.tokens:
            if token.dep == "amod":  # Adjectival modifier
                head_idx = token.head_idx
                if token.idx in composition.token_vectors and head_idx in composition.token_vectors:
                    mod_vec = composition.token_vectors[token.idx]
                    head_vec = composition.token_vectors[head_idx]

                    # Check for contradictory evaluators
                    mod_eval = self._get_bank_signal(mod_vec, SemanticBank.EVALUATORS)
                    head_eval = self._get_bank_signal(head_vec, SemanticBank.EVALUATORS)

                    if mod_eval > 10 and head_eval > 10:
                        # Both have evaluative content - check compatibility
                        dense_mod = mod_vec.to_dense()
                        dense_head = head_vec.to_dense()
                        eval_range = list(self.bank_ranges[SemanticBank.EVALUATORS])

                        # Check for sign conflicts (GOOD vs BAD, BIG vs SMALL)
                        mod_signs = np.sign(dense_mod[eval_range])
                        head_signs = np.sign(dense_head[eval_range])
                        conflicts = np.sum((mod_signs * head_signs) < 0)

                        if conflicts > 20:  # Significant conflict
                            mod_word = parsed.tokens[token.idx].surface
                            head_word = parsed.tokens[head_idx].surface
                            anomalies.append(
                                f"Semantic conflict: '{mod_word}' may conflict with '{head_word}'"
                            )
                            scores.append(0.4)
                        else:
                            scores.append(1.0)
                    else:
                        scores.append(1.0)

        return np.mean(scores) if scores else 1.0, anomalies

    def _analyze_bank_distribution(self, composition: CompositionResult) -> Dict[str, float]:
        """Analyze the distribution of signal across semantic banks."""
        result = {}
        total = composition.sentence_vector.nnz
        if total == 0:
            return {bank.name: 0.0 for bank in SemanticBank}

        for bank in SemanticBank:
            signal = self._get_bank_signal(composition.sentence_vector, bank)
            result[bank.name] = signal / total

        return result
    
    def _check_agent_animacy(self, composition: CompositionResult,
                              parsed: ParsedSentence) -> float:
        """Check if agents are appropriately animate for the verb."""
        # Find agent role and check if verb requires animate agent
        agent_idx = None
        verb_lemma = None
        requires_animate = False

        for role in parsed.roles:
            if role.role == "agent":
                agent_idx = role.token_idx
                break

        # Check if verb is mental/perception (requires animate agent)
        from gse.parser import POS
        for token in parsed.tokens:
            if token.pos == POS.VERB:
                verb_lemma = token.lemma.lower()
                for verb_class in VERB_CLASSES.values():
                    if verb_lemma in verb_class["verbs"]:
                        if verb_class["agent_type"] == "mental_agent":
                            requires_animate = True
                        break
                break

        if agent_idx is None or not requires_animate:
            return 1.0  # No agent to check or verb doesn't require animate

        if agent_idx not in composition.token_vectors:
             return 1.0

        # Check for animacy using sense selections (decompositions)
        # Check if agent has animate markers in its sense selection
        is_animate = False
        is_inanimate = False
        has_decomposition = False

        if agent_idx in composition.sense_selections:
            sense_info = composition.sense_selections[agent_idx]
            decomp = sense_info.decomposition if sense_info.decomposition else []
            if decomp:
                has_decomposition = True
                for prim, role in decomp:
                    # SOMEONE indicates animate
                    if prim == "SOMEONE":
                        is_animate = True
                    # LIVE with state role indicates animate
                    elif prim == "LIVE" and role == "state":
                        is_animate = True
                    # SOMETHING typically inanimate (unless with LIVE)
                    elif prim == "SOMETHING":
                        is_inanimate = True

        # If we have decomposition info, use it
        if has_decomposition:
            if is_animate:
                return 1.0
            if is_inanimate and not is_animate:
                return 0.1
            return 0.7

        # Fallback: use dimension-based check for mock/legacy lexicons
        agent_vec = composition.token_vectors[agent_idx].to_dense()
        animacy_signal = np.sum(agent_vec[self.animacy_dims])
        return min(1.0, max(0.0, (animacy_signal + 10) / 20))
    
    def _check_sparsity(self, composition: CompositionResult) -> float:
        """Check if vector sparsity is in expected range."""
        sparsity = composition.sentence_vector.sparsity
        
        # Expected range: 5% to 30%
        if 0.05 <= sparsity <= 0.30:
            return 1.0
        elif sparsity < 0.05:
            # Too sparse. 
            return max(0.0, sparsity / 0.05)
        else:
            # Too dense.
            return max(0.0, 1.0 - (sparsity - 0.30) / 0.30)
    
    def _check_completeness(self, composition: CompositionResult,
                            parsed: ParsedSentence) -> float:
        """Check if expected roles are filled."""
        # Find main verb
        main_verb = parsed.tokens[parsed.root_idx]
        
        if main_verb.pos.value != "VERB":
            return 1.0  # Not a verbal predicate
        
        # Check for subject
        # Using dependency labels directly to check for subject presence
        has_subject = any(t.dep in ["nsubj", "nsubjpass"] for t in parsed.tokens)
        
        # Simple scoring
        if has_subject:
            return 1.0
        return 0.4
    
    def _check_consistency(self, composition: CompositionResult,
                           parsed: ParsedSentence) -> float:
        """Check internal semantic consistency."""
        # Check if composed vector is reasonably similar to at least some components
        component_sims = []
        for idx, vec in composition.token_vectors.items():
            sim = composition.sentence_vector.cosine(vec)
            component_sims.append(sim)
        
        if not component_sims:
            return 1.0
        
        # At least some components should be reflected in the whole
        max_sim = max(component_sims)
        # normalize
        return min(1.0, max_sim + 0.5)
    
    def _generate_suggestions(self, anomalies: List[str],
                              composition: CompositionResult,
                              parsed: ParsedSentence) -> List[str]:
        """Generate suggestions for fixing anomalies."""
        suggestions = []
        
        for anomaly in anomalies:
            if "animacy" in anomaly.lower():
                suggestions.append("Check if the subject is appropriate for this verb")
            if "sparsity" in anomaly.lower():
                suggestions.append("Sentence may have unusual semantic structure")
            if "missing" in anomaly.lower():
                suggestions.append("Consider adding more context or arguments")
            if "inconsistency" in anomaly.lower():
                suggestions.append("Check for semantic conflicts between words")
        
        return suggestions
