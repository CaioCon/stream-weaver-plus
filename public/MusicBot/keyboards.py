#!/usr/bin/env python3
# ══════════════════════════════════════════════
# ⌨️  TECLADOS INLINE — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from config import CFG, ALBUMS_PAGE, SONGS_PAGE
from helpers import thumb, cut, sec, ico
from session import cs


# ══════════════════════════════════════════════
# TECLADO DE CONFIGURAÇÕES
# ══════════════════════════════════════════════
def kb_settings() -> InlineKeyboardMarkup:
    lbl = "🟢 Buscas ATIVAS" if CFG["dm_on"] else "🔴 Buscas INATIVAS"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbl, callback_data="CFG:dm")],
        [InlineKeyboardButton("✖️ Fechar", callback_data="DEL")],
    ])


# ══════════════════════════════════════════════
# TECLADO DE RESULTADOS DE BUSCA
# ══════════════════════════════════════════════
def kb_search_results(results: dict) -> InlineKeyboardMarkup:
    rows = []
    for al in results.get("albums", [])[:4]:
        bid = al.get("browseId", "")
        if not bid:
            continue
        k = cs({"bid": bid, "cover": thumb(al.get("thumbnails", []))})
        year = al.get("year", "")
        rows.append([InlineKeyboardButton(
            f"{ico(al.get('type', 'Album'))} "
            f"{cut(al.get('title', '?'), 28)}"
            + (f" [{year}]" if year else ""),
            callback_data=f"SA:{k}",
        )])
    for sg in results.get("songs", [])[:4]:
        vid = sg.get("videoId", "")
        if not vid:
            continue
        title = sg.get("title", "?")
        artist = (sg.get("artists") or [{}])[0].get("name", "")
        k = cs({
            "video_id": vid, "title": title, "artist": artist,
            "album": (sg.get("album") or {}).get("name", ""),
            "cover": thumb(sg.get("thumbnails", [])),
            "dur": sg.get("duration_seconds", 0),
            "track": "", "year": "",
        })
        rows.append([InlineKeyboardButton(
            f"🎵 {cut(title, 26)} — {cut(artist, 16)}",
            callback_data=f"SD:{k}",
        )])
    rows.append([InlineKeyboardButton("✖️ Fechar", callback_data="DEL")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════
# TECLADO DO CARD DE ARTISTA
# ══════════════════════════════════════════════
def kb_artist_card(artist_key: str, n_releases: int, n_songs: int) -> InlineKeyboardMarkup:
    rows = []
    if n_releases:
        rows.append([InlineKeyboardButton(
            f"💿 Discografia ({n_releases})",
            callback_data=f"AL:{artist_key}:0",
        )])
    if n_songs:
        rows.append([InlineKeyboardButton(
            f"🎵 Músicas ({n_songs})",
            callback_data=f"SG:{artist_key}:0",
        )])
    rows.append([InlineKeyboardButton("✖️ Fechar", callback_data="DEL")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════
# TECLADO DE ÁLBUNS (com paginação)
# ══════════════════════════════════════════════
def kb_albums(page_items: list, artist_key: str,
              page: int, total: int, n_songs: int) -> InlineKeyboardMarkup:
    total_pages = max(1, -(-total // ALBUMS_PAGE))
    rows = []
    for rel in page_items:
        bid = (rel.get("browseId") or rel.get("playlistId") or "").strip()
        if not bid:
            continue
        atype = rel.get("type", "Album")
        year = rel.get("year", "")
        k = cs({"album_id": bid, "cover": thumb(rel.get("thumbnails", [])),
                "artist_key": artist_key, "page": page})
        rows.append([InlineKeyboardButton(
            f"{ico(atype)} {cut(rel.get('title', '?'), 28)}"
            + (f" [{year}]" if year else ""),
            callback_data=f"TR:{k}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"AL:{artist_key}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="NOP"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"AL:{artist_key}:{page + 1}"))
    rows.append(nav)

    bottom = [InlineKeyboardButton("🔙 Artista", callback_data=f"AK:{artist_key}")]
    if n_songs:
        bottom.append(InlineKeyboardButton(f"🎵 Músicas ({n_songs})",
                                           callback_data=f"SG:{artist_key}:0"))
    bottom.append(InlineKeyboardButton("✖️", callback_data="DEL"))
    rows.append(bottom)
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════
# TECLADO DE MÚSICAS (com paginação)
# ══════════════════════════════════════════════
def kb_songs(page_items: list, artist_key: str, page: int,
             total: int, artist_name: str, picture: str,
             n_releases: int) -> InlineKeyboardMarkup:
    total_pages = max(1, -(-total // SONGS_PAGE))
    rows = []
    for sg in page_items:
        vid = sg.get("videoId", "")
        if not vid:
            continue
        title = sg.get("title", "?")
        dur = sg.get("duration") or sec(sg.get("duration_seconds", 0))
        k = cs({
            "video_id": vid, "title": title,
            "artist": artist_name, "album": "",
            "cover": thumb(sg.get("thumbnails", [])) or picture,
            "dur": sg.get("duration_seconds", 0),
            "track": "", "year": "",
        })
        rows.append([InlineKeyboardButton(
            f"🎵 {cut(title, 28)} [{dur}]",
            callback_data=f"DL:{k}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"SG:{artist_key}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="NOP"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"SG:{artist_key}:{page + 1}"))
    rows.append(nav)

    bottom = [InlineKeyboardButton("🔙 Artista", callback_data=f"AK:{artist_key}")]
    if n_releases:
        bottom.append(InlineKeyboardButton(f"💿 Álbuns ({n_releases})",
                                           callback_data=f"AL:{artist_key}:0"))
    bottom.append(InlineKeyboardButton("✖️", callback_data="DEL"))
    rows.append(bottom)
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════
# TECLADO DE FAIXAS DO ÁLBUM
# ══════════════════════════════════════════════
def kb_tracks(info: dict, album_key: str) -> InlineKeyboardMarkup:
    from session import cg

    data = cg(album_key) or {}
    artist_key = data.get("artist_key", "")
    page = data.get("page", 0)
    cover = data.get("cover", "")

    tracks = info.get("tracks") or []
    valid = [t for t in tracks if t.get("videoId") and t.get("isAvailable", True)]
    artist_name = (info.get("artists") or [{}])[0].get("name", "")
    album_title = info.get("title", "")
    year = info.get("year", "")

    rows = []

    # Botão de baixar álbum completo
    if valid:
        all_t = [
            {"video_id": t["videoId"], "title": t.get("title", ""),
             "artist": artist_name, "album": album_title,
             "track": t.get("trackNumber") or i + 1,
             "year": year, "cover": cover,
             "dur": t.get("duration_seconds", 0)}
            for i, t in enumerate(valid)
        ]
        ak = cs({"tracks": all_t, "label": f"💿 {album_title}"})
        rows.append([InlineKeyboardButton(
            f"⬇️ Baixar álbum completo ({len(valid)} faixas)",
            callback_data=f"DAL:{ak}",
        )])
        rows.append([InlineKeyboardButton("─" * 22, callback_data="NOP")])

    for i, t in enumerate(valid):
        pos = t.get("trackNumber") or i + 1
        dur = t.get("duration") or sec(t.get("duration_seconds", 0))
        k = cs({
            "video_id": t["videoId"], "title": t.get("title", ""),
            "artist": artist_name, "album": album_title,
            "track": pos, "year": year, "cover": cover,
            "dur": t.get("duration_seconds", 0),
        })
        rows.append([InlineKeyboardButton(
            f"🎵 {pos:02d}. {cut(t.get('title', ''), 26)} [{dur}]",
            callback_data=f"DL:{k}",
        )])

    nav = []
    if artist_key:
        nav.append(InlineKeyboardButton("🔙 Álbuns",
                                        callback_data=f"AL:{artist_key}:{page}"))
    nav.append(InlineKeyboardButton("✖️ Fechar", callback_data="DEL"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)
