#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 📡  HANDLERS — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode, ChatAction
from telegram.error import BadRequest

from config import (
    OWNER_ID, CFG, AUDIO_QUALITY, MAX_BATCH, MAX_DL_SLOTS,
    HAS_FFMPEG, HAS_ARIA2C, DB_PATH, CACHE_DIR, ALBUMS_PAGE, SONGS_PAGE,
)
from helpers import cut, ico, sec, thumb, is_owner, dm_ok
from session import cs, cg, session_set
from database import (
    db_upsert_user, db_set_topic, db_get_topic, db_del_topic,
    db_log_download, db_stats,
)
from downloader import run_search, dl_task, SEARCH_POOL, DL_POOL, _STRATEGIES
from renderer import render, send_audio, batch_download
from keyboards import (
    kb_settings, kb_search_results, kb_artist_card,
    kb_albums, kb_songs, kb_tracks,
)
from ytmusic import fetch_artist_full, search, get_album

log = logging.getLogger("musicbot")


# ══════════════════════════════════════════════
# FILTRO DE TÓPICO
# ══════════════════════════════════════════════
async def _topic_allowed(update: Update) -> bool:
    """Retorna True se o update deve ser processado."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return True
    msg = update.effective_message
    thread_id = msg.message_thread_id if msg else None
    configured = await run_search(db_get_topic, chat.id)
    if configured is None:
        return True
    return thread_id == configured


def _thread_id(update: Update) -> int | None:
    """Retorna o message_thread_id do update atual."""
    msg = update.effective_message
    return msg.message_thread_id if msg else None


# ══════════════════════════════════════════════
# LOAD ARTISTA (lazy)
# ══════════════════════════════════════════════
async def _load_artist(artist_key: str) -> dict | None:
    data = cg(artist_key)
    if not data:
        return None
    if data.get("_loaded"):
        return data
    try:
        full = await run_search(fetch_artist_full, data["artist_id"])
        data.update({
            "_loaded": True,
            "_releases": full["releases"],
            "_songs": full["songs"],
            "_info": full["info"],
            "picture": data.get("picture") or full["picture"],
            "artist_name": data.get("artist_name") or full["name"],
        })
        session_set(artist_key, data)
        return data
    except Exception as e:
        log.error(f"_load_artist: {e}")
        return None


# ══════════════════════════════════════════════
# SHOW FUNCTIONS
# ══════════════════════════════════════════════
async def _show_artist_card(target, artist_key: str,
                            edit: bool = False, thread_id: int | None = None):
    data = await _load_artist(artist_key)
    if not data:
        if hasattr(target, "reply_text"):
            await target.reply_text("❌ Sessão expirada. Busque novamente.")
        return
    releases = data.get("_releases", [])
    songs = data.get("_songs", [])
    info = data.get("_info", {})
    picture = data.get("picture", "")
    name = data.get("artist_name", "?")
    desc = (info.get("description") or "")[:220]
    views = info.get("views", "")
    n_albums = sum(1 for r in releases if r.get("type", "").lower() == "album")
    n_singles = sum(1 for r in releases if r.get("type", "").lower() == "single")
    n_eps = sum(1 for r in releases if r.get("type", "").lower() == "ep")
    lines = [f"🎤 **{name}**"]
    if views:
        lines.append(f"👁 {views}")
    parts = []
    if n_albums:
        parts.append(f"💿 {n_albums} álbum(ns)")
    if n_eps:
        parts.append(f"📀 {n_eps} EP(s)")
    if n_singles:
        parts.append(f"🎵 {n_singles} single(s)")
    if parts:
        lines.append(" · ".join(parts))
    if desc:
        lines.append(f"\n _{desc}…_")
    lines.append("\n\nEscolha uma seção:")
    kb = kb_artist_card(artist_key, len(releases), len(songs))
    await render(target, picture, "\n".join(lines), kb, edit=edit, thread_id=thread_id)


async def _show_albums(target, artist_key: str, page: int,
                       edit: bool = True, thread_id: int | None = None):
    data = await _load_artist(artist_key)
    if not data:
        if hasattr(target, "reply_text"):
            await target.reply_text("❌ Sessão expirada.")
        return
    releases = data.get("_releases", [])
    songs = data.get("_songs", [])
    total = len(releases)
    page_items = releases[page * ALBUMS_PAGE:(page + 1) * ALBUMS_PAGE]
    total_pages = max(1, -(-total // ALBUMS_PAGE))
    picture = data.get("picture", "")
    name = data.get("artist_name", "?")
    n_albums = sum(1 for r in releases if r.get("type", "").lower() == "album")
    n_singles = sum(1 for r in releases if r.get("type", "").lower() == "single")
    n_eps = sum(1 for r in releases if r.get("type", "").lower() == "ep")
    caption = (
        f"🎤 **{name}** — Discografia\n\n"
        f"💿 {n_albums} álbum(ns) · 📀 {n_eps} EP(s) · 🎵 {n_singles} single(s)\n"
        f"  _{total} lançamentos · pág. {page + 1}/{total_pages}_\n\n"
        f"Selecione para ver as faixas:"
    )
    kb = kb_albums(page_items, artist_key, page, total, len(songs))
    await render(target, picture, caption, kb, edit=edit, thread_id=thread_id)


async def _show_songs(target, artist_key: str, page: int,
                      edit: bool = True, thread_id: int | None = None):
    data = await _load_artist(artist_key)
    if not data:
        if hasattr(target, "reply_text"):
            await target.reply_text("❌ Sessão expirada.")
        return
    songs = data.get("_songs", [])
    releases = data.get("_releases", [])
    total = len(songs)
    page_items = songs[page * SONGS_PAGE:(page + 1) * SONGS_PAGE]
    total_pages = max(1, -(-total // SONGS_PAGE))
    picture = data.get("picture", "")
    name = data.get("artist_name", "?")
    if not songs:
        caption = (
            f"🎤 **{name}** — Músicas\n\n"
            f"😕 Nenhuma música disponível via API.\n"
            f"Tente buscar diretamente pelo nome da música."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Artista", callback_data=f"AK:{artist_key}"),
            InlineKeyboardButton(f"💿 Álbuns ({len(releases)})",
                                 callback_data=f"AL:{artist_key}:0"),
            InlineKeyboardButton("✖️ Fechar", callback_data="DEL"),
        ]])
        await render(target, picture, caption, kb, edit=edit, thread_id=thread_id)
        return
    caption = (
        f"🎤 **{name}** — Músicas\n\n"
        f"  _{total} faixas · pág. {page + 1}/{total_pages}_\n\n"
        f"Toque em uma música para baixar:"
    )
    kb = kb_songs(page_items, artist_key, page, total, name, picture, len(releases))
    await render(target, picture, caption, kb, edit=edit, thread_id=thread_id)


async def _show_tracks(target, album_id: str, cover_fb: str,
                       artist_key: str, page: int,
                       edit: bool = True, thread_id: int | None = None):
    try:
        info = await run_search(get_album, album_id)
    except Exception as e:
        if hasattr(target, "reply_text"):
            await target.reply_text(f"❌ Erro ao carregar álbum: {e}")
        return
    tracks = info.get("tracks") or []
    if not tracks:
        if hasattr(target, "reply_text"):
            await target.reply_text("😕 Sem faixas disponíveis.")
        return
    atype = info.get("type", "Álbum")
    artist_name = (info.get("artists") or [{}])[0].get("name", "")
    title = info.get("title", "")
    year = info.get("year", "")
    duration = info.get("duration", "")
    tc = info.get("trackCount") or len(tracks)
    cover = thumb(info.get("thumbnails", [])) or cover_fb
    valid = [t for t in tracks if t.get("videoId") and t.get("isAvailable", True)]
    unavail = len(tracks) - len(valid)
    album_key = cs({"album_id": album_id, "cover": cover,
                    "artist_key": artist_key, "page": page})
    caption = (
        f"{ico(atype)} **{title}**\n\n"
        f"🎤 {artist_name}\n"
        f"🗓 {year} · {atype}\n"
        f"🎵 {tc} faixas"
        + (f" · ⏱ {duration}" if duration else "")
        + (f"\n⚠️ {unavail} faixa(s) indisponível(is)" if unavail else "")
        + f"\n\n✅ {len(valid)} disponíveis para download:"
    )
    kb = kb_tracks(info, album_key)
    await render(target, cover, caption, kb, edit=edit, thread_id=thread_id)


# ══════════════════════════════════════════════
# BUSCA
# ══════════════════════════════════════════════
async def _do_search(message, query: str, thread_id: int | None = None):
    status = await message.reply_text(
        f"🔍 Buscando **{cut(query, 40)}**…",
        parse_mode=ParseMode.HTML)
    results = await run_search(search, query)
    try:
        await status.delete()
    except Exception:
        pass

    artists = results.get("artists", [])
    albums = results.get("albums", [])
    songs = results.get("songs", [])

    if not any([artists, albums, songs]):
        await message.reply_text("😕 Nada encontrado. Tente outro termo.")
        return

    if artists:
        a = artists[0]
        k = cs({
            "artist_id": a["browseId"],
            "artist_name": a.get("artist") or a.get("name") or "?",
            "picture": thumb(a.get("thumbnails", [])),
        })
        await _show_artist_card(message, k, edit=False, thread_id=thread_id)
        return

    if albums and not songs:
        al = albums[0]
        bid = al.get("browseId", "")
        if bid:
            await _show_tracks(message, bid, thumb(al.get("thumbnails", [])),
                               "", 0, edit=False, thread_id=thread_id)
            return

    await message.reply_text(
        f"🔍 **{cut(query, 40)}**\n\n"
        f"💿 = álbum/EP  🎵 = música\n\nSelecione:",
        reply_markup=kb_search_results(results),
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════
# COMANDOS
# ══════════════════════════════════════════════
async def cmd_start(u: Update, ctx):
    if not await _topic_allowed(u):
        return
    if u.effective_user:
        await run_search(db_upsert_user, u.effective_user)
    name = (u.effective_user.first_name or "você") if u.effective_user else "você"
    await u.message.reply_text(
        f"🎵 Olá, **{name}**!\n\n"
        f"Digite para buscar:\n"
        f"  🎤 artista → card com Álbuns e Músicas\n"
        f"  💿 álbum / EP → faixas\n"
        f"  🎵 música → download\n\n"
        f"  **Múltiplas músicas** — separe por vírgula:\n"
        f"`música 1, música 2`\n\n"
        f"`/buscar nome` → busca direta",
        parse_mode=ParseMode.HTML,
    )


async def cmd_buscar(u: Update, ctx):
    if not await _topic_allowed(u):
        return
    if u.effective_user:
        await run_search(db_upsert_user, u.effective_user)
    if not dm_ok(u):
        await u.message.reply_text("❌ Buscas desativadas.")
        return
    q = " ".join(ctx.args).strip() if ctx.args else ""
    if not q:
        await u.message.reply_text(
            "ℹ️ Use: `/buscar nome`", parse_mode=ParseMode.HTML)
        return
    await _do_search(u.message, q, _thread_id(u))


async def cmd_settopic(u: Update, ctx):
    """Configura o tópico do grupo onde o bot responde."""
    if not u.message or not u.effective_chat or not u.effective_user:
        return

    chat = u.effective_chat
    user = u.effective_user
    msg = u.message

    if chat.type not in ("group", "supergroup"):
        await msg.reply_text(
            "❌ Este comando só funciona em **grupos com tópicos** habilitados.",
            parse_mode=ParseMode.HTML)
        return

    is_adm = False
    try:
        member = await chat.get_member(user.id)
        is_adm = member.status in ("administrator", "creator")
    except Exception:
        pass

    if not is_adm and not is_owner(u):
        await msg.reply_text("❌ Apenas **administradores** podem configurar o tópico.",
                             parse_mode=ParseMode.HTML)
        return

    thread_id = msg.message_thread_id
    args = ctx.args or []

    if args and args[0].lower() == "clear":
        await run_search(db_del_topic, chat.id)
        await msg.reply_text(
            "🗑 Configuração de tópico **removida**.\n"
            "O bot voltará a responder em qualquer lugar do grupo.",
            parse_mode=ParseMode.HTML)
        return

    if not thread_id:
        await msg.reply_text(
            "❌ Você precisa usar este comando **dentro de um tópico**.\n\n"
            "Como fazer:\n"
            "1. Abra o tópico desejado\n"
            "2. Digite `/settopic` nesse tópico\n\n"
            "Para remover: `/settopic clear`",
            parse_mode=ParseMode.HTML)
        return

    await run_search(db_set_topic, chat.id, thread_id, user.id)
    await msg.reply_text(
        f"✅ **Tópico configurado com sucesso!**\n\n"
        f"🔒 O bot responderá **apenas neste tópico**.\n"
        f"📌 ID do tópico: `{thread_id}`\n"
        f"🗓 Configurado por: {user.full_name}\n\n"
        f"Para alterar: use `/settopic` em outro tópico.\n"
        f"Para remover: `/settopic clear`",
        parse_mode=ParseMode.HTML)
    log.info(f"📌 Tópico configurado: chat={chat.id} topic={thread_id} by={user.id}")


async def cmd_settings(u: Update, ctx):
    if not is_owner(u):
        await u.message.reply_text("❌ Sem permissão.")
        return
    stats = await run_search(db_stats)
    dm = "🟢 Ativo" if CFG["dm_on"] else "🔴 Inativo"
    await u.message.reply_text(
        "⚙️ **Configurações — MusicBot Pro v5**\n"
        f"{'─' * 30}\n"
        f"💬 Buscas      : {dm}\n"
        f"{'─' * 30}\n"
        f"👥 Usuários    : {stats['users']}\n"
        f"⬇️ Downloads   : {stats['downloads']} (✅ {stats['sent']} enviados)\n"
        f"🎤 Artistas DB : {stats['artists']}\n"
        f"💿 Álbuns DB   : {stats['albums']}\n"
        f"📌 Tópicos conf. : {stats['topics']}\n"
        f"{'─' * 30}\n"
        f"🎚 Qualidade   : {AUDIO_QUALITY} kbps\n"
        f"🔧 ffmpeg      : {'✅' if HAS_FFMPEG else '❌'}\n"
        f"⚡ aria2c      : {'✅ 16x' if HAS_ARIA2C else '❌'}\n"
        f"🔄 Estratégias : {len(_STRATEGIES)}\n"
        f"⚡ DL Slots    : {MAX_DL_SLOTS}\n"
        f"🧵 Search Pool : {SEARCH_POOL._max_workers}w\n"
        f"🧵 DL Pool     : {DL_POOL._max_workers}w\n"
        f"📂 DB          : `{DB_PATH}`\n"
        f"📁 Cache       : `{CACHE_DIR}`",
        reply_markup=kb_settings(),
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════
# HANDLER DE MENSAGENS
# ══════════════════════════════════════════════
async def handle_msg(u: Update, ctx):
    if not u.effective_chat or not u.message:
        return
    if not await _topic_allowed(u):
        return
    if u.effective_user:
        await run_search(db_upsert_user, u.effective_user)
    if not dm_ok(u):
        await u.message.reply_text("❌ Buscas desativadas.")
        return

    query = (u.message.text or "").strip()
    if not query:
        return

    tid = _thread_id(u)
    user_id = u.effective_user.id if u.effective_user else 0

    # Múltiplas músicas separadas por vírgula
    parts = [p.strip() for p in query.split(",") if p.strip()]
    if len(parts) > 1:
        parts = parts[:MAX_BATCH]
        status = await u.message.reply_text(
            f"⚡ **{len(parts)}** músicas — baixando em paralelo…",
            parse_mode=ParseMode.HTML)
        items = [(f"ytsearch1:{p}", p, None) for p in parts]
        await batch_download(ctx.bot, u.effective_chat.id, status, items,
                             f"{len(parts)} músicas", user_id, tid)
        return

    await _do_search(u.message, query, tid)


# ══════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════
async def handle_cb(u: Update, ctx):
    q = u.callback_query
    data = (q.data or "").strip()
    await q.answer()

    chat_id = q.message.chat.id if q.message else q.from_user.id
    msg = q.message
    user_id = q.from_user.id if q.from_user else 0
    tid = msg.message_thread_id if msg else None

    async def _new(text: str):
        return await ctx.bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML,
            **({"message_thread_id": tid} if tid else {}),
        )

    if data == "NOP":
        return
    if data == "DEL":
        try:
            await msg.delete()
        except Exception:
            pass
        return

    if data.startswith("CFG:"):
        if q.from_user.id != OWNER_ID:
            await q.answer("❌ Sem permissão.", show_alert=True)
            return
        k = data.split(":")[1]
        CFG[f"{k}_on"] = not CFG.get(f"{k}_on", True)
        st = "🟢 ativadas" if CFG[f"{k}_on"] else "🔴 desativadas"
        await q.answer(f"Buscas {st}")
        try:
            await msg.edit_reply_markup(kb_settings())
        except Exception:
            pass
        return

    if data.startswith("AK:"):
        await _show_artist_card(msg, data[3:], edit=True)
        return

    if data.startswith("AL:"):
        _, key, pg = data.split(":", 2)
        await _show_albums(msg, key, int(pg), edit=True)
        return

    if data.startswith("SG:"):
        _, key, pg = data.split(":", 2)
        await _show_songs(msg, key, int(pg), edit=True)
        return

    if data.startswith("SA:"):
        d = cg(data[3:])
        if not d:
            await q.answer("Sessão expirada.", show_alert=True)
            return
        await _show_tracks(msg, d["bid"], d.get("cover", ""), "", 0, edit=True)
        return

    if data.startswith("TR:"):
        d = cg(data[3:])
        if not d:
            await q.answer("Sessão expirada.", show_alert=True)
            return
        await _show_tracks(msg, d["album_id"], d.get("cover", ""),
                           d.get("artist_key", ""), d.get("page", 0), edit=True)
        return

    if data.startswith("DL:") or data.startswith("SD:"):
        meta = cg(data[3:])
        if not meta:
            await q.answer("Sessão expirada.", show_alert=True)
            return
        title = meta.get("title", "")
        artist = meta.get("artist", "")
        smsg = await _new(
            f"⏬ **{cut(title)}**"
            + (f" — {artist}" if artist else "") + "\n _Baixando…_"
        )
        log_id = await run_search(db_log_download, user_id, meta)
        vid = meta.get("video_id", "")
        target = (f"https://music.youtube.com/watch?v={vid}"
                  if vid else f"ytsearch1:{title} {artist}")
        res = await dl_task(target, meta)
        if res["ok"]:
            sent = await send_audio(ctx.bot, chat_id, res, tid, log_id)
            try:
                await smsg.delete()
            except Exception:
                pass
            if not sent:
                await _new("⚠️ Arquivo muito grande (> 50 MB).")
        else:
            try:
                await smsg.edit_text(
                    f"❌ **{cut(title)}**\n"
                    f"  _{cut(res['error'], 200)}_",
                    parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return

    if data.startswith("DAL:"):
        d = cg(data[4:])
        if not d:
            await q.answer("Sessão expirada.", show_alert=True)
            return
        tracks = d.get("tracks", [])
        label = d.get("label", "Álbum")
        smsg = await _new(
            f"⚡ **{cut(label, 40)}**\n"
            f"  _Iniciando {len(tracks)} downloads em paralelo…_"
        )
        items = []
        for t in tracks:
            vid = t.get("video_id", "")
            url = (f"https://music.youtube.com/watch?v={vid}" if vid
                   else f"ytsearch1:{t.get('title', '')} {t.get('artist', '')}")
            items.append((url, t.get("title", ""), t))
        await batch_download(ctx.bot, chat_id, smsg, items, label, user_id, tid)
        return


# ══════════════════════════════════════════════
# ERROR HANDLER
# ══════════════════════════════════════════════
async def error_handler(update: object, ctx):
    log.error("Erro não tratado:", exc_info=ctx.error)
