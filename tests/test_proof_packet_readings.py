"""The proof packet's readings that still reproduce are protected (GSE-00, task 8.1).

On 2026-11-24 the dated proof packet (``resume/Communication/vision/GSE/GSE_Proof_Packet.md``) was re-run
against the code (``docs/readings/2026-11-24-proof-packet-rerun/``). Sections 1, 3, 4 and 6 reproduced. These
tests pin those readings through the packet's own reproduce command, ``scripts/proof_packet.py``, so a change
that alters them fails here instead of being found by the next re-run.

What is pinned is the reading: which way a comparison or a cause points, each verdict, and each proof chain.
Two printed values are not pinned. The encoding hash changed with the lexicon (``b1aacd8a02f3`` in the packet),
so only its determinism is checked. The bag-of-words cosine of section 1 is 1.0 for any reordering of the same
words, so it distinguishes nothing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def packet():
    spec = importlib.util.spec_from_file_location("proof_packet", ROOT / "scripts/proof_packet.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module._ENC.close()


def _printed(capsys) -> list[str]:
    return [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip()]


def test_swapping_the_arguments_reverses_the_comparison(packet):
    # Section 1: the same words in a different order are opposite claims.
    a = packet.predicates(packet.pipe("The zorble is bigger than the florp"))[0]
    b = packet.predicates(packet.pipe("The florp is bigger than the zorble"))[0]
    assert packet.show(a) == "Comparison(zorble > florp, axis=big)"
    assert packet.show(b) == "Comparison(florp > zorble, axis=big)"


def test_clause_order_reverses_the_causation(packet):
    # Section 1: which clause is the cause follows the connective, not the word bag.
    assert (
        packet.show(packet.pipe("Rex barks because the dog is cute"))
        == "Causation(cause=TypeAssertion(dog is_a cute) → effect=Event(bark: rex))"
    )
    assert (
        packet.show(packet.pipe("The dog is cute because Rex barks"))
        == "Causation(cause=Event(bark: rex) → effect=TypeAssertion(dog is_a cute))"
    )


def test_encoding_is_byte_identical_across_runs(packet):
    sentence = "Macbeth murdered Duncan and Macduff killed Macbeth."
    assert len({packet.vec_hash(sentence) for _ in range(3)}) == 1


def test_lsat_derivations_and_refusals(packet):
    # Section 3: multi-step derivation from raw text, a conditional that fires, and two refusals.
    assert [str(d) for d in packet._run_lsat(packet._LSAT)] == [
        "greater(mike, bob)  =  TRUE     ⊢  mike → rex → spot → bob",
        "is_a(mike, animal)  =  TRUE     ⊢  mike → poodle → dog → animal",
        "greater(bob, mike)  =  not entailed",
        "is_a(mike, knife)  =  not entailed",
        "event(mike, mike win)  =  TRUE     ⊢  mike → rex → spot → bob → mike → poodle → "
        "rule: poodle > bob ⇒ poodle win → ∴ mike win",
    ]


def test_needle_correctness_does_not_decay_with_distance(packet, capsys):
    # Section 4: the proof grows with the chain, and the reverse is refused at every length.
    packet.needle()
    assert _printed(capsys)[-4:] == [
        "chain length  10  (30 sentences): greater(kakan, sakan) = True  [proof: 10 steps]   reverse: REFUSED",
        "chain length  25  (75 sentences): greater(kakan, vekan) = True  [proof: 25 steps]   reverse: REFUSED",
        "chain length  50  (150 sentences): greater(kakan, tokan) = True  [proof: 50 steps]   reverse: REFUSED",
        "chain length 100  (300 sentences): greater(kakan, riban) = True  [proof: 100 steps]   reverse: REFUSED",
    ]


def test_policy_ruling_cites_its_chain_and_refuses_the_rest(packet, capsys):
    # Section 6: rules and facts give a ruling with its chain; no fact, no ruling.
    packet.policy()
    assert _printed(capsys)[-4:] == [
        "event(alice, alice lose vote)  =  TRUE     ⊢  fact: alice miss payment → alice → member → "
        "rule: member miss payment ⇒ member lose vote → ∴ alice lose vote",
        "event(alice, alice leave board)  =  TRUE     ⊢  fact: alice miss payment → alice → member → "
        "rule: member miss payment ⇒ member lose vote → ∴ alice lose vote → alice → member → "
        "rule: member lose vote ⇒ member leave board → ∴ alice leave board",
        "event(bob, bob lose vote)  =  not entailed",
        "event(carol, carol lose vote)  =  not entailed",
    ]
