"""
Configurações centrais do bot
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_USERS: list[int] = [
    int(uid) for uid in os.getenv("ALLOWED_USERS", "").split(",") if uid.strip()
]

# ── Deezer ────────────────────────────────────────────────────────
ARL_TOKEN: str = os.getenv("ARL_TOKEN", "")

# ── Download ──────────────────────────────────────────────────────
DOWNLOAD_PATH: Path = Path(os.getenv("DOWNLOAD_PATH", "./downloads"))
MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", 10))

# ── Qualidade de Áudio ────────────────────────────────────────────
BITRATE_MAP: dict[str, str] = {
    "flac": "9",       # FLAC Lossless
    "mp3_320": "3",    # MP3 320kbps
    "mp3_128": "1",    # MP3 128kbps
}

QUALITY_LABELS: dict[str, str] = {
    "flac": "🎼 FLAC (Lossless)",
    "mp3_320": "🎵 MP3 320kbps",
    "mp3_128": "🎶 MP3 128kbps",
}

DEFAULT_QUALITY: str = "mp3_320"

# ── Padrões de URL Deezer ─────────────────────────────────────────
URL_PATTERNS: dict[str, str] = {
    "track": r"deezer\.com(?:/[a-z]{2})?/track/(\d+)",
    "album": r"deezer\.com(?:/[a-z]{2})?/album/(\d+)",
    "playlist": r"deezer\.com(?:/[a-z]{2})?/playlist/(\d+)",
    "artist": r"deezer\.com(?:/[a-z]{2})?/artist/(\d+)",
    "genre": r"deezer\.com(?:/[a-z]{2})?/genre/(\d+)",
}

TYPE_EMOJI: dict[str, str] = {
    "track": "🎵",
    "album": "💿",
    "playlist": "📋",
    "artist": "🎸",
    "genre": "🎼",
}

TYPE_LABEL: dict[str, str] = {
    "track": "Música",
    "album": "Álbum",
    "playlist": "Playlist",
    "artist": "Artista",
    "genre": "Gênero",
}
