"""
Store transitório do fluxo OAuth (PKCE/state) entre /login e /callback.

Não há sessão persistente nem cookie: o objetivo é apenas guardar o
code_verifier/nonce entre o início do login e o callback. Em memória.
"""

from __future__ import annotations

import secrets
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


@dataclass
class LoginResult:
    """Resultado do login (payload do callback) guardado por um token curto."""

    token: str
    payload: dict
    created_at: float = field(default_factory=time.time)


class ResultStore:
    """
    Store em memória do RESULTADO do login (token -> payload).

    Depois do callback, o payload completo (Entra + CAv4 + Graph) fica guardado
    aqui por alguns minutos, associado a um token aleatório. O frontend recebe
    apenas o token na URL (/viewer?r=TOKEN) e busca o payload em
    GET /auth/result/{token}. Assim os dados não trafegam pela URL.
    """

    def __init__(self) -> None:
        self._results: dict[str, LoginResult] = {}

    def save(self, payload: dict) -> str:
        """Guarda o payload e devolve um token de uso curto para recuperá-lo."""
        self.cleanup()
        token = secrets.token_urlsafe(32)
        self._results[token] = LoginResult(token=token, payload=payload)
        return token

    def get(self, token: str | None) -> dict | None:
        """Lê o payload pelo token (sem remover; expira por tempo)."""
        if not token:
            return None
        result = self._results.get(token)
        return result.payload if result else None

    def cleanup(self, max_age: int = 600) -> None:
        """Remove resultados antigos (expiração de 10 minutos por padrão)."""
        now = time.time()
        expired = [t for t, r in self._results.items() if now - r.created_at > max_age]
        for t in expired:
            self._results.pop(t, None)


result_store = ResultStore()
