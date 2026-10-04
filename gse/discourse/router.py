"""The Society-of-Mind register router — the L2 dispatcher.

A small learned ensemble over GSE's deterministic feature profile (it never sees
text — only the numeric banks `text_profile` produces). Faithful to the SoM design:

* **bank specialists** — one per feature bank (operator_mix / complexity /
  coherence / affect / register / primitives). Each sees *its* bank through a
  high-capacity encoder AND the full profile through a low-capacity encoder (the
  asymmetric dual path that makes it a specialist without going blind to context).
* **orchestrator** — a trust head that softmaxes over the specialists from the full
  profile; the final genre logits are the trust-weighted sum of specialist logits.

Trained three-stage (specialists → frozen-specialist orchestrator → joint), see
``scripts/train_register_router.py``. Sized small for the classical-AI-scale corpus.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import torch
import torch.nn as nn

# Bank order = the specialists, matching gse.discourse.profile.TextProfile banks.
BANKS: Sequence[str] = (
    "operator_mix", "complexity", "coherence", "affect", "register", "primitives",
)


def banks_to_tensors(banks: Dict[str, Dict[str, float]]) -> List[torch.Tensor]:
    """One feature tensor per bank, in ``BANKS`` order (keys sorted for stability)."""
    return [torch.tensor([banks[b][k] for k in sorted(banks[b])], dtype=torch.float32)
            for b in BANKS]


class _BankSpecialist(nn.Module):
    """Dual-path: its bank at high capacity + the full profile at low capacity."""

    def __init__(self, bank_dim: int, full_dim: int, n_genres: int,
                 hi: int = 24, lo: int = 12):
        super().__init__()
        self.bank_enc = nn.Sequential(
            nn.Linear(bank_dim, hi), nn.LayerNorm(hi), nn.GELU())
        self.ctx_enc = nn.Sequential(nn.Linear(full_dim, lo), nn.GELU())
        self.head = nn.Linear(hi + lo, n_genres)

    def forward(self, bank_x: torch.Tensor, full_x: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.bank_enc(bank_x), self.ctx_enc(full_x)], -1))


class RegisterRouter(nn.Module):
    """SoM register router: bank specialists + a trust-softmax orchestrator."""

    def __init__(self, bank_dims: Sequence[int], full_dim: int, n_genres: int):
        super().__init__()
        self.specialists = nn.ModuleList(
            [_BankSpecialist(d, full_dim, n_genres) for d in bank_dims])
        self.orch_ctx = nn.Sequential(nn.Linear(full_dim, 32), nn.GELU())
        self.trust_head = nn.Linear(32, len(bank_dims))

    def specialist_logits(self, banks_x: Sequence[torch.Tensor],
                          full_x: torch.Tensor) -> torch.Tensor:
        # [B, n_specialists, n_genres]
        return torch.stack([sp(banks_x[i], full_x)
                            for i, sp in enumerate(self.specialists)], dim=1)

    def trust(self, full_x: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.trust_head(self.orch_ctx(full_x)), dim=-1)  # [B, S]

    def forward(self, banks_x: Sequence[torch.Tensor],
                full_x: torch.Tensor) -> torch.Tensor:
        spec = self.specialist_logits(banks_x, full_x)        # [B, S, G]
        trust = self.trust(full_x)                            # [B, S]
        return (trust.unsqueeze(-1) * spec).sum(dim=1)        # [B, G]

    def freeze_specialists(self, frozen: bool = True) -> None:
        for p in self.specialists.parameters():
            p.requires_grad = not frozen
