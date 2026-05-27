"""
Local Music Player — Flask Backend

Responsabilidades:
  - Escanear diretório de músicas locais (mp3, flac, m4a, ogg, wav, opus, aac, wma, ape, m4b)
  - Ler metadados existentes com mutagen
  - Enriquecer metadados incompletos via API pública do Deezer
  - Injetar metadados corrigidos com ffmpeg
  - Servir stream de áudio e capas
  - Proxy Deezer para busca/catálogo (resolve CORS)
  - Servir index.html
"""

# ─── Auto-instalação de dependências ──────────────────────────────────────────
import sys, subprocess as _sp

def _ensure(*pkgs):
    """Instala pacotes ausentes automaticamente."""
    import importlib
    _pip_map = {
        "flask":       "Flask",
        "flask_cors":  "Flask-Cors",
        "dotenv":      "python-dotenv",
        "mutagen":     "mutagen",
        "requests":    "requests",
    }
    to_install = []
    for pkg in pkgs:
        try:
            importlib.import_module(pkg)
        except ImportError:
            pip_name = _pip_map.get(pkg, pkg)
            to_install.append(pip_name)
    if to_install:
        print(f"📦  Instalando dependências: {', '.join(to_install)} ...")
        _sp.check_call([sys.executable, "-m", "pip", "install", "--quiet", *to_install])
        print("✅  Dependências instaladas.")

_ensure("flask", "flask_cors", "dotenv", "mutagen", "requests")

import os, re, json, shutil, hashlib, subprocess, tempfile, threading, urllib.request
import socket
from pathlib import Path
from flask import Flask, Response, request, jsonify, send_file, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app  = Flask(__name__)
CORS(app)

# ─── Configuração ─────────────────────────────────────────────────────────────

# Lista de diretórios "candidatos" comuns em Android / Termux / Linux / Windows / macOS.
# São testados em runtime; somente os que existem são usados.
_CANDIDATE_DIRS = [
    # Android — raízes que normalmente contém Music/, Download/, WhatsApp/Media/Audio/, etc.
    "/sdcard", "/storage/emulated/0", "/storage/self/primary",
    "/storage/sdcard0", "/storage/sdcard1", "/storage/extSdCard",
    "/mnt/sdcard", "/mnt/extSdCard", "/mnt/media_rw",
    # Termux
    "/data/data/com.termux/files/home/storage/shared",
    "/data/data/com.termux/files/home/storage/music",
    "/data/data/com.termux/files/home/storage/downloads",
    # Linux/macOS padrão
    str(Path.home() / "Music"),
    str(Path.home() / "Downloads"),
    str(Path.home() / "Documents"),
    "/media", "/mnt",
    # Windows
    "C:/Users/Public/Music",
]

def _discover_music_roots() -> list[Path]:
    """Descobre diretórios reais no dispositivo. Honra MUSIC_DIR/MUSIC_DIRS env."""
    env_dirs = os.environ.get("MUSIC_DIRS", "") or os.environ.get("MUSIC_DIR", "")
    roots: list[Path] = []
    if env_dirs.strip():
        for raw in re.split(r"[;:,]+", env_dirs):
            raw = raw.strip()
            if not raw:
                continue
            p = Path(raw).expanduser()
            if p.exists() and p.is_dir():
                roots.append(p)
    if not roots:
        for c in _CANDIDATE_DIRS:
            try:
                p = Path(c).expanduser()
                if p.exists() and p.is_dir():
                    roots.append(p)
            except Exception:
                continue
    # Fallback final
    if not roots:
        roots.append(Path.home())
    # Dedup preservando ordem
    seen, uniq = set(), []
    for p in roots:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq

MUSIC_ROOTS: list[Path] = _discover_music_roots()
MUSIC_DIR: Path = MUSIC_ROOTS[0]  # mantém compatibilidade com referências antigas

# Diretórios ignorados durante a varredura recursiva (ruído / cache / sistema)
_SKIP_DIR_NAMES = {
    ".thumbnails", ".trash", ".Trash", ".Trashes", "$RECYCLE.BIN",
    "Android", "cache", "Cache", ".cache", "node_modules",
    ".git", ".svn", "tmp", "temp", "__pycache__",
}

