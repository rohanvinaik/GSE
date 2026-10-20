#!/usr/bin/env python3
"""Retired profiler entry point; use the SquishOS voice read/compare instrument.

The replacement preserves complete source populations and explicit unavailable
channels. This stub does not import personal-wiki, read a corpus, or reinterpret
an old profile as the new schema. RohanVoice remains a separate versioned consumer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MIGRATION = {
    "state": "retired",
    "reason": "use_complete_voice_instrument",
    "replacement_schema": "voice.reading/1",
    "read": "From the declared SquishOS checkout: uv run tools/voice/voice.py read PATH",
    "compare": "From the declared SquishOS checkout: uv run tools/voice/voice.py compare ORIGINAL DRAFT",
    "environment": ["SQUISHOS_REPO", "GSE_REPO"],
    "recognizer": "scripts/rohan_voice.py (gse.rohan-voice/2; explicit manifest refit required)",
}


def migration() -> dict:
    """Return runnable replacement argv only for a declared local checkout."""
    record = dict(MIGRATION)
    declared = os.environ.get("SQUISHOS_REPO")
    if declared:
        root = Path(declared).expanduser().resolve()
        launcher = root / "tools" / "voice" / "voice.py"
        if launcher.is_file():
            command = ["uv", "run", "--project", str(root), "python", str(launcher)]
            record["read_argv"] = [*command, "read", "<path>"]
            record["compare_argv"] = [*command, "compare", "<original>", "<draft>"]
            record["launcher_state"] = "declared"
        else:
            record["launcher_state"] = "declared_launcher_missing"
    else:
        record["launcher_state"] = "squishos_repo_required"
    return record


class RetiredProfileError(RuntimeError):
    """The old profile API cannot provide the replacement's complete record."""

    migration = MIGRATION


def profile(*args, **kwargs) -> dict:
    """Explicit migration failure for callers of the retired Python function."""
    raise RetiredProfileError(
        "voice_profile.profile is retired; use uv run tools/voice/voice.py read or compare from SquishOS"
    )


def main() -> None:
    print(json.dumps(migration(), indent=2))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
