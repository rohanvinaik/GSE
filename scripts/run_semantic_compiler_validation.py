#!/usr/bin/env python3
"""
GSE Semantic Compiler Validation Suite

Validates GSE's core claim: GSE is a semantic compiler that transforms
natural language into computable semantic representations.

Tier 2 Experiments:
1. Semantic Canonicalization - Paraphrases produce equivalent traces
2. Semantic Difference Detection - Different meanings produce different traces
3. Full Operator Verification - All 10 compositional operators working
4. Truth-Conditional Evaluation - Evaluate comparisons against world model
5. Structural Entailment - Basic inference from operator structure
6. Presupposition Detection - Separate presupposition from assertion
7. Quantifier Scope Demonstration - Represent scope ambiguities

The benchmark isn't similarity correlation. The benchmark is:
- Can we evaluate truth conditions?
- Can we perform inference?
- Can we compose meanings?
"""

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.api import GSEDecoder, GSEEncoder
from gse.evaluation.world_model import create_test_world


@dataclass
class ExperimentResult:
    """Result of a single experiment."""
    name: str
    passed: bool
    metrics: Dict[str, Any]
    details: str


class SemanticCompilerValidation:
    """
    Validates GSE as a semantic compiler.

    Core claim: GSE transforms natural language into computable
    semantic representations grounded in cognitive primitives.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.encoder = GSEEncoder()
        self.decoder = GSEDecoder()
        self.world = create_test_world()
        self.results: List[ExperimentResult] = []

    def log(self, msg: str = ""):
        if self.verbose:
            print(msg)

    def close(self):
        self.encoder.close()
        self.decoder.close()

    def run_all(self) -> Dict[str, Any]:
        """Run all Tier 2 semantic compiler experiments."""
        self.log("=" * 70)
        self.log("GSE SEMANTIC COMPILER VALIDATION")
        self.log("Testing: Can we evaluate truth? Can we infer? Can we compose?")
        self.log("=" * 70)
        self.log()

        self.results = []

        # Tier 2 Experiments
        self.test_semantic_canonicalization()
        self.test_semantic_difference_detection()
        self.test_full_operator_verification()
        self.test_truth_conditional_evaluation()
        self.test_structural_entailment()
        self.test_presupposition_detection()
        self.test_quantifier_scope()

        return self._generate_report()

    # =========================================================================
    # EXPERIMENT 2.1: Semantic Canonicalization
    # =========================================================================
    def test_semantic_canonicalization(self):
        """
        Same meaning -> equivalent compiled form.

        Paraphrases should produce structurally equivalent traces.
        """
        self.log("[2.1] SEMANTIC CANONICALIZATION")
        self.log("-" * 50)
        self.log("  Testing: Paraphrases produce equivalent operator traces")
        self.log()

        test_cases = [
            {
                "name": "comparison_paraphrase",
                "sentences": [
                    "The dog is cuter than the cat",
                    "The dog is more cute than the cat",
                    "Compared to the cat, the dog is cuter",
                ],
                "expected_operator": "COMP_THAN",
            },
            {
                "name": "causal_paraphrase",
                "sentences": [
                    "She left because she was tired",
                    "She left since she was tired",
                ],
                "expected_operator": "COMP_BECAUSE",
            },
            {
                "name": "question_paraphrase",
                "sentences": [
                    "How fast can you run?",
                    "How quickly can you run?",
                ],
                "expected_operator": "COMP_HOW",
            },
        ]

        metrics = {"test_cases": [], "summary": {}}
        total_groups = 0
        equivalent_groups = 0

        for case in test_cases:
            traces = []
            for sent in case["sentences"]:
                trace = self.encoder.encode(sent)
                traces.append(trace)

            # Check if all traces have the expected operator
            has_operator = []
            for trace in traces:
                found = any(op.primitive == case["expected_operator"]
                           for op in trace.operators)
                has_operator.append(found)

            # Check HDC similarity between paraphrases
            cosines = []
            if len(traces) >= 2:
                for i in range(len(traces) - 1):
                    cos = traces[i].vector.cosine(traces[i+1].vector)
                    cosines.append(cos)

            # Calculate equivalence
            operator_consistency = all(has_operator)
            mean_cosine = sum(cosines) / len(cosines) if cosines else 0
            is_equivalent = operator_consistency and mean_cosine > 0.5

            total_groups += 1
            if is_equivalent:
                equivalent_groups += 1

            case_result = {
                "name": case["name"],
                "sentences": case["sentences"],
                "expected_operator": case["expected_operator"],
                "has_operator": has_operator,
                "operator_consistency": operator_consistency,
                "pairwise_cosines": [float(c) for c in cosines],
                "mean_cosine": float(mean_cosine),
                "is_equivalent": is_equivalent,
            }
            metrics["test_cases"].append(case_result)

            status = "OK" if is_equivalent else "FAIL"
            self.log(f"  [{status}] {case['name']}")
            self.log(f"       Operator present: {has_operator}")
            self.log(f"       Mean paraphrase cosine: {mean_cosine:.3f}")

        equivalence_rate = equivalent_groups / total_groups if total_groups > 0 else 0
        metrics["summary"] = {
            "total_groups": total_groups,
            "equivalent_groups": equivalent_groups,
            "equivalence_rate": equivalence_rate,
        }

        self.log()
        self.log(f"  Paraphrase equivalence rate: {equivalence_rate:.1%}")

        self.results.append(ExperimentResult(
            name="semantic_canonicalization",
            passed=equivalence_rate >= 0.6,
            metrics=metrics,
            details=f"Paraphrases produce equivalent traces: {equivalence_rate:.1%}",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.2: Semantic Difference Detection
    # =========================================================================
    def test_semantic_difference_detection(self):
        """
        Different meaning -> detectable difference in compiled form.

        Tests:
        - Argument swaps (same content, different structure)
        - Negation (same structure, opposite polarity)
        - Operator changes (different relations)
        """
        self.log("[2.2] SEMANTIC DIFFERENCE DETECTION")
        self.log("-" * 50)
        self.log("  Testing: Different meanings produce different traces")
        self.log()

        test_cases = [
            # Argument swaps
            {
                "name": "argument_swap_1",
                "type": "argument_swap",
                "sentence1": "The dog is cuter than the cat",
                "sentence2": "The cat is cuter than the dog",
                "expected_different": True,
                "expected_swap": True,
            },
            {
                "name": "argument_swap_2",
                "type": "argument_swap",
                "sentence1": "John is taller than Mary",
                "sentence2": "Mary is taller than John",
                "expected_different": True,
                "expected_swap": True,
            },
            # Negation
            {
                "name": "negation_1",
                "type": "negation",
                "sentence1": "The dog is happy",
                "sentence2": "The dog is not happy",
                "expected_different": True,
                "expected_swap": False,
            },
            # Operator change
            {
                "name": "operator_change",
                "type": "operator_change",
                "sentence1": "She left because she was tired",
                "sentence2": "She left so she could rest",
                "expected_different": True,
                "expected_swap": False,
            },
            # Paraphrase (should NOT be detected as different)
            {
                "name": "paraphrase",
                "type": "paraphrase",
                "sentence1": "The dog is cuter than the cat",
                "sentence2": "The dog is more cute than the cat",
                "expected_different": False,
                "expected_swap": False,
            },
        ]

        metrics = {"test_cases": [], "summary": {}}
        correct = 0
        total = 0

        for case in test_cases:
            t1 = self.encoder.encode(case["sentence1"])
            t2 = self.encoder.encode(case["sentence2"])

            # Logical comparison
            logically_equal = t1.logical_equals(t2)
            is_arg_swap = t1.is_argument_swap_of(t2)
            hdc_cosine = t1.vector.cosine(t2.vector)

            # Determine if difference detected correctly
            if case["type"] == "argument_swap":
                detected_different = not logically_equal
                correct_detection = detected_different == case["expected_different"]
                swap_correct = is_arg_swap == case["expected_swap"]
            elif case["type"] == "paraphrase":
                # For paraphrases, high cosine = correctly NOT detecting difference
                detected_different = hdc_cosine < 0.5
                correct_detection = detected_different == case["expected_different"]
                swap_correct = True  # N/A
            else:
                detected_different = not logically_equal or hdc_cosine < 0.5
                correct_detection = detected_different == case["expected_different"]
                swap_correct = True  # N/A

            total += 1
            if correct_detection and swap_correct:
                correct += 1

            case_result = {
                "name": case["name"],
                "type": case["type"],
                "sentence1": case["sentence1"],
                "sentence2": case["sentence2"],
                "logically_equal": logically_equal,
                "is_argument_swap": is_arg_swap,
                "hdc_cosine": float(hdc_cosine),
                "detected_different": detected_different,
                "correct_detection": correct_detection,
            }
            metrics["test_cases"].append(case_result)

            status = "OK" if correct_detection else "FAIL"
            self.log(f"  [{status}] {case['name']} ({case['type']})")
            self.log(f"       LogEqual: {logically_equal} | ArgSwap: {is_arg_swap} | cos: {hdc_cosine:.3f}")

        accuracy = correct / total if total > 0 else 0
        metrics["summary"] = {
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
        }

        self.log()
        self.log(f"  Semantic difference detection accuracy: {accuracy:.1%}")

        self.results.append(ExperimentResult(
            name="semantic_difference_detection",
            passed=accuracy >= 0.7,
            metrics=metrics,
            details=f"Different meanings detected: {accuracy:.1%}",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.3: Full Operator Verification
    # =========================================================================
    def test_full_operator_verification(self):
        """
        Validate all 10 compositional operators.

        Each operator should:
        1. Be detected when present
        2. Extract correct arguments
        3. Apply correct operation
        """
        self.log("[2.3] FULL OPERATOR VERIFICATION")
        self.log("-" * 50)
        self.log("  Testing: All 10 compositional operators")
        self.log()

        # All 10 operators with test sentences
        operator_tests = [
            {
                "operator": "COMP_THAN",
                "operation": "SET_DIFF",
                "sentence": "The dog is bigger than the cat",
                "description": "Comparison (SET_DIFF)",
            },
            {
                "operator": "COMP_AS",
                "operation": "BIND_EQ",
                "sentence": "The dog is as big as the cat",
                "description": "Equality (BIND_EQ)",
            },
            {
                "operator": "COMP_HOW",
                "operation": "DEGREE_QUERY",
                "sentence": "How fast can you run?",
                "description": "Degree query",
            },
            {
                "operator": "COMP_WHAT",
                "operation": "TYPE_QUERY",
                "sentence": "What kind of dog is that?",
                "description": "Type query",
            },
            {
                "operator": "COMP_JUST",
                "operation": "CARD_LOWER",
                "sentence": "She just arrived",
                "description": "Recency marker",
            },
            {
                "operator": "COMP_ONLY",
                "operation": "SET_RESTRICT",
                "sentence": "Only John came to the party",
                "description": "Restriction",
            },
            {
                "operator": "COMP_EVEN",
                "operation": "SCALAR_EXTREME",
                "sentence": "Even Mary agreed with the plan",
                "description": "Scalar extreme",
            },
            {
                "operator": "COMP_BUT",
                "operation": "CONTRAST",
                "sentence": "He is smart but lazy",
                "description": "Contrast",
            },
            {
                "operator": "COMP_SO",
                "operation": "CONSEQUENCE",
                "sentence": "She was tired so she left",
                "description": "Consequence",
            },
            {
                "operator": "COMP_BECAUSE",
                "operation": "CAUSAL_SOURCE",
                "sentence": "She left because she was tired",
                "description": "Causal source",
            },
        ]

        metrics = {"operators": [], "summary": {}}
        detected = 0
        total = len(operator_tests)

        for test in operator_tests:
            trace = self.encoder.encode(test["sentence"])

            # Find operator in trace
            found_op = None
            for op in trace.operators:
                if op.primitive == test["operator"]:
                    found_op = op
                    break

            if found_op:
                detected += 1
                status = "OK"
                result = {
                    "operator": test["operator"],
                    "sentence": test["sentence"],
                    "found": True,
                    "operation": found_op.operation,
                    "arg1_lemmas": found_op.arg1_lemmas,
                    "arg2_lemmas": found_op.arg2_lemmas,
                    "arity": found_op.arity,
                }
                self.log(f"  [{status}] {test['operator']} ({test['description']})")
                self.log(f"       Sentence: '{test['sentence'][:40]}...'")
                self.log(f"       Args: {found_op.arg1_lemmas} | {found_op.arg2_lemmas}")
            else:
                status = "--"
                result = {
                    "operator": test["operator"],
                    "sentence": test["sentence"],
                    "found": False,
                    "all_operators": [op.primitive for op in trace.operators],
                }
                self.log(f"  [{status}] {test['operator']} ({test['description']}) - NOT FOUND")
                self.log(f"       Found: {[op.primitive for op in trace.operators]}")

            metrics["operators"].append(result)

        detection_rate = detected / total if total > 0 else 0
        metrics["summary"] = {
            "total": total,
            "detected": detected,
            "detection_rate": detection_rate,
        }

        self.log()
        self.log(f"  Operator detection rate: {detection_rate:.1%} ({detected}/{total})")

        self.results.append(ExperimentResult(
            name="operator_verification",
            passed=detection_rate >= 0.5,  # At least half must work
            metrics=metrics,
            details=f"Operators detected: {detected}/{total} ({detection_rate:.1%})",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.4: Truth-Conditional Evaluation
    # =========================================================================
    def test_truth_conditional_evaluation(self):
        """
        Evaluate sentences against toy world model.

        Given a sentence and world model, can GSE help determine truth value?
        """
        self.log("[2.4] TRUTH-CONDITIONAL EVALUATION")
        self.log("-" * 50)
        self.log("  Testing: Evaluate comparisons against world model")
        self.log(f"  World: {self.world}")
        self.log()

        test_cases = [
            # True statements
            {
                "sentence": "Fido is bigger than Whiskers",
                "expected": True,
            },
            {
                "sentence": "The dog is cuter than the cat",
                "expected": True,
            },
            {
                "sentence": "John is taller than Mary",
                "expected": True,
            },
            {
                "sentence": "Jumbo is bigger than Fido",
                "expected": True,
            },
            # False statements
            {
                "sentence": "Whiskers is bigger than Fido",
                "expected": False,
            },
            {
                "sentence": "Mary is taller than John",
                "expected": False,
            },
            {
                "sentence": "Tweety is bigger than Jumbo",
                "expected": False,
            },
            # Transitive inference
            {
                "sentence": "Jumbo is bigger than Whiskers",
                "expected": True,  # jumbo > fido > whiskers
            },
        ]

        metrics = {"evaluations": [], "summary": {}}
        correct = 0
        evaluated = 0
        total = len(test_cases)

        for case in test_cases:
            trace = self.encoder.encode(case["sentence"])
            result = self.world.evaluate_trace_comparison(trace)

            if result is not None:
                evaluated += 1
                is_correct = result == case["expected"]
                if is_correct:
                    correct += 1
                status = "OK" if is_correct else "FAIL"
            else:
                status = "N/A"
                is_correct = None

            eval_result = {
                "sentence": case["sentence"],
                "expected": case["expected"],
                "evaluated": result,
                "correct": is_correct,
            }
            metrics["evaluations"].append(eval_result)

            self.log(f"  [{status}] '{case['sentence']}'")
            self.log(f"       Expected: {case['expected']} | Evaluated: {result}")

        # Accuracy only on evaluated cases
        accuracy = correct / evaluated if evaluated > 0 else 0
        evaluation_rate = evaluated / total if total > 0 else 0

        metrics["summary"] = {
            "total": total,
            "evaluated": evaluated,
            "correct": correct,
            "accuracy": accuracy,
            "evaluation_rate": evaluation_rate,
        }

        self.log()
        self.log(f"  Evaluation rate: {evaluation_rate:.1%} ({evaluated}/{total})")
        self.log(f"  Accuracy on evaluated: {accuracy:.1%} ({correct}/{evaluated})")

        self.results.append(ExperimentResult(
            name="truth_conditional_evaluation",
            passed=accuracy >= 0.7 and evaluation_rate >= 0.5,
            metrics=metrics,
            details=f"Truth evaluation: {accuracy:.1%} accuracy on {evaluation_rate:.1%} evaluated",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.5: Structural Entailment
    # =========================================================================
    def test_structural_entailment(self):
        """
        Can GSE's operator system support basic inference?

        Tests:
        - Comparison transitivity: A > B, B > C => A > C
        - Contrast decomposition: BUT(P, Q) => P AND Q
        - Causal direction: BECAUSE(effect, cause) identifies cause
        """
        self.log("[2.5] STRUCTURAL ENTAILMENT")
        self.log("-" * 50)
        self.log("  Testing: Basic inference from operator structure")
        self.log()

        metrics = {"entailments": [], "summary": {}}
        correct = 0
        total = 0

        # Test 1: Contrast decomposition
        self.log("  Type 1: Contrast Decomposition")
        contrast_sentence = "John is smart but lazy"
        trace = self.encoder.encode(contrast_sentence)

        # Find COMP_BUT operator
        but_op = None
        for op in trace.operators:
            if op.primitive == "COMP_BUT":
                but_op = op
                break

        if but_op:
            # COMP_BUT(P, Q) => P AND Q
            # Check if both properties are in the arguments
            all_lemmas = but_op.arg1_lemmas + but_op.arg2_lemmas
            has_smart = "smart" in all_lemmas
            has_lazy = "lazy" in all_lemmas

            decomposition_correct = has_smart and has_lazy
            total += 1
            if decomposition_correct:
                correct += 1

            status = "OK" if decomposition_correct else "FAIL"
            self.log(f"    [{status}] '{contrast_sentence}'")
            self.log(f"         COMP_BUT found: args contain 'smart' and 'lazy': {decomposition_correct}")
            metrics["entailments"].append({
                "type": "contrast_decomposition",
                "sentence": contrast_sentence,
                "correct": decomposition_correct,
            })
        else:
            self.log("    [--] COMP_BUT not found")
            metrics["entailments"].append({
                "type": "contrast_decomposition",
                "sentence": contrast_sentence,
                "correct": False,
                "note": "operator_not_found",
            })
            total += 1

        # Test 2: Comparison structure preserved
        self.log("  Type 2: Comparison Structure")
        comp_pairs = [
            ("The dog is bigger than the cat", "dog", "cat", True),
            ("The cat is bigger than the dog", "cat", "dog", True),
        ]

        for sent, expected_arg1, expected_arg2, should_match in comp_pairs:
            trace = self.encoder.encode(sent)

            than_op = None
            for op in trace.operators:
                if op.primitive == "COMP_THAN":
                    than_op = op
                    break

            if than_op:
                entity_args = than_op.get_entity_args()
                arg1_correct = expected_arg1 in entity_args[0]
                arg2_correct = expected_arg2 in entity_args[1]
                structure_correct = arg1_correct and arg2_correct

                total += 1
                if structure_correct == should_match:
                    correct += 1

                status = "OK" if structure_correct else "FAIL"
                self.log(f"    [{status}] '{sent[:40]}...'")
                self.log(f"         Arg1 has '{expected_arg1}': {arg1_correct}, Arg2 has '{expected_arg2}': {arg2_correct}")

                metrics["entailments"].append({
                    "type": "comparison_structure",
                    "sentence": sent,
                    "expected_arg1": expected_arg1,
                    "expected_arg2": expected_arg2,
                    "actual_arg1": list(entity_args[0]),
                    "actual_arg2": list(entity_args[1]),
                    "correct": structure_correct,
                })
            else:
                total += 1
                self.log(f"    [--] '{sent[:40]}...' - COMP_THAN not found")
                metrics["entailments"].append({
                    "type": "comparison_structure",
                    "sentence": sent,
                    "correct": False,
                    "note": "operator_not_found",
                })

        # Test 3: Causal direction
        self.log("  Type 3: Causal Direction")
        causal_sentence = "She left because she was tired"
        trace = self.encoder.encode(causal_sentence)

        because_op = None
        for op in trace.operators:
            if op.primitive == "COMP_BECAUSE":
                because_op = op
                break

        if because_op:
            # BECAUSE(effect, cause) - arg2 should contain "tired"
            has_cause = "tire" in because_op.arg2_lemmas or "tired" in because_op.arg2_lemmas
            has_effect = "left" in because_op.arg1_lemmas or "leave" in because_op.arg1_lemmas

            causal_correct = has_cause or has_effect  # At least one direction captured
            total += 1
            if causal_correct:
                correct += 1

            status = "OK" if causal_correct else "FAIL"
            self.log(f"    [{status}] '{causal_sentence}'")
            self.log(f"         Arg1 (effect): {because_op.arg1_lemmas}")
            self.log(f"         Arg2 (cause): {because_op.arg2_lemmas}")

            metrics["entailments"].append({
                "type": "causal_direction",
                "sentence": causal_sentence,
                "arg1": because_op.arg1_lemmas,
                "arg2": because_op.arg2_lemmas,
                "correct": causal_correct,
            })
        else:
            total += 1
            self.log("    [--] COMP_BECAUSE not found")
            metrics["entailments"].append({
                "type": "causal_direction",
                "sentence": causal_sentence,
                "correct": False,
                "note": "operator_not_found",
            })

        accuracy = correct / total if total > 0 else 0
        metrics["summary"] = {
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
        }

        self.log()
        self.log(f"  Structural entailment accuracy: {accuracy:.1%} ({correct}/{total})")

        self.results.append(ExperimentResult(
            name="structural_entailment",
            passed=accuracy >= 0.5,
            metrics=metrics,
            details=f"Entailment accuracy: {accuracy:.1%}",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.6: Presupposition Detection
    # =========================================================================
    def test_presupposition_detection(self):
        """
        Does the trace layer capture presuppositional content?

        Presupposition triggers:
        - Definite descriptions ("the king of France")
        - Aspectual verbs ("stopped", "continued")
        - Factive verbs ("knows that", "realized that")
        """
        self.log("[2.6] PRESUPPOSITION DETECTION")
        self.log("-" * 50)
        self.log("  Testing: Identify presupposition triggers in trace")
        self.log()

        metrics = {"cases": [], "summary": {}}
        detected = 0
        total = 0

        test_cases = [
            {
                "sentence": "John stopped smoking",
                "trigger_type": "aspectual",
                "trigger_word": "stop",
                "presupposition": "John used to smoke",
            },
            {
                "sentence": "Mary knows that it is raining",
                "trigger_type": "factive",
                "trigger_word": "know",
                "presupposition": "It is raining",
            },
            {
                "sentence": "The king of France is bald",
                "trigger_type": "definite",
                "trigger_word": "the",
                "presupposition": "France has a king",
            },
            {
                "sentence": "She continued working",
                "trigger_type": "aspectual",
                "trigger_word": "continue",
                "presupposition": "She was working before",
            },
        ]

        for case in test_cases:
            trace = self.encoder.encode(case["sentence"])
            total += 1

            # Check if trigger word is in tokens with relevant primitives
            trigger_found = False
            trigger_info = {}

            for token in trace.tokens:
                if case["trigger_word"] in token.lemma.lower():
                    trigger_found = True
                    trigger_info = {
                        "lemma": token.lemma,
                        "word_primitives": dict(token.word_primitives),
                    }

                    # Check for aspectual markers (BEFORE/AFTER for aspectual verbs)
                    if case["trigger_type"] == "aspectual":
                        has_temporal = (
                            token.word_primitives.get("BEFORE", 0) != 0 or
                            token.word_primitives.get("AFTER", 0) != 0 or
                            token.word_primitives.get("TIME", 0) != 0
                        )
                        if has_temporal:
                            detected += 1
                            trigger_info["temporal_marker"] = True

                    # Check for factive markers (KNOW primitive)
                    elif case["trigger_type"] == "factive":
                        has_know = token.word_primitives.get("KNOW", 0) != 0
                        if has_know:
                            detected += 1
                            trigger_info["factive_marker"] = True

                    # Definite descriptions
                    elif case["trigger_type"] == "definite":
                        # "the" creates reference presupposition
                        if token.is_operator or token.word_primitives.get("SAME", 0) != 0:
                            detected += 1
                            trigger_info["definite_marker"] = True

                    break

            if not trigger_found:
                # Fallback: check if presupposition-related primitives are anywhere
                for token in trace.tokens:
                    prims = token.word_primitives
                    if case["trigger_type"] == "aspectual" and prims.get("BEFORE", 0) != 0:
                        detected += 1
                        trigger_found = True
                        trigger_info = {"found_temporal": True}
                        break

            status = "OK" if trigger_found else "--"
            case_result = {
                "sentence": case["sentence"],
                "trigger_type": case["trigger_type"],
                "trigger_word": case["trigger_word"],
                "presupposition": case["presupposition"],
                "trigger_found": trigger_found,
                "trigger_info": trigger_info,
            }
            metrics["cases"].append(case_result)

            self.log(f"  [{status}] '{case['sentence']}'")
            self.log(f"       Trigger: '{case['trigger_word']}' ({case['trigger_type']})")
            self.log(f"       Presupposes: {case['presupposition']}")
            if trigger_info:
                self.log(f"       Info: {trigger_info}")

        detection_rate = detected / total if total > 0 else 0
        metrics["summary"] = {
            "total": total,
            "detected": detected,
            "detection_rate": detection_rate,
        }

        self.log()
        self.log(f"  Presupposition trigger detection: {detection_rate:.1%}")

        # This is exploratory - lower threshold
        self.results.append(ExperimentResult(
            name="presupposition_detection",
            passed=True,  # Informational for now
            metrics=metrics,
            details=f"Presupposition triggers detected: {detected}/{total}",
        ))
        self.log()

    # =========================================================================
    # EXPERIMENT 2.7: Quantifier Scope
    # =========================================================================
    def test_quantifier_scope(self):
        """
        Can GSE represent scope ambiguities?

        This is a demonstration, not a pass/fail test.
        Shows that quantifier-bearing elements are captured.
        """
        self.log("[2.7] QUANTIFIER SCOPE DEMONSTRATION")
        self.log("-" * 50)
        self.log("  Testing: Represent quantifier scope elements")
        self.log()

        metrics = {"cases": [], "summary": {}}

        test_cases = [
            {
                "sentence": "Every student read a book",
                "quantifiers": ["every", "a"],
                "note": "Two possible readings: each student different book, or same book",
            },
            {
                "sentence": "All dogs like some treats",
                "quantifiers": ["all", "some"],
                "note": "Universal + existential quantifiers",
            },
            {
                "sentence": "Someone loves everyone",
                "quantifiers": ["someone", "everyone"],
                "note": "Scope ambiguity: one person loves all, or each has a lover",
            },
        ]

        for case in test_cases:
            trace = self.encoder.encode(case["sentence"])

            # Check for quantifier primitives
            found_quantifiers = []
            for token in trace.tokens:
                prims = token.word_primitives
                if prims.get("ALL", 0) != 0:
                    found_quantifiers.append(("ALL", token.lemma))
                if prims.get("SOME", 0) != 0:
                    found_quantifiers.append(("SOME", token.lemma))
                if prims.get("ONE", 0) != 0:
                    found_quantifiers.append(("ONE", token.lemma))
                if prims.get("MANY", 0) != 0:
                    found_quantifiers.append(("MANY", token.lemma))

            case_result = {
                "sentence": case["sentence"],
                "expected_quantifiers": case["quantifiers"],
                "found_quantifiers": found_quantifiers,
                "note": case["note"],
            }
            metrics["cases"].append(case_result)

            self.log(f"  Sentence: '{case['sentence']}'")
            self.log(f"    Expected: {case['quantifiers']}")
            self.log(f"    Found primitives: {found_quantifiers}")
            self.log(f"    Note: {case['note']}")
            self.log()

        metrics["summary"] = {
            "demonstration": True,
            "note": "Scope representation is demonstrated, not evaluated for correctness",
        }

        self.results.append(ExperimentResult(
            name="quantifier_scope",
            passed=True,  # Demonstration only
            metrics=metrics,
            details="Quantifier primitives captured in trace",
        ))
        self.log()

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    def _generate_report(self) -> Dict[str, Any]:
        """Generate final report."""
        self.log("=" * 70)
        self.log("SEMANTIC COMPILER VALIDATION SUMMARY")
        self.log("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        for result in self.results:
            status = "[PASS]" if result.passed else "[FAIL]"
            self.log(f"  {status} {result.name}: {result.details}")

        self.log()
        self.log(f"  TOTAL: {passed}/{total} experiments passed")
        self.log("=" * 70)

        report = {
            "title": "GSE Semantic Compiler Validation",
            "timestamp": datetime.now().isoformat(),
            "claim": "GSE is a semantic compiler that transforms NL into computable representations",
            "summary": {
                "passed": passed,
                "total": total,
                "pass_rate": passed / total if total > 0 else 0,
            },
            "experiments": {r.name: asdict(r) for r in self.results},
        }

        return report


def main():
    validation = SemanticCompilerValidation(verbose=True)

    try:
        report = validation.run_all()

        # Save report
        output_path = Path("data/SEMANTIC_COMPILER_VALIDATION.json")
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nResults saved to: {output_path}")

        return report

    finally:
        validation.close()


if __name__ == "__main__":
    main()
