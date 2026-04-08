#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 🛠️  HELPERS GERAIS — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import uuid
import shutil
import logging
from pathlib import Path

from telegram import Update

from config import OWNER_ID, CFG, CACHE_DIR

log = logging.getLogger("musicbot")


def thumb(thumbs: list, min_w: int = 300) -> str:
    """Seleciona a melhor thumbnail da lista."""
    if not thumbs:
        return ""
    pool = [t for t in thumbs if t.get("width", 0) >= min_w] or thumbs
    return max(pool, key=lambda t: t.get("width", 0)).get("url", "")


def cut(t: str, n: int = 36) -> str:
    """Trunca texto com reticências."""
    t = str(t or "")
    return t if len(t) <= n else t[:n - 1] + "…"


def sec(s) -> str:
    """Converte segundos em formato legível."""
    if not s:
        return "?:??"
    h, r = divmod(int(s), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ico(tp: str) -> str:
    """Retorna ícone baseado no tipo de lançamento."""
    return {"single": "🎵", "ep": "📀"}.get(str(tp or "").lower(), "💿")


def is_owner(u: Update) -> bool:
    """Verifica se o usuário é o owner do bot."""
    return bool(u.effective_user and u.effective_user.id == OWNER_ID)


def dm_ok(u: Update) -> bool:
    """Verifica se buscas estão ativas para o usuário."""
    return True if is_owner(u) else CFG["dm_on"]


def work_dir() -> Path:
    """Cria diretório temporário para download."""
    d = CACHE_DIR / uuid.uuid4().hex
    d.mkdir(parents=True, exist_ok=True)
    return d


def cleanup(path) -> None:
    """Remove arquivo/diretório temporário após envio."""
    try:
        p = Path(path)
        parent = p.parent
        if parent != CACHE_DIR and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
    except Exception as e:
        log.debug(f"cleanup: {e}")


def ensure_dirs():
    """Garante que os diretórios base existem."""
    from config import BASE_DIR
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
