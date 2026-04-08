#!/usr/bin/env python3
# ══════════════════════════════════════════════
# ⬇️  DOWNLOADER & TAGGER — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import os
import shutil
import asyncio
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests as rq
import yt_dlp

from config import (
    AUDIO_QUALITY, MAX_DL_SLOTS,
    HAS_FFMPEG, HAS_ARIA2C, random_ua,
)
from helpers import work_dir, cleanup

log = logging.getLogger("musicbot")

# ── Thread Pools ──────────────────────────────
SEARCH_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="search")
DL_POOL = ThreadPoolExecutor(max_workers=MAX_DL_SLOTS + 4, thread_name_prefix="dl")
DL_SEM: asyncio.Semaphore | None = None


async def run_search(fn, *args):
    """Executa função no pool de busca."""
    return await asyncio.get_event_loop().run_in_executor(SEARCH_POOL, fn, *args)


async def run_dl(fn, *args):
    """Executa função no pool de download."""
    return await asyncio.get_event_loop().run_in_executor(DL_POOL, fn, *args)


def init_semaphore():
    """Inicializa o semáforo de download (deve ser chamado no loop asyncio)."""
    global DL_SEM
    DL_SEM = asyncio.Semaphore(MAX_DL_SLOTS)


# ══════════════════════════════════════════════
# ESTRATÉGIAS DE DOWNLOAD
# ══════════════════════════════════════════════
_STRATEGIES: list[tuple[list, str]] = [
    (["ios"], "bestaudio/best"),
    (["ios"], "best"),
    (["android"], "bestaudio/best"),
    (["android"], "best"),
    (["mweb"], "bestaudio/best"),
    (["web"], "bestaudio/best"),
    (["web"], "best"),
]


def _build_opts(out_dir: str, fmt: str, clients: list) -> dict:
    """Constrói opções do yt-dlp para uma estratégia."""
    o: dict = {
        "format": fmt,
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cachedir": False,
        "age_limit": 99,
        "retries": 3,
        "fragment_retries": 5,
        "socket_timeout": 20,
        "extractor_args": {
            "youtube": {"player_client": clients, "player_skip": ["webpage"]}
        },
        "http_headers": {"User-Agent": random_ua(), "Accept-Language": "en-US,en;q=0.9"},
    }
    if HAS_ARIA2C:
        o["external_downloader"] = "aria2c"
        o["external_downloader_args"] = {
            "default": ["-x16", "-k1M", "--min-split-size=1M",
                        "-j16", "--quiet", "--no-conf"]
        }
    if HAS_FFMPEG:
        o["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": AUDIO_QUALITY,
        }]
    return o


def _locate_file(raw: str) -> str | None:
    """Localiza o arquivo baixado (pode ter extensão diferente)."""
    stem = os.path.splitext(raw)[0]
    for ext in (".mp3", ".m4a", ".opus", ".webm", ".ogg", ".aac"):
        if os.path.isfile(stem + ext):
            return stem + ext
    return raw if os.path.isfile(raw) else None


def _try_download(target: str, out_dir: str) -> tuple[dict | None, str]:
    """Tenta baixar usando todas as estratégias disponíveis."""
    last_err = "Erro desconhecido"
    captured: list[str] = []

    def _hook(d):
        if d["status"] == "finished":
            captured.append(d.get("filename", ""))

    for clients, fmt in _STRATEGIES:
        captured.clear()
        opts = _build_opts(out_dir, fmt, clients)
        opts["progress_hooks"] = [_hook]
        tag = f"{clients[0]}/{fmt[:12]}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if not info:
                    last_err = "Sem resultado"
                    continue
                entry = info["entries"][0] if info.get("entries") else info
                raw = captured[0] if captured else ydl.prepare_filename(entry)
                found = _locate_file(raw)
                if found:
                    log.info(f"✅ [{tag}] {Path(found).name}")
                    return entry, found
                last_err = "Arquivo não encontrado"
        except yt_dlp.utils.DownloadError as e:
            last_err = str(e).split("\n")[0][:180]
            log.warning(f"⚠ [{tag}] {last_err[:80]}")
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            log.warning(f"⚠ [{tag}] {last_err[:80]}")
    return None, last_err


