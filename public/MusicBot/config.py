#!/usr/bin/env python3
# ══════════════════════════════════════════════
# ⚙️  CONFIGURAÇÕES — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import os
import sys
import subprocess
import importlib.util
import shutil
import random
from pathlib import Path

# ── Token e Owner ─────────────────────────────
BOT_TOKEN = "8618840827:AAHohLnNTWh_lkP4l9du6KJTaRQcPsNrwV8"
OWNER_ID = 2061557102

# ── Qualidade e Limites ───────────────────────
AUDIO_QUALITY = "192"
MAX_BATCH = 15
ALBUMS_PAGE = 6
SONGS_PAGE = 8
MAX_DL_SLOTS = 8

# ── Estado global ─────────────────────────────
CFG: dict = {"dm_on": True}

# ── Diretórios ────────────────────────────────
BASE_DIR = Path("/sdcard/Usuário bot Music")
DB_PATH = BASE_DIR / "musicbot.db"
CACHE_DIR = BASE_DIR / "cache"

# ── User Agents ───────────────────────────────
_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

def random_ua() -> str:
    return random.choice(_UAS)

# ── Ferramentas externas ──────────────────────
HAS_FFMPEG = bool(shutil.which("ffmpeg"))
HAS_ARIA2C = bool(shutil.which("aria2c"))


# ══════════════════════════════════════════════
# BOOTSTRAP — Instala dependências ausentes
# ══════════════════════════════════════════════
def bootstrap():
    pkgs = {
        "telegram": "python-telegram-bot>=20.7",
        "yt_dlp": "yt-dlp",
        "mutagen": "mutagen",
        "requests": "requests",
        "rich": "rich",
        "ytmusicapi": "ytmusicapi",
        "bs4": "beautifulsoup4",
    }
    miss = [pip for mod, pip in pkgs.items() if not importlib.util.find_spec(mod)]
    if miss:
        print(f"📦 Instalando: {', '.join(miss)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *miss, "-q"])
