#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 🗄️  BANCO DE DADOS SQLite — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import sqlite3
import logging
from datetime import datetime
from threading import Lock

from config import BASE_DIR, CACHE_DIR, DB_PATH

log = logging.getLogger("musicbot")
_DB_LOCK = Lock()


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_init():
    """Cria todas as tabelas se não existirem."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK, _db_conn() as conn:
        conn.executescript("""
        -- ── Usuários ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name   TEXT NOT NULL DEFAULT '',
            username    TEXT NOT NULL DEFAULT '',
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        );

        -- ── Tópicos de grupo ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS topic_configs (
            chat_id  INTEGER PRIMARY KEY,
            topic_id INTEGER NOT NULL,
            set_by   INTEGER NOT NULL,
            set_at   TEXT NOT NULL
        );

        -- ── Artistas ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS artists (
            ytm_id      TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            picture_url TEXT DEFAULT '',
            cached_at   TEXT NOT NULL
        );

        -- ── Álbuns ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS albums (
            ytm_id     TEXT PRIMARY KEY,
            artist_id  TEXT NOT NULL REFERENCES artists(ytm_id),
            title      TEXT NOT NULL,
            album_type TEXT DEFAULT 'Album',
            year       TEXT DEFAULT '',
            cover_url  TEXT DEFAULT '',
            cached_at  TEXT NOT NULL
        );

        -- ── Músicas ───────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS tracks (
            video_id     TEXT PRIMARY KEY,
            album_id     TEXT REFERENCES albums(ytm_id),
            artist_id    TEXT REFERENCES artists(ytm_id),
            title        TEXT NOT NULL,
            track_number INTEGER DEFAULT 0,
            duration_sec INTEGER DEFAULT 0,
            cover_url    TEXT DEFAULT ''
        );

        -- ── Log de Downloads ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS download_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(telegram_id),
            video_id     TEXT DEFAULT '',
            title        TEXT DEFAULT '',
            artist       TEXT DEFAULT '',
            album        TEXT DEFAULT '',
            requested_at TEXT NOT NULL,
            sent_at      TEXT DEFAULT '',
            success      INTEGER DEFAULT 0
        );

        -- Índices
        CREATE INDEX IF NOT EXISTS idx_dl_user   ON download_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_dl_video  ON download_logs(video_id);
        CREATE INDEX IF NOT EXISTS idx_albums_art ON albums(artist_id);
        CREATE INDEX IF NOT EXISTS idx_tracks_alb ON tracks(album_id);
        """)
        conn.commit()
    log.info(f"🗄 DB inicializado: {DB_PATH}")


# ══════════════════════════════════════════════
# HELPERS DO DB
# ══════════════════════════════════════════════
def db_upsert_user(user) -> None:
    """Insere ou atualiza usuário no banco."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    uid = user.id
    name = (user.full_name or "").strip()
    un = (f"@{user.username}" if user.username else "")
    with _DB_LOCK, _db_conn() as conn:
        conn.execute("""
            INSERT INTO users(telegram_id, full_name, username, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username  = excluded.username,
                last_seen = excluded.last_seen
        """, (uid, name, un, now, now))
        conn.commit()


def db_set_topic(chat_id: int, topic_id: int, set_by: int) -> None:
    """Configura tópico de um grupo."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _DB_LOCK, _db_conn() as conn:
        conn.execute("""
            INSERT INTO topic_configs(chat_id, topic_id, set_by, set_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                topic_id = excluded.topic_id,
                set_by   = excluded.set_by,
                set_at   = excluded.set_at
        """, (chat_id, topic_id, set_by, now))
        conn.commit()


def db_get_topic(chat_id: int) -> int | None:
    """Retorna o topic_id configurado ou None."""
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT topic_id FROM topic_configs WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return row["topic_id"] if row else None


def db_del_topic(chat_id: int) -> None:
    """Remove configuração de tópico."""
    with _DB_LOCK, _db_conn() as conn:
        conn.execute("DELETE FROM topic_configs WHERE chat_id = ?", (chat_id,))
        conn.commit()


def db_log_download(user_id: int, meta: dict | None) -> int:
    """Registra um download pendente. Retorna o ID do log."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    m = meta or {}
    with _DB_LOCK, _db_conn() as conn:
        cur = conn.execute("""
            INSERT INTO download_logs
                (user_id, video_id, title, artist, album, requested_at, success)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (user_id, m.get("video_id", ""), m.get("title", ""),
              m.get("artist", ""), m.get("album", ""), now))
        conn.commit()
        return cur.lastrowid


def db_log_sent(log_id: int) -> None:
    """Marca download como enviado com sucesso."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with _DB_LOCK, _db_conn() as conn:
        conn.execute(
            "UPDATE download_logs SET success=1, sent_at=? WHERE id=?",
            (now, log_id))
        conn.commit()


def db_cache_artist(artist_id: str, name: str, picture: str) -> None:
    """Salva artista no cache do DB."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _DB_LOCK, _db_conn() as conn:
        conn.execute("""
            INSERT INTO artists(ytm_id, name, picture_url, cached_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ytm_id) DO UPDATE SET
                name=excluded.name, picture_url=excluded.picture_url,
                cached_at=excluded.cached_at
        """, (artist_id, name, picture, now))
        conn.commit()


def db_cache_album(ytm_id: str, artist_id: str, title: str,
                   atype: str, year: str, cover: str) -> None:
    """Salva álbum no cache do DB."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _DB_LOCK, _db_conn() as conn:
        conn.execute("""
            INSERT INTO albums(ytm_id, artist_id, title, album_type, year, cover_url, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ytm_id) DO UPDATE SET
                title=excluded.title, album_type=excluded.album_type,
                year=excluded.year, cover_url=excluded.cover_url,
                cached_at=excluded.cached_at
        """, (ytm_id, artist_id, title, atype, year, cover, now))
        conn.commit()


def db_stats() -> dict:
    """Retorna estatísticas gerais do banco."""
    with _db_conn() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        tracks = conn.execute("SELECT COUNT(*) FROM download_logs").fetchone()[0]
        ok = conn.execute(
            "SELECT COUNT(*) FROM download_logs WHERE success=1").fetchone()[0]
        topics = conn.execute("SELECT COUNT(*) FROM topic_configs").fetchone()[0]
        artists = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
        albums = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
    return {
        "users": users, "downloads": tracks, "sent": ok,
        "topics": topics, "artists": artists, "albums": albums
    }