def dl(target: str, out_dir: str, meta: dict | None) -> dict:
    """Download principal com fallbacks automáticos."""
    from ytmusic import yt_html_search

    try:
        c = Path.home() / ".cache" / "yt-dlp"
        if c.exists():
            shutil.rmtree(c, ignore_errors=True)
    except Exception:
        pass

    entry, result = _try_download(target, out_dir)

    if entry is None and target.startswith("https://"):
        t = (meta or {}).get("title", "")
        a = (meta or {}).get("artist", "")
        if t:
            entry, result = _try_download(f"ytsearch1:{t} {a} audio".strip(), out_dir)

    if entry is None:
        t = (meta or {}).get("title", "")
        a = (meta or {}).get("artist", "")
        if t:
            url = yt_html_search(f"{t} {a} official audio")
            if url:
                entry, result = _try_download(url, out_dir)

    if entry is None:
        return {"ok": False, "error": result}

    if meta:
        try:
            tag(result, meta)
        except Exception as e:
            log.warning(f"tag: {e}")

    return {
        "ok": True,
        "file": result,
        "title": (meta or {}).get("title", "") or entry.get("title", ""),
        "artist": (meta or {}).get("artist", "") or "",
        "dur": (meta or {}).get("dur", 0) or entry.get("duration", 0),
    }


async def dl_task(target: str, meta: dict | None) -> dict:
    """Download com semáforo para controle de concorrência."""
    assert DL_SEM is not None
    async with DL_SEM:
        work = work_dir()
        try:
            return await run_dl(dl, target, str(work), meta)
        except Exception as e:
            cleanup(work)
            return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════
# TAGGER — Metadados de áudio
# ══════════════════════════════════════════════
def _fetch_img(url: str) -> bytes | None:
    """Baixa imagem de capa."""
    try:
        r = rq.get(url, timeout=8, headers={"User-Agent": random_ua()})
        return r.content if r.ok else None
    except Exception:
        return None


def tag(path: str, m: dict):
    """Aplica tags de metadados ao arquivo de áudio."""
    ext = Path(path).suffix.lower()
    cover = _fetch_img(m["cover"]) if m.get("cover") else None
    if ext == ".mp3":
        _tag_mp3(path, m, cover)
    elif ext in (".m4a", ".aac"):
        _tag_m4a(path, m, cover)
    elif ext == ".opus":
        _tag_opus(path, m)


def _tag_mp3(path, m, cover):
    from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TDRC, APIC
    try:
        try:
            t = ID3(path)
        except ID3NoHeaderError:
            t = ID3()
        if m.get("title"):
            t["TIT2"] = TIT2(encoding=3, text=m["title"])
        if m.get("artist"):
            t["TPE1"] = TPE1(encoding=3, text=m["artist"])
        if m.get("album"):
            t["TALB"] = TALB(encoding=3, text=m["album"])
        if m.get("track"):
            t["TRCK"] = TRCK(encoding=3, text=str(m["track"]))
        if m.get("year"):
            t["TDRC"] = TDRC(encoding=3, text=m["year"])
        if cover:
            t["APIC"] = APIC(encoding=3, mime="image/jpeg",
                             type=3, desc="Cover", data=cover)
        t.save(path, v2_version=3)
    except Exception as e:
        log.warning(f"tag_mp3: {e}")


def _tag_m4a(path, m, cover):
    from mutagen.mp4 import MP4, MP4Cover
    try:
        t = MP4(path)
        if m.get("title"):
            t["\xa9nam"] = [m["title"]]
        if m.get("artist"):
            t["\xa9ART"] = [m["artist"]]
        if m.get("album"):
            t["\xa9alb"] = [m["album"]]
        if m.get("year"):
            t["\xa9day"] = [m["year"]]
        if m.get("track"):
            t["trkn"] = [(int(m["track"]), 0)]
        if cover:
            t["covr"] = [MP4Cover(cover, MP4Cover.FORMAT_JPEG)]
        t.save()
    except Exception as e:
        log.warning(f"tag_m4a: {e}")


def _tag_opus(path, m):
    from mutagen.oggopus import OggOpus
    try:
        t = OggOpus(path)
        for k, v in [("title", m.get("title")), ("artist", m.get("artist")),
                     ("album", m.get("album")), ("date", m.get("year")),
                     ("tracknumber", str(m.get("track", "")))]:
            if v:
                t[k] = [v]
        t.save()
    except Exception as e:
        log.warning(f"tag_opus: {e}")