CACHE_DIR  = Path(tempfile.gettempdir()) / "lmp_cache"
COVER_DIR  = CACHE_DIR / "covers"
CACHE_DIR.mkdir(exist_ok=True)
COVER_DIR.mkdir(exist_ok=True)

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".opus",
              ".aac", ".wma", ".ape", ".m4b", ".alac", ".webm"}

DZ_API = "https://api.deezer.com"

import requests as _req
_session = _req.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})


def _iter_audio_files(roots: list[Path]):
    """Walk recursivo pulando diretórios irrelevantes; lida com PermissionError."""
    for root in roots:
        try:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                # filtra in-place para não descer em pastas ignoradas / ocultas
                dirnames[:] = [d for d in dirnames
                               if d not in _SKIP_DIR_NAMES and not d.startswith(".")]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in AUDIO_EXTS:
                        yield Path(dirpath) / fn
        except PermissionError:
            continue
        except Exception as ex:
            app.logger.warning(f"walk falhou em {root}: {ex}")
            continue

# Cache em memória das faixas escaneadas  {track_id: dict}
_library: dict = {}
_library_lock  = threading.Lock()
_scan_status   = {"running": False, "total": 0, "done": 0, "error": None, "current": ""}


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _track_id(path: Path) -> str:
    """ID estável baseado no caminho absoluto."""
    return hashlib.md5(str(path).encode()).hexdigest()


def _dz_get(path: str, **params):
    url = f"{DZ_API}/{path.lstrip('/')}"
    r   = _session.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "error" in data:
        raise ValueError(data["error"].get("message", "Deezer API error"))
    return data



def _clean_text(value: str) -> str:
    """Normaliza texto de arquivos/metadata para melhorar comparação no Deezer."""
    value = str(value or "")
    value = re.sub(r"\.[a-zA-Z0-9]{2,5}$", "", value)
    value = re.sub(r"[_\.]+", " ", value)
    value = re.sub(r"\s*\[[^\]]+\]|\s*\([^)]*(official|lyrics?|audio|video|remaster|explicit|sped up|slowed|nightcore|128|192|256|320|kbps)[^)]*\)", " ", value, flags=re.I)
    value = re.sub(r"\b(www\.|https?://|mp3|flac|m4a|audio|official|video|lyrics?)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -_.,")
    return value.strip()


