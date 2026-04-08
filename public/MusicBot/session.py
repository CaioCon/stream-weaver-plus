#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 🔑  SESSION CACHE — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import uuid

_SESSION: dict[str, dict] = {}


def cs(data: dict) -> str:
    """Cria uma chave curta e armazena dados pesados na sessão."""
    k = uuid.uuid4().hex[:12]
    _SESSION[k] = data
    return k


def cg(k: str) -> dict | None:
    """Recupera dados da sessão pela chave."""
    return _SESSION.get(k)


def session_set(k: str, data: dict) -> None:
    """Atualiza dados na sessão."""
    _SESSION[k] = data
