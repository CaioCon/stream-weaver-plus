#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 🎵  YOUTUBE MUSIC API — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import re
import logging

import requests as rq
from bs4 import BeautifulSoup
from ytmusicapi import YTMusic

from config import random_ua
from helpers import thumb
from database import db_cache_artist, db_cache_album

log = logging.getLogger("musicbot")
YTM = YTMusic()


# ══════════════════════════════════════════════
# BUSCA COMPLETA DE ARTISTA (3 fallbacks)
# ══════════════════════════════════════════════
def fetch_artist_full(artist_id: str) -> dict:
    """Busca discografia completa de um artista com 3 níveis de fallback."""
    info = YTM.get_artist(artist_id)
    releases: list[dict] = []
    seen: set[str] = set()

    def _add(items: list, tag: str):
        for item in (items or []):
            bid = (item.get("browseId") or item.get("playlistId") or "").strip()
            if bid and bid not in seen:
                seen.add(bid)
                r = dict(item)
                r["type"] = r.get("type") or tag
                releases.append(r)

    def _fetch_section(key: str, default_type: str):
        sec = info.get(key) or {}
        browse = (sec.get("browseId") or "").strip()
        params = (sec.get("params") or "").strip()
        channel = (info.get("channelId") or "").strip()

        # Tentativa 1: browseId da seção + params
        if browse and params:
            try:
                r = YTM.get_artist_albums(browse, params) or []
                log.info(f"  [{key}] ✅ {len(r)} via browseId+params")
                _add(r, default_type)
                return
            except Exception as e:
                log.warning(f"  [{key}] browseId+params: {e}")

        # Tentativa 2: channelId principal + params da seção
        if channel and params:
            try:
                r = YTM.get_artist_albums(channel, params) or []
                log.info(f"  [{key}] ✅ {len(r)} via channelId+params")
                _add(r, default_type)
                return
            except Exception as e:
                log.warning(f"  [{key}] channelId+params: {e}")

        # Tentativa 3: results[] embutido (limitado)
        results = sec.get("results") or []
        log.warning(f"  [{key}] ⚠ results[] fallback ({len(results)} itens)")
        _add(results, default_type)

    log.info(f"🔍 Discografia: {info.get('name', artist_id)}")
    _fetch_section("albums", "Album")
    _fetch_section("singles", "Single")
    _fetch_section("eps", "EP")

    songs = (info.get("songs") or {}).get("results") or []
    name = info.get("name", "?")
    picture = thumb(info.get("thumbnails", []), 400)

    # Persiste no DB
    try:
        db_cache_artist(artist_id, name, picture)
        for rel in releases:
            bid = rel.get("browseId", "")
            if bid:
                db_cache_album(bid, artist_id, rel.get("title", ""),
                               rel.get("type", "Album"), rel.get("year", ""),
                               thumb(rel.get("thumbnails", [])))
    except Exception as e:
        log.debug(f"_db_cache: {e}")

    log.info(f"✅ {name} → {len(releases)} lançamentos | {len(songs)} músicas")
    return {
        "info": info,
        "releases": releases,
        "songs": songs,
        "picture": picture,
        "name": name,
    }


def search(q: str) -> dict:
    """Busca artistas, álbuns e músicas no YouTube Music."""
    out = {"artists": [], "albums": [], "songs": []}
    try:
        out["artists"] = YTM.search(q, filter="artists", limit=5) or []
    except Exception:
        pass
    try:
        out["albums"] = YTM.search(q, filter="albums", limit=10) or []
    except Exception:
        pass
    try:
        out["songs"] = YTM.search(q, filter="songs", limit=10) or []
    except Exception:
        pass
    return out


def get_album(bid: str) -> dict:
    """Busca detalhes de um álbum pelo browseId."""
    return YTM.get_album(bid)


# ══════════════════════════════════════════════
# HTML FALLBACK — Busca de vídeo via scraping
# ══════════════════════════════════════════════
def yt_html_search(q: str) -> str | None:
    """Busca vídeo no YouTube via HTML scraping como fallback."""
    try:
        r = rq.get(
            f"https://www.youtube.com/results"
            f"?search_query={rq.utils.quote(q)}&sp=EgIQAQ%3D%3D",
            headers={"User-Agent": random_ua(), "Accept-Language": "en-US,en;q=0.9"},
            timeout=12,
        )
        if not r.ok:
            return None
        for s in BeautifulSoup(r.text, "html.parser").find_all("script"):
            m = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', s.string or "")
            if m:
                return f"https://www.youtube.com/watch?v={m.group(1)}"
    except Exception as e:
        log.warning(f"html_search: {e}")
    return None
