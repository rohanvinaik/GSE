"""rohan_voice, the recognizer the SquishOS voice tool's `recognize` runs, reads its banks from GSE's registry (#148).

Its hand copy put 12 of the 73 primes in the wrong bank and lacked CERTAINTY, so its bank features disagreed with
every other reader of GSE's banks.
"""

import sys
from pathlib import Path

from gse.primitives_v2 import SemanticBank, get_all_primitives, get_bank_for_primitive

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rohan_voice  # noqa: E402  (a script, importable from scripts/)


def test_every_prime_sits_in_its_gse_bank():
    registry = {p: get_bank_for_primitive(p) for p in get_all_primitives()}
    assert {p: b.name for p, b in registry.items() if b is not None} == rohan_voice.BANK_MAP
    assert set(rohan_voice.BANK_MAP) == set(registry)  # every prime, CERTAINTY included


def test_the_bank_features_cover_exactly_gse_banks():
    # BANKS orders the model's bank features: a bank outside it would be counted and silently dropped.
    assert sorted(rohan_voice.BANKS) == sorted(b.name for b in SemanticBank)
    assert set(rohan_voice.BANK_MAP.values()) <= set(rohan_voice.BANKS)
