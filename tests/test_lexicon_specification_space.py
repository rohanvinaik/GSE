"""Intent tests for coupled-space progress through the real solver and CLI."""

import hashlib
import json
from dataclasses import replace

import pytest

from GSE.curation.cli.commands import main
from GSE.curation.lexicon_builder.engine import Assertion, DomainRestriction, Relation, propagate
from GSE.curation.lexicon_builder.epoch import _domains, _resolve, forecast, gains, question_effects
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.specification import (
    compare_measurements,
    frequency_buckets,
    measure_resolution,
    measure_space,
    space_delta,
)


def law(name, banks, rows):
    return Relation(name, banks, rows, ("synthetic:specification-intent-not-a-linguistic-law",), "foundational", True)


def test_joint_exclusion_is_progress_even_with_unchanged_marginals():
    before = propagate(("A", "B"), (), ())
    equal = law("synthetic-equal", ("A", "B"), ((-1, -1), (0, 0), (1, 1)))
    after = propagate(("A", "B"), (), (equal,))
    assert before.domains == after.domains
    assert measure_resolution(before)["possible_assignments"] == 9
    assert measure_resolution(after)["possible_assignments"] == 3
    delta = space_delta(measure_resolution(before), measure_resolution(after))
    assert delta["code"] == "CONTRACTION" and delta["removed_assignments"] == 6
    assert delta["domain_potential_gain_bits"] == 0
    assert delta["specification_gain_bits"] == pytest.approx(1.584962500721156)


def test_partial_narrowing_counts_without_assigning_a_bank():
    before = propagate(("A",), (), ())
    after = propagate(("A",), (), (), domain_restrictions=(DomainRestriction("A", (0, 1), "test", "one", "test"),))
    assert after.assignments == {}
    assert space_delta(measure_resolution(before), measure_resolution(after))[
        "specification_gain_bits"
    ] == pytest.approx(0.584962500721156)
    assert measure_resolution(after)["unresolved_banks"] == 1
    assert measure_resolution(after)["explicit_zero_banks"] == 0


def test_factorization_counts_disconnected_components_and_free_banks_once():
    eq = law("eq", ("A", "B"), ((-1, -1), (0, 0), (1, 1)))
    opposite = law("opposite", ("C", "D"), ((-1, 1), (0, 0), (1, -1)))
    state = propagate(("A", "B", "C", "D", "E"), (), (eq, opposite))
    assert measure_resolution(state)["possible_assignments"] == 27


def test_solver_limit_is_not_zero_uncertainty_or_proven_consistency():
    eq = law("eq", ("A", "B"), ((-1, -1), (0, 0), (1, 1)))
    state = propagate(("A", "B"), (), (eq,), max_joint_assignments=1)
    measured = measure_resolution(state)
    assert measured["code"] == "SOLVER_LIMIT"
    assert measured["possible_assignments"] is None and measured["specification_bits"] is None
    assert measured["upper_bound_bits"] == pytest.approx(3.169925001442312)
    assert space_delta(measured, measured)["code"] == "UNAVAILABLE"


def test_conflicts_receive_no_completion_reward():
    state = propagate(("A",), (Assertion("A", 0, "test", "a", "test"), Assertion("A", 1, "test", "b", "test")), ())
    measured = measure_resolution(state)
    assert measured["code"] == "CONFLICT"
    assert measured["possible_assignments"] == 0 and measured["specification_bits"] is None
    assert space_delta(measured, measured)["code"] == "UNAVAILABLE"


def test_missing_certificate_is_not_an_exact_joint_count():
    measured = measure_space({"A": [-1, 0, 1]}, ())
    assert measured["code"] == "MISSING_SOLVER_CERTIFICATE"
    assert measured["possible_assignments"] is None


def test_overlapping_component_receipts_cannot_double_count_support():
    state = propagate(("A", "B"), (), (law("eq", ("A", "B"), ((0, 0), (1, 1))),))
    check = next(r for r in state.trace if r["kind"] == "JOINT_CHECK")
    with pytest.raises(ValueError, match="FACTORS_NOT_DISJOINT"):
        measure_space(state.domains, (*state.trace, check))


