"""Run the new lexical-definition builder directly: python -m gse.lexicon_builder."""

import sys

from gse.lexicon_builder.audit import main as audit_main
from gse.lexicon_builder.build import main
from gse.lexicon_builder.core import _run_cli
from gse.lexicon_builder.number import main as number_main

if len(sys.argv) > 1 and sys.argv[1] == "symbolic-audit":
    raise SystemExit(audit_main())
if len(sys.argv) > 1 and sys.argv[1] == "number-order":
    raise SystemExit(number_main())
raise SystemExit(main() if len(sys.argv) > 1 and sys.argv[1] in {"build", "rules"} else _run_cli())
