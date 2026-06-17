"""
Store transitório do fluxo OAuth (PKCE/state) entre /login e /callback.

Não há sessão persistente nem cookie: o objetivo é apenas guardar o
code_verifier/nonce entre o início do login e o callback. Em memória.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PendingLogin:
    """Estado transitório do fluxo OAuth entre /login e /callback (PKCE)."""

    state: str
    code_verifier: str
    nonce: str
    created_at: float = field(default_factory=time.time)


class PendingStore:
    """Store em memória dos logins pendentes (state -> PKCE)."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}

    def save(self, pending: PendingLogin) -> None:
        self._pending[pending.state] = pending

    def pop(self, state: str | None) -> PendingLogin | None:
        if not state:
            return None
        return self._pending.pop(state, None)

    def cleanup(self, max_age: int = 600) -> None:
        """Remove logins pendentes antigos (expiração do fluxo)."""
        now = time.time()
        expired = [s for s, p in self._pending.items() if now - p.created_at > max_age]
        for s in expired:
            self._pending.pop(s, None)


pending_store = PendingStore()