def _norm(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _token_score(query: str, candidate: str) -> float:
    q = set(_norm(query).split())
    c = set(_norm(candidate).split())
    if not q or not c:
        return 0.0
    return len(q & c) / max(len(q), len(c))


def _guess_from_path(path: Path) -> dict:
    """Extrai artista/título/álbum prováveis do nome do arquivo e pastas."""
    title = _clean_text(path.stem)
    artist = ""
    album = ""
    parent = _clean_text(path.parent.name)
    grand = _clean_text(path.parent.parent.name) if path.parent.parent != path.parent else ""
    for pat in (
        r"^\s*(?P<num>\d{1,3})\s*[-_. ]+\s*(?P<artist>.+?)\s+-\s+(?P<title>.+)$",
        r"^\s*(?P<artist>.+?)\s+-\s+(?P<title>.+)$",
        r"^\s*(?P<num>\d{1,3})\s*[-_. ]+\s*(?P<title>.+)$",
    ):
        m = re.match(pat, title)
        if m:
            gd = m.groupdict()
            title = _clean_text(gd.get("title") or title)
            artist = _clean_text(gd.get("artist") or artist)
            break
    ignored = {"music", "musicas", "músicas", "download", "downloads", "audio", "audios"}
    if not album and parent and parent.lower() not in ignored:
        album = parent
    if not artist and grand and grand.lower() not in ignored:
        artist = grand
    return {"title": title, "artist": artist, "album": album}


def _deezer_track_to_meta(item: dict, album_detail: dict | None = None) -> dict:
    alb_info = item.get("album") or {}
    art_info = item.get("artist") or {}
    release = (album_detail or {}).get("release_date") or item.get("release_date") or ""
    track_no = item.get("track_position") or item.get("track_number") or 0
    return {
        "title": item.get("title") or item.get("title_short") or "",
        "artist": art_info.get("name") or "",
        "album": (album_detail or {}).get("title") or alb_info.get("title") or "",
        "album_artist": ((album_detail or {}).get("artist") or {}).get("name") or art_info.get("name") or "",
        "cover_url": (alb_info.get("cover_xl") or alb_info.get("cover_big") or alb_info.get("cover_medium") or (album_detail or {}).get("cover_xl") or (album_detail or {}).get("cover_big") or ""),
        "year": str(release)[:4] if release else "",
        "release_date": release,
        "deezer_id": str(item.get("id", "")),
        "album_id": str(alb_info.get("id") or (album_detail or {}).get("id") or ""),
        "track_number": int(track_no) if str(track_no).isdigit() else 0,
        "duration": int(item.get("duration") or 0),
    }


def _read_metadata(path: Path) -> dict:
    """Lê metadados do arquivo com mutagen. Retorna dict com campos normalizados."""
    meta = {
        "title": "", "artist": "", "album": "",
        "track_number": 0, "duration": 0,
        "cover_embedded": False, "year": "",
    }
    try:
        from mutagen import File as MuFile

        mf = MuFile(str(path), easy=False)
        if mf is None:
            return meta

        meta["duration"] = int(getattr(mf.info, "length", 0))

        ef = MuFile(str(path), easy=True)
        if ef:
            def _tag(key):
                v = ef.get(key)
                return str(v[0]).strip() if v else ""
            meta["title"]        = _tag("title")
            meta["artist"]       = _tag("artist") or _tag("albumartist")
            meta["album"]        = _tag("album")
            meta["year"]         = _tag("date")[:4] if _tag("date") else ""
            tn = _tag("tracknumber")
            if tn:
                m = re.search(r"\d+", tn)
                meta["track_number"] = int(m.group(0)) if m else 0

        # Verifica capa embedded por formato
        ext = path.suffix.lower()
        if ext == ".mp3":
            try:
                from mutagen.id3 import ID3
                tags = ID3(str(path))
                meta["cover_embedded"] = any(k.startswith("APIC") for k in tags.keys())
            except Exception:
                pass
        elif ext == ".flac":
            meta["cover_embedded"] = bool(mf.pictures)
        elif ext in (".m4a", ".m4b", ".alac"):
            covr = mf.tags.get("covr") if mf.tags else None
            meta["cover_embedded"] = bool(covr)
        elif ext in (".ogg", ".opus"):
            meta["cover_embedded"] = "metadata_block_picture" in (mf.tags or {})

    except Exception as ex:
        app.logger.debug(f"mutagen erro em {path.name}: {ex}")

    return meta


def _is_incomplete(meta: dict) -> bool:
    """Retorna True se faltar título, artista, álbum ou capa."""
    return not (meta.get("title") and meta.get("artist") and meta.get("album") and meta.get("cover_embedded"))


def _search_deezer(title: str, artist: str, album: str, path: Path | None = None):
    """Busca e pontua a melhor faixa na Deezer comparando música, artista e álbum."""
    guessed = _guess_from_path(path) if path else {}
    title = _clean_text(title) or guessed.get("title", "")
    artist = _clean_text(artist) or guessed.get("artist", "")
    album = _clean_text(album) or guessed.get("album", "")

    queries = []
    if artist and title:
        queries += [f'artist:"{artist}" track:"{title}"', f"{artist} {title}"]
    if album and title:
        queries += [f'album:"{album}" track:"{title}"', f"{album} {title}"]
    if title:
        queries.append(title)
    if path:
        g = _guess_from_path(path)
        combo = " ".join([g.get("artist", ""), g.get("title", "")]).strip()
        if combo:
            queries.append(combo)

    seen, best_item, best_score, best_album_detail = [], None, -1.0, None
    for query in queries:
        query = query.strip()
        if not query or query in seen:
            continue
        seen.append(query)
        try:
            items = (_dz_get("search", q=query, limit=15).get("data") or [])
        except Exception as ex:
            app.logger.debug(f"Deezer busca falhou para '{query}': {ex}")
            continue
        for item in items:
            alb_info = item.get("album") or {}
            art_info = item.get("artist") or {}
            c_title = item.get("title") or item.get("title_short") or ""
            c_artist = art_info.get("name") or ""
            c_album = alb_info.get("title") or ""
            score = _token_score(title, c_title) * 5
            score += _token_score(artist, c_artist) * 3 if artist else 0.6
            score += _token_score(album, c_album) * 2 if album else 0.2
            if title and _norm(title) in _norm(c_title): score += 1
            if artist and _norm(artist) in _norm(c_artist): score += 1
            if album and _norm(album) in _norm(c_album): score += 1
            if score > best_score:
                best_item, best_score = item, score

    if not best_item:
        return None
    album_id = (best_item.get("album") or {}).get("id")
    if album_id:
        try:
            best_album_detail = _dz_get(f"album/{album_id}")
        except Exception:
            best_album_detail = None
    return _deezer_track_to_meta(best_item, best_album_detail)


def _search_deezer_album(album: str, artist: str = ""):
    query = " ".join(filter(None, [_clean_text(artist), _clean_text(album)])).strip()
    if not query:
        return None
    try:
        data = _dz_get("search/album", q=query, limit=10)
        items = data.get("data") or []
        if not items:
            return None
        best = max(items, key=lambda a: _token_score(album, a.get("title", "")) * 3 + _token_score(artist, (a.get("artist") or {}).get("name", "")) * 2)
        detail = _dz_get(f"album/{best['id']}")
        detail["tracks_data"] = detail.get("tracks", {}).get("data", [])
        return detail
    except Exception as ex:
        app.logger.debug(f"Deezer álbum falhou para '{query}': {ex}")
        return None


def _match_album_track(album_detail: dict, track: dict) -> dict | None:
    tracks = album_detail.get("tracks_data") or album_detail.get("tracks", {}).get("data", []) or []
    if not tracks:
        return None
    title = track.get("title", "") or track.get("filename", "")
    tn = int(track.get("track_number") or 0)
    score, item = max(((
        _token_score(title, it.get("title", "")) * 5 + (3 if tn and int(it.get("track_position") or 0) == tn else 0), it
    ) for it in tracks), key=lambda x: x[0])
    if score < 1.2:
        return None
    return _deezer_track_to_meta(item, album_detail)


def _download_cover(url: str, cover_path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            cover_path.write_bytes(r.read())
        return True
    except Exception:
        return False


def _inject_metadata_ffmpeg(src: Path, title: str, artist: str,
                             album: str, year: str, cover_path=None,
                             track_number: int = 0, album_artist: str = "") -> bool:
    """Injeta metadados e capa via ffmpeg, substituindo o arquivo original sem recodificar áudio."""
    if not shutil.which("ffmpeg"):
        app.logger.warning("ffmpeg não encontrado no PATH")
        return False
    tmp = src.with_name(src.stem + ".lmp_tmp" + src.suffix)
    try:
        has_cover = bool(cover_path and Path(cover_path).exists())
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
        if has_cover:
            cmd += ["-i", str(cover_path)]
        cmd += ["-map", "0:a:0"]
        if has_cover:
            cmd += ["-map", "1:v:0", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
        cmd += ["-c:a", "copy", "-map_metadata", "-1",
                "-metadata", f"title={title}",
                "-metadata", f"artist={artist}",
                "-metadata", f"album={album}"]
        if album_artist:
            cmd += ["-metadata", f"album_artist={album_artist}"]
        if year:
            cmd += ["-metadata", f"date={year}"]
        if track_number:
            cmd += ["-metadata", f"track={track_number}"]
        if src.suffix.lower() == ".mp3":
            cmd += ["-id3v2_version", "3", "-write_id3v1", "1"]
        cmd += [str(tmp)]
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        if result.returncode != 0:
            app.logger.warning(f"ffmpeg erro: {result.stderr.decode(errors='ignore')[:500]}")
            tmp.unlink(missing_ok=True)
            return False
        if tmp.exists() and tmp.stat().st_size > 0:
            shutil.move(str(tmp), str(src))
            return True
        return False
    except Exception as ex:
        app.logger.warning(f"ffmpeg inject falhou {src.name}: {ex}")
        tmp.unlink(missing_ok=True)
        return False


def _extract_cover_to_cache(path: Path, cover_path: Path) -> bool:
    """Extrai capa embedded via ffmpeg."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-an", "-vcodec", "copy", str(cover_path)],
            capture_output=True, timeout=15
        )
        return result.returncode == 0 and cover_path.exists() and cover_path.stat().st_size > 0
    except Exception:
        return False


def _build_track(path: Path, enrich: bool = True) -> dict:
    """Lê, reconhece via Deezer e corrige metadados/capa do arquivo via ffmpeg."""
    tid = _track_id(path)
    meta = _read_metadata(path)
    guessed = _guess_from_path(path)
    meta["title"] = _clean_text(meta["title"] or guessed.get("title") or path.stem)
    meta["artist"] = _clean_text(meta["artist"] or guessed.get("artist", ""))
    meta["album"] = _clean_text(meta["album"] or guessed.get("album", ""))

    deezer_info = None
    if enrich:
        deezer_info = _search_deezer(meta["title"], meta["artist"], meta["album"], path=path)
        if deezer_info:
            new_title = deezer_info.get("title") or meta["title"]
            new_artist = deezer_info.get("artist") or meta["artist"]
            new_album = deezer_info.get("album") or meta["album"]
            new_year = deezer_info.get("year") or meta["year"]
            new_track_number = int(deezer_info.get("track_number") or meta["track_number"] or 0)
            album_artist = deezer_info.get("album_artist") or new_artist
            cover_path = None
            if deezer_info.get("cover_url"):
                cover_path = COVER_DIR / f"{tid}.jpg"
                if not cover_path.exists() or cover_path.stat().st_size == 0:
                    if not _download_cover(deezer_info["cover_url"], cover_path):
                        cover_path = None
            changed = any([
                new_title and new_title != meta["title"],
                new_artist and new_artist != meta["artist"],
                new_album and new_album != meta["album"],
                new_year and new_year != meta["year"],
                new_track_number and new_track_number != meta["track_number"],
                cover_path and not meta["cover_embedded"],
            ])
            if changed:
                ok = _inject_metadata_ffmpeg(path, new_title, new_artist, new_album, new_year, cover_path, new_track_number, album_artist)
                if ok:
                    meta.update({"title": new_title, "artist": new_artist, "album": new_album, "year": new_year, "track_number": new_track_number, "cover_embedded": bool(cover_path) or meta["cover_embedded"]})
                    app.logger.info(f"Metadados enriquecidos via Deezer: {path.name}")

    cover_cache = COVER_DIR / f"{tid}.jpg"
    if not cover_cache.exists() or cover_cache.stat().st_size == 0:
        if meta["cover_embedded"]:
            _extract_cover_to_cache(path, cover_cache)
        elif deezer_info and deezer_info.get("cover_url"):
            _download_cover(deezer_info["cover_url"], cover_cache)

    return {
        "id": tid,
        "path": str(path),
        "filename": path.name,
        "ext": path.suffix.lower().lstrip("."),
        "title": meta["title"] or path.stem,
        "artist": meta["artist"] or "Desconhecido",
        "album": meta["album"] or "Desconhecido",
        "year": meta["year"],
        "track_number": int(meta["track_number"] or 0),
        "duration": int(meta["duration"] or 0),
        "has_cover": cover_cache.exists() and cover_cache.stat().st_size > 0,
        "size": path.stat().st_size,
        "deezer_id": deezer_info.get("deezer_id") if deezer_info else "",
        "album_id": deezer_info.get("album_id") if deezer_info else "",
    }


def _scan_library(music_dir: Path, enrich: bool = True):
    global _scan_status
    with _library_lock:
        _library.clear()
    _scan_status.update({"running": True, "done": 0, "error": None, "current": ""})

    try:
        files = [p for p in music_dir.rglob("*")
                 if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
        _scan_status["total"] = len(files)

        for f in files:
            try:
                _scan_status["current"] = f.name
                track = _build_track(f, enrich=enrich)
                with _library_lock:
                    _library[track["id"]] = track
            except Exception as ex:
                app.logger.warning(f"Erro ao processar {f.name}: {ex}")
            finally:
                _scan_status["done"] += 1

    except Exception as ex:
        _scan_status["error"] = str(ex)
        app.logger.error(f"Erro no scan: {ex}")
    finally:
        _scan_status["running"] = False
        _scan_status["current"] = ""


# ─── Rotas ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Inicia scan assíncrono. Body JSON opcional: {"dir": "/path", "enrich": true}"""
    body    = request.get_json(silent=True) or {}
    dir_arg = body.get("dir", "").strip()
    enrich  = bool(body.get("enrich", True))
    target  = Path(dir_arg) if dir_arg else MUSIC_DIR

    if not target.exists() or not target.is_dir():
        return jsonify({"error": f"Diretório não encontrado: {target}"}), 400
    if _scan_status["running"]:
        return jsonify({"error": "Scan já em andamento"}), 409

    threading.Thread(target=_scan_library, args=(target, enrich), daemon=True).start()
    return jsonify({"message": "Scan iniciado", "dir": str(target), "enrich": enrich})


@app.route("/api/scan/status")
def api_scan_status():
    return jsonify({**_scan_status, "library_size": len(_library)})


@app.route("/api/tracks")
def api_tracks():
    q = request.args.get("q", "").strip().lower()
    with _library_lock:
        tracks = list(_library.values())
    if q:
        tracks = [t for t in tracks if
                  q in t["title"].lower() or
                  q in t["artist"].lower() or
                  q in t["album"].lower()]
    tracks.sort(key=lambda t: (t["artist"].lower(), t["album"].lower(),
                                t["track_number"], t["title"].lower()))
    return jsonify(tracks)


@app.route("/api/track/<tid>")
def api_track(tid: str):
    with _library_lock:
        track = _library.get(tid)
    if not track:
        return jsonify({"error": "Faixa não encontrada"}), 404
    return jsonify(track)


@app.route("/api/albums")
def api_albums():
    with _library_lock:
        tracks = list(_library.values())
    albums = {}
    for t in tracks:
        key = f"{t['artist']}||{t['album']}"
        if key not in albums:
            albums[key] = {
                "album":    t["album"]  or "Desconhecido",
                "artist":   t["artist"] or "Desconhecido",
                "year":     t["year"],
                "cover_id": t["id"] if t["has_cover"] else None,
                "tracks":   [],
                "duration": 0,
            }
        albums[key]["tracks"].append(t)
        albums[key]["duration"] += int(t.get("duration") or 0)
        if not albums[key]["cover_id"] and t.get("has_cover"):
            albums[key]["cover_id"] = t["id"]
    result = sorted(albums.values(),
                    key=lambda a: (a["artist"].lower(), a["album"].lower()))
    return jsonify(result)


@app.route("/api/artists")
def api_artists():
    with _library_lock:
        tracks = list(_library.values())
    artists = {}
    for t in tracks:
        name = t["artist"] or "Desconhecido"
        if name not in artists:
            artists[name] = {"name": name, "track_count": 0, "albums": set()}
        artists[name]["track_count"] += 1
        if t["album"]:
            artists[name]["albums"].add(t["album"])
    result = [{"name": a["name"], "track_count": a["track_count"],
               "album_count": len(a["albums"])}
              for a in artists.values()]
    result.sort(key=lambda a: a["name"].lower())
    return jsonify(result)


@app.route("/api/playlists")
def api_playlists():
    with _library_lock:
        tracks = list(_library.values())
    playlists = []
    by_artist, by_album, by_year = {}, {}, {}
    for t in tracks:
        art = t["artist"] or "Desconhecido"
        alb = t["album"] or "Desconhecido"
        year = t.get("year") or "Sem ano"
        by_artist.setdefault(art, []).append(t)
        by_album.setdefault(f"{art} — {alb}", []).append(t)
        by_year.setdefault(year, []).append(t)

    def pack(kind, name, tks):
        tks = sorted(tks, key=lambda x: (x.get("track_number") or 9999, x.get("title", "").lower()))
        return {"type": kind, "name": name, "track_count": len(tks), "duration": sum(int(t.get("duration") or 0) for t in tks), "cover_id": next((t["id"] for t in tks if t.get("has_cover")), None), "tracks": tks}

    playlists.append(pack("all", "Todas as músicas", tracks))
    for name, tks in sorted(by_album.items()): playlists.append(pack("album", name, tks))
    for name, tks in sorted(by_artist.items()): playlists.append(pack("artist", name, tks))
    for name, tks in sorted(by_year.items()):
        if name != "Sem ano" and len(tks) >= 3: playlists.append(pack("year", name, tks))
    return jsonify(playlists)


@app.route("/api/deezer/search")
def api_deezer_search():
    q = request.args.get("q", "").strip()
    kind = request.args.get("type", "track").strip().lower()
    if not q: return jsonify({"error": "Informe q"}), 400
    endpoint = "search" if kind not in ("album", "playlist", "artist") else f"search/{kind}"
    try:
        return jsonify(_dz_get(endpoint, q=q, limit=int(request.args.get("limit", 12))))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/deezer/album/compare", methods=["POST"])
def api_deezer_album_compare():
    body = request.get_json(silent=True) or {}
    album = _clean_text(body.get("album", ""))
    artist = _clean_text(body.get("artist", ""))
    local_tracks = body.get("tracks") or []
    detail = _search_deezer_album(album, artist)
    if not detail: return jsonify({"error": "Álbum não encontrado no Deezer"}), 404
    return jsonify({"album": detail, "matches": [{"local": t, "deezer": _match_album_track(detail, t)} for t in local_tracks]})


@app.route("/api/enrich/album", methods=["POST"])
def api_enrich_album():
    body = request.get_json(silent=True) or {}
    album = _clean_text(body.get("album", ""))
    artist = _clean_text(body.get("artist", ""))
    ids = set(body.get("ids") or [])
    with _library_lock:
        tracks = [t for t in _library.values() if (not ids or t["id"] in ids) and (not album or _norm(t.get("album")) == _norm(album)) and (not artist or _norm(t.get("artist")) == _norm(artist))]
    if not tracks: return jsonify({"error": "Nenhuma faixa local encontrada para esse álbum"}), 404
    detail = _search_deezer_album(album or tracks[0]["album"], artist or tracks[0]["artist"])
    if not detail: return jsonify({"error": "Álbum não encontrado no Deezer"}), 404
    updated = []
    for t in tracks:
        meta = _match_album_track(detail, t)
        if not meta: continue
        cover_path = None
        if meta.get("cover_url"):
            cover_path = COVER_DIR / f"{t['id']}.jpg"
            _download_cover(meta["cover_url"], cover_path)
        ok = _inject_metadata_ffmpeg(Path(t["path"]), meta["title"], meta["artist"], meta["album"], meta["year"], cover_path, meta.get("track_number") or 0, meta.get("album_artist") or meta.get("artist") or "")
        if ok:
            rebuilt = _build_track(Path(t["path"]), enrich=False)
            with _library_lock:
                _library[t["id"]] = rebuilt
            updated.append(rebuilt)
    return jsonify({"message": f"{len(updated)} faixa(s) atualizada(s)", "tracks": updated})


@app.route("/api/stream/<tid>")
def api_stream(tid: str):
    """Stream de áudio com suporte a Range (seek)."""
    with _library_lock:
        track = _library.get(tid)
    if not track:
        return jsonify({"error": "Faixa não encontrada"}), 404

    path = Path(track["path"])
    if not path.exists():
        return jsonify({"error": "Arquivo não encontrado no disco"}), 404

    ext_mime = {
        "mp3": "audio/mpeg", "flac": "audio/flac", "m4a": "audio/mp4",
        "m4b": "audio/mp4",  "ogg": "audio/ogg",   "opus": "audio/ogg",
        "wav": "audio/wav",  "aac": "audio/aac",    "wma": "audio/x-ms-wma",
        "ape": "audio/ape",  "alac": "audio/mp4",   "webm": "audio/webm",
    }
    mime      = ext_mime.get(track["ext"], "audio/mpeg")
    filesize  = path.stat().st_size
    range_hdr = request.headers.get("Range")

    if range_hdr:
        m = re.match(r"bytes=(\d+)-(\d*)", range_hdr)
        if not m:
            return Response(status=416)
        start  = int(m.group(1))
        end    = int(m.group(2)) if m.group(2) else filesize - 1
        end    = min(end, filesize - 1)
        length = end - start + 1

        def gen_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return Response(stream_with_context(gen_range()), status=206, headers={
            "Content-Type":   mime,
            "Accept-Ranges":  "bytes",
            "Content-Range":  f"bytes {start}-{end}/{filesize}",
            "Content-Length": str(length),
        })

    return send_file(str(path), mimetype=mime, conditional=True)


@app.route("/api/cover/<tid>")
def api_cover(tid: str):
    cover = COVER_DIR / f"{tid}.jpg"
    if cover.exists():
        return send_file(str(cover), mimetype="image/jpeg")
    with _library_lock:
        track = _library.get(tid)
    if track and track.get("cover_embedded"):
        if _extract_cover_to_cache(Path(track["path"]), cover):
            return send_file(str(cover), mimetype="image/jpeg")
    return jsonify({"error": "Capa não disponível"}), 404


@app.route("/dz/<path:dz_path>")
def dz_proxy(dz_path: str):
    allowed = ("chart", "search", "artist", "album", "playlist", "track", "genre", "editorial")
    if dz_path.split("/")[0].lower() not in allowed:
        return jsonify({"error": "Rota não permitida"}), 403
    params = dict(request.args)
    params.setdefault("output", "json")
    try:
        return jsonify(_dz_get(dz_path, **params))
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/enrich/<tid>", methods=["POST"])
def api_enrich(tid: str):
    """Força enriquecimento de metadados de uma faixa via Deezer + ffmpeg."""
    with _library_lock:
        track = _library.get(tid)
    if not track:
        return jsonify({"error": "Faixa não encontrada"}), 404
    try:
        updated = _build_track(Path(track["path"]), enrich=True)
        with _library_lock:
            _library[tid] = updated
        return jsonify({"message": "Enriquecido com sucesso", "track": updated})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/status")
def api_status():
    return jsonify({
        "music_dir":     str(MUSIC_DIR),
        "library_size":  len(_library),
        "scan":          _scan_status,
        "audio_formats": sorted(AUDIO_EXTS),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "deezer": True,
    })


# ══════════════════════════════════════════════════════════════════════════════
# 🔧  EXTENSÕES (preservando 100% do código original acima)
#     - Edição manual de tags por faixa
#     - Detalhe de álbum/playlist (lista de faixas + edição individual)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/track/<tid>/tags", methods=["POST"])
def api_track_set_tags(tid: str):
    """Atualiza tags manualmente (sem Deezer) via ffmpeg, preservando áudio."""
    body = request.get_json(silent=True) or {}
    with _library_lock:
        track = _library.get(tid)
    if not track:
        return jsonify({"error": "Faixa não encontrada"}), 404
    path = Path(track["path"])
    if not path.exists():
        return jsonify({"error": "Arquivo não existe"}), 404

    title        = str(body.get("title",        track["title"])).strip() or track["title"]
    artist       = str(body.get("artist",       track["artist"])).strip() or track["artist"]
    album        = str(body.get("album",        track["album"])).strip() or track["album"]
    year         = str(body.get("year",         track.get("year", ""))).strip()
    album_artist = str(body.get("album_artist", artist)).strip() or artist
    try:
        track_number = int(body.get("track_number") or track.get("track_number") or 0)
    except (TypeError, ValueError):
        track_number = 0

    cover_url = str(body.get("cover_url", "")).strip()
    cover_path = None
    if cover_url:
        cp = COVER_DIR / f"{tid}.jpg"
        if _download_cover(cover_url, cp):
            cover_path = cp
    elif (COVER_DIR / f"{tid}.jpg").exists():
        cover_path = COVER_DIR / f"{tid}.jpg"

    ok = _inject_metadata_ffmpeg(
        path, title, artist, album, year,
        cover_path, track_number, album_artist
    )
    if not ok:
        return jsonify({"error": "Falha ao gravar tags (ffmpeg)"}), 500

    rebuilt = _build_track(path, enrich=False)
    with _library_lock:
        _library[tid] = rebuilt
    return jsonify({"message": "Tags atualizadas", "track": rebuilt})


# ─────────────────────────────────────────────────────────────────────────────
def _find_free_port(start: int = 5000, end: int = 5099) -> int:
    """Retorna o primeiro port livre no intervalo [start, end]."""
    for p in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    raise RuntimeError(f"Nenhuma porta livre encontrada entre {start} e {end}.")


if __name__ == "__main__":
    _preferred = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Tenta a porta preferida; se ocupada, acha uma livre automaticamente
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
        _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            _s.bind(("0.0.0.0", _preferred))
            port = _preferred
        except OSError:
            port = _find_free_port(_preferred + 1)
            print(f"⚠️   Porta {_preferred} em uso — usando porta {port} automaticamente.")

    print(f"🎵  Local Music Player → http://0.0.0.0:{port}")
    print(f"📁  Diretório de músicas: {MUSIC_DIR}")
    print(f"🎧  Formatos suportados: {', '.join(sorted(AUDIO_EXTS))}")
    print(f"🔍  Metadados: mutagen + Deezer API + ffmpeg")
    print(f"ℹ️   POST /api/scan para iniciar scan da biblioteca")

    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
