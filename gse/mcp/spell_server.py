"""SymbolicSpellCheck MCP transport over :mod:`gse.nlp.heal`.

Correction, protection, learning, source edits and policy identities are owned by
that reusable core. Import the core directly when MCP transport is not needed.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from gse.nlp import heal
from gse.nlp.heal import _hdc_recover as _hdc_recover
from gse.nlp.heal import _hdc_tiebreak as _hdc_tiebreak

mcp = FastMCP("SymbolicSpellCheck")


@mcp.tool()
def spell_suggest(text: str, n: int = 5) -> dict[str, Any]:
    """Shared deterministic correction with exact source spans and an edit ledger."""
    return heal.suggest(text, n=n)


@mcp.tool()
def spell_learn(
    word: str, kind: str = "term", aliases: list[str] | None = None, definition: str | None = None
) -> dict[str, Any]:
    """Persist protected spelling through the shared typed learning operation."""
    if kind == "term" and aliases is None and definition is None:
        return heal.learn(word)
    return heal.learn({"surface": word, "kind": kind, "aliases": aliases or [], "definition": definition})


@mcp.tool()
def spell_boundaries(text: str) -> dict[str, Any]:
    """Offer uncertain sentence boundaries without silently changing the text."""
    return heal.boundaries(text)


def main() -> None:
    """Console entry point for the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
