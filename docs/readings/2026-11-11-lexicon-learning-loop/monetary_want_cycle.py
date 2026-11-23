"""Audit the monetary WANT rule and continue exact residual lexicon work."""

import argparse

from audit_volume_want import WantAudit, audit, prepare, review
from complete_unit_want_cycle import DATA
from complete_volume_want_cycle import OUTPUT as BASELINE
from complete_volume_want_cycle import ResidualCycle, finish, probe, retry_timeouts

MONETARY = WantAudit(
    prefix="monetary-want",
    baseline=BASELINE,
    parent_report="volume-want-cycle-verification.json",
    ancestor="monetary_unit.n.01",
    seeds=(
        (
            "wordnet:real:real.n.02",
            "real-discovery",
            "The Brazilian denomination is defined by equivalence to 100 centavos. The exchange scale leaves desire orthogonal.",
        ),
        (
            "wordnet:sent:sent.n.01",
            "sent-discovery",
            "The Estonian denomination is defined by its fraction of a kroon. No conative role is constitutive of the unit.",
        ),
        (
            "wordnet:bob:british_shilling.n.01",
            "bob-discovery",
            "The former British shilling denotes a denomination. Its historical exchange role is compatible with different desires.",
        ),
    ),
    held_out=(
        "wordnet:anna:anna.n.01",
        "wordnet:dollar:dollar.n.01",
        "wordnet:eurodollar:eurodollar.n.01",
        "wordnet:penny:penny.n.01",
    ),
    exclusions=(),
    statement=(
        "An exact attested native monetary-unit noun in this reviewed WordNet branch denotes a denomination, "
        "a coin distinguished by its denomination, or a currency amount in deposit. The denomination or amount "
        "has the same definitional identity across different desires of holders, depositors, and counterparties. "
        "WANT=0 records that orthogonality for the witnessed monetary role. Copper as the coin material, "
        "trade financing as an application, and economic value as a relation among denominations do not introduce "
        "a conative argument into the unit. The ancestry and native lemma guards confine the rule to exact "
        "source senses, including where their spellings have unrelated meanings."
    ),
    rule_slug="monetary",
)

MONETARY_CYCLE = ResidualCycle(
    audit=MONETARY,
    migrated=DATA / "constructed-corpus-monetary-want.db",
    output=DATA / "constructed-corpus-monetary-want-zipf.db",
    quantity_reviews={
        "wordnet:em:em.n.01": (
            1,
            "The historical printer's glossary and the Amalgamated Printers' Association describe the same "
            "square spacing block, also called mutton quad in the latter. Its width equals the type body size. "
            "An equal-side artifact can have arbitrary absolute size, but this exact spacer denotes one type "
            "body of horizontal spacing by convention. This resolves the size-standard issue in the prior review.",
        ),
        "wordnet:emu:electromagnetic_unit.n.01": (
            None,
            "NIST distinguishes EMU as the cgs electromagnetic system from the use of emu for an individual "
            "unit of magnetic moment. The exact corpus gloss denotes a system. A quantitative subject matter "
            "is compatible with a system-level definition, and the unit abbreviation does not resolve that bank here.",
        ),
        "wordnet:partition:partition.n.02": (
            None,
            "The UEFI specification defines a GPT partition as a range with specified start and end addresses. "
            "Its span can be counted, but different extents remain partitions and 'single unit' in the corpus "
            "gloss specifies access. This source establishes the extent of each object rather than a lexical "
            "standard, count, or magnitude for this exact definition.",
        ),
        "wordnet:word:word.n.07": (
            1,
            "The RISC-V and IBM storage specifications define a 32-bit word, while the Intel data-type "
            "specification defines a 16-bit word. The stored bit string "
            "in this exact corpus sense is that conventional unit of information. The positive sign encodes "
            "the grouping, with no shared bit count imposed across architectures or other word senses.",
        ),
    },
    zipf_reviews={
        "wordnet:stone:stone.n.05": "The stone denotes a standard of fourteen pounds. Application to weighing people is independent of a person's desire.",
        "wordnet:block:block.n.06": "The computer-storage block is a minimum permitted data granule. Its size follows the storage system's structure.",
        "wordnet:weight:weight_unit.n.02": "This exact weight is a standard for measuring weight. The magnitude is independent of an agent's wants.",
        "wordnet:unit:unit_of_measurement.n.01": "This unit is a recognized quantitative standard. Acceptance establishes the convention across different purposes of measuring or exchanging.",
        "wordnet:grade:grad.n.01": "The grade is an angular fraction of a right angle. Its mathematical scale is independent of desire.",
        "wordnet:section:section.n.07": "The section is a land-area unit equal to one square mile. Its survey magnitude is independent of ownership or desire for land.",
    },
    source_refs={
        "wordnet:em:em.n.01": (
            "https://apa-letterpress.com/?page_id=26201",
            "https://upload.wikimedia.org/wikipedia/commons/a/a2/The_printer%27s_dictionary_of_technical_terms%3B_a_handbook_of_definitions_and_information_about_processes_of_printing_%28IA_printersdictiona00stew%29.pdf",
        ),
        "wordnet:emu:electromagnetic_unit.n.01": (
            "https://www.nist.gov/publications/persistence-electromagnetic-units-magnetism",
            "https://www.nist.gov/system/files/documents/pml/electromagnetics/magnetics/magnetic_units.pdf",
        ),
        "wordnet:partition:partition.n.02": ("https://uefi.org/specs/UEFI/2.11/05_GUID_Partition_Table_Format.html",),
        "wordnet:word:word.n.07": (
            "https://docs.riscv.org/reference/isa/v20250508/unpriv/intro.html#memory",
            "https://www.ibm.com/docs/en/module_1678991624569/pdf/SA22-7832-13.pdf",
            "https://cdrdv2-public.intel.com/843827/253665-sdm-vol-1-dec-24.pdf",
        ),
    },
    probe_without_warrant=False,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "audit", "review", "probe", "retry", "finish"))
    args = parser.parse_args()
    if args.phase in {"probe", "retry", "finish"}:
        {"probe": probe, "retry": retry_timeouts, "finish": finish}[args.phase](MONETARY_CYCLE)
    else:
        {"prepare": prepare, "audit": audit, "review": review}[args.phase](MONETARY)
