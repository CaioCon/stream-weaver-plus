"""
Funções utilitárias do bot
"""

import re
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def detect_url_type(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Detecta o tipo e ID de uma URL do Deezer.
    Retorna (tipo, id) ou (None, None).
    """
    from config import URL_PATTERNS

    for url_type, pattern in URL_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            return url_type, match.group(1)
    return None, None

def build_deezer_url(url_type: str, item_id: str) -> str:
    """Constrói uma URL do Deezer a partir do tipo e ID."""
    return f"https://www.deezer.com/{url_type}/{item_id}"

def get_free_space(path: Path) -> str:
    """Retorna o espaço em disco disponível formatado."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        total, used, free = shutil.disk_usage(path)
        if free >= 1024 ** 3:
            return f"{free / (1024 ** 3):.1f} GB"
        return f"{free / (1024 ** 2):.0f} MB"
    except Exception:
        return "N/A"

def format_duration(seconds: int) -> str:
    """Formata duração em segundos para mm:ss ou hh:mm:ss."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_number(n: int) -> str:
    """Formata número com separador de milhar."""
    return f"{n:,}".replace(",", ".")

def is_user_allowed(user_id: int) -> bool:
    """Verifica se um usuário tem permissão para usar o bot."""
    from config import ALLOWED_USERS
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

def setup_logging() -> logging.Logger:
    """Configura e retorna o logger principal."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    return logging.getLogger("MusicBot")