@pytest.mark.parametrize("domains", [None, {}, {"A": [True]}, {"A": [2]}, {"A": [0, 0]}])
def test_malformed_domains_are_refused(domains):
    with pytest.raises(ValueError):
        measure_space(domains, ())


@pytest.mark.parametrize("rows", [((0,), (1,)), ((-1, -1), (0, 0), (1, 1))])
def test_production_forecast_preserves_non_singleton_gain(rows):
    definition = Definition("synthetic", "synthetic", "noun", "Synthetic diagnostic.")
    observation = {"source": "synthetic", "features": {}}
    row = (definition, (), (), observation, {})
    baseline = _resolve(row, ())
    row = (*row[:-1], _domains(baseline))
    banks = ("THINK",) if len(rows[0]) == 1 else ("THINK", "KNOW")
    report = forecast({"synthetic": row}, (), (law("test", banks, rows),))
    assert gains(report) == set()
    assert report["progress_code"] == "CONTRACTION"
    assert report["specification_gain_bits"] > 0


def test_answer_simulation_uses_coupled_constraints_without_writing():
    definition = Definition("synthetic", "synthetic", "noun", "Synthetic diagnostic.")
    observation = {"source": "synthetic", "features": {}}
    row = (definition, (), (), observation, {})
    eq = law("eq", ("THINK", "KNOW"), ((-1, -1), (0, 0), (1, 1)))
    effects = question_effects(row, (eq,), "THINK")
    assert [r["value"] for r in effects] == [-1, 0, 1]
    assert all(r["net_filled_banks"] == 2 for r in effects)
    assert row[1] == ()


def test_unproved_guard_does_not_reduce_the_space():
    before = propagate(("A",), (), ())
    guarded = replace(law("guarded", ("A",), ((0,),)), guards=(("witness", "true"),))
    after = propagate(("A",), (), (guarded,))
    assert space_delta(measure_resolution(before), measure_resolution(after))["code"] == "UNCHANGED"


def test_frequency_buckets_are_disjoint_and_include_all_spellings():
    frequencies = {f"w{i:05}": 6000 - i for i in range(5100)}
    result = frequency_buckets([*frequencies, "NO_FREQUENCY"], frequencies)
    assert len(result) == 5101
    assert result["w00499"] == "1-500" and result["w00500"] == "501-1500"
    assert result["w01499"] == "501-1500" and result["w01500"] == "1501-5000"
    assert result["w04999"] == "1501-5000" and result["w05000"] == "5001+"
    assert result["no_frequency"] == "unranked"


def test_public_measure_cli_keeps_all_senses_and_does_not_modify_database(tmp_path, monkeypatch, capsys):
    database, frequency, report = (tmp_path / name for name in ("lexicon.db", "frequency.csv", "measurement.json"))
    definitions = (
        Definition("alpha:1", "alpha", "noun", "Synthetic first sense."),
        Definition("alpha:2", "alpha", "noun", "Synthetic second sense."),
        Definition("beta:1", "beta", "noun", "Synthetic unranked sense."),
    )
    build_dictionary(EvidenceBundle(definitions, (), (), ()), database)
    frequency.write_text("Word,SUBTLEX\nalpha,100\nbeta,0\n")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "sys.argv",
        [
            "lexicon",
            "--lexicon-db",
            str(database),
            "measure",
            "--frequency-file",
            str(frequency),
            "--report",
            str(report),
        ],
    )
    main()
    measured = json.loads(capsys.readouterr().out)
    assert measured == json.loads(report.read_text())
    assert measured["lexicon"]["definitions"] == 3 and measured["lexicon"]["spellings"] == 2
    assert measured["buckets"]["1-500"]["definitions"] == 2
    assert measured["buckets"]["unranked"]["definitions"] == 1
    assert measured["lexicon"]["exact_definitions"] == 3
    assert compare_measurements(measured, measured)["lexicon"]["specification_gain_bits"] == 0
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    changed = dict(measured, cohort_sha256="changed")
    with pytest.raises(ValueError, match="POPULATION_CHANGED"):
        compare_measurements(measured, changed)
