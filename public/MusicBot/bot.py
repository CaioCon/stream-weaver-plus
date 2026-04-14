#!/usr/bin/env python3
"""
🎵 Telegram Music Downloader Bot
Powered by Deemix | Suporte a músicas, álbuns, playlists, artistas e gêneros

Uso:
 pip install -r requirements.txt
 python bot.py
"""

import asyncio
import logging
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatAction

import config
from utils import (
    detect_url_type,
    build_deezer_url,
    format_duration,
    format_number,
    get_free_space,
    is_user_allowed,
    setup_logging,
)
from downloader import MusicDownloader

# ── Setup ─────────────────────────────────────────────────────────

logger = setup_logging()

music_dl = MusicDownloader(
    arl_token=config.ARL_TOKEN,
    download_path=config.DOWNLOAD_PATH,
)

# ═══════════════════════════════════════════════════════════════════
# GUARDS
# ═══════════════════════════════════════════════════════════════════

def require_auth(func):
    """Decorator: bloqueia usuários não autorizados."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not is_user_allowed(user.id):
            await update.effective_message.reply_text(
                "⛔ *Acesso negado.*\n"
                "Você não tem permissão para usar este bot.",
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.warning(f"Acesso negado para {user.id} (@{user.username})")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

# ═══════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Ajuda", callback_data="help"),
            InlineKeyboardButton("⚙️ Qualidade", callback_data="menu_quality"),
        ],
        [
            InlineKeyboardButton("🔍 Buscar Música", callback_data="prompt_search"),
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
    ])

def kb_confirm_download(url_type: str, item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"⬇️ Baixar {config.TYPE_LABEL.get(url_type, 'Item')}",
            callback_data=f"dl_{url_type}_{item_id}",
        )],
        [InlineKeyboardButton("❌ Cancelar", callback_data="close")],
    ])

def kb_quality(back_cb: str = "close") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"setq_{key}")]
        for key, label in config.QUALITY_LABELS.items()
    ]
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

def kb_genre_artists(artists: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            f"🎸 {a['name']}",
            callback_data=f"dl_artist_{a['id']}",
        )]
        for a in artists
    ]
    rows.append([InlineKeyboardButton("❌ Fechar", callback_data="close")])
    return InlineKeyboardMarkup(rows)

def kb_search_results(tracks: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            f"⬇️ {i}. {t['title'][:28]} — {t['artist'][:20]}",
            callback_data=f"dl_track_{t['id']}",
        )]
        for i, t in enumerate(tracks, 1)
    ]
    rows.append([InlineKeyboardButton("❌ Cancelar", callback_data="close")])
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════════════
# TEXTOS INFORMATIVOS
# ═══════════════════════════════════════════════════════════════════

async def build_item_info_text(url_type: str, item_id: str) -> str:
    """Monta texto descritivo de um item Deezer."""
    try:
        if url_type == "track":
            info = music_dl.get_track_info(item_id)
            return (
                f"🎵 *{info['title']}*\n"
                f"👤 Artista: {info['artist']}\n"
                f"💿 Álbum: {info['album']}\n"
                f"⏱ Duração: {format_duration(info['duration'])}"
            )
        elif url_type == "album":
            info = music_dl.get_album_info(item_id)
            return (
                f"💿 *{info['title']}*\n"
                f"👤 Artista: {info['artist']}\n"
                f"🎼 Gênero: {info['genre']}\n"
                f"🎵 Faixas: {info['nb_tracks']}\n"
                f"📅 Lançamento: {info['release_date']}"
            )
        elif url_type == "playlist":
            info = music_dl.get_playlist_info(item_id)
            return (
                f"📋 *{info['title']}*\n"
                f"👤 Criador: {info['creator']}\n"
                f"🎵 Faixas: {info['nb_tracks']}\n"
                f"⏱ Duração total: {format_duration(info['duration'])}"
            )
        elif url_type == "artist":
            info = music_dl.get_artist_info(item_id)
            return (
                f"🎸 *{info['name']}*\n"
                f"👥 Fãs: {format_number(info['nb_fan'])}\n"
                f"💿 Álbuns: {info['nb_album']}"
            )
    except Exception as exc:
        logger.error(f"Erro ao obter info ({url_type}/{item_id}): {exc}")
        return f"ID: `{item_id}`"
    return f"ID: `{item_id}`"

# ═══════════════════════════════════════════════════════════════════
# HANDLERS — COMANDOS
# ═══════════════════════════════════════════════════════════════════

@require_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🎵 *Olá, {user.first_name}!*\n\n"
        "Bem-vindo ao *Music Downloader Bot*!\n\n"
        "📥 *O que posso baixar:*\n"
        " • 🎵 Músicas individuais\n"
        " • 💿 Álbuns completos\n"
        " • 📋 Playlists\n"
        " • 🎸 Discografia de artistas\n"
        " • 🎼 Artistas por gênero musical\n\n"
        "📌 *Como usar:*\n"
        "Envie um link do Deezer ou use `/search` para buscar!\n\n"
        "```\n"
        "deezer.com/track/ID\n"
        "deezer.com/album/ID\n"
        "deezer.com/playlist/ID\n"
        "deezer.com/artist/ID\n"
        "deezer.com/genre/ID\n"
        "```"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )

@require_auth
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Comandos disponíveis*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "/start — Menu principal\n"
        "/help — Esta mensagem\n"
        "/search — Buscar música\n"
        "/quality — Alterar qualidade\n"
        "/status — Status do bot\n"
        "/queue — Fila de downloads\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Links suportados:*\n\n"
        "`deezer.com/track/ID` 🎵 Música\n"
        "`deezer.com/album/ID` 💿 Álbum\n"
        "`deezer.com/playlist/ID` 📋 Playlist\n"
        "`deezer.com/artist/ID` 🎸 Artista\n"
        "`deezer.com/genre/ID` 🎼 Gênero\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@require_auth
async def cmd_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = context.user_data.get("quality", config.DEFAULT_QUALITY)
    text = (
        "⚙️ *Configurar Qualidade*\n\n"
        f"Qualidade atual: {config.QUALITY_LABELS.get(current)}\n\n"
        "Selecione a nova qualidade:"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_quality(),
    )

@require_auth
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok = music_dl.logged_in
    space = get_free_space(config.DOWNLOAD_PATH)
    qual = context.user_data.get("quality", config.DEFAULT_QUALITY)
    queue = context.bot_data.get("download_queue", [])

    text = (
        "📊 *Status do Bot*\n\n"
        f"{'✅' if ok else '❌'} Deezer: "
        f"{'Conectado' if ok else 'Desconectado'}\n"
        f"⚙️ Qualidade: {config.QUALITY_LABELS.get(qual)}\n"
        f"📁 Pasta: `{config.DOWNLOAD_PATH}`\n"
        f"💾 Espaço livre: {space}\n"
        f"📥 Fila: {len(queue)} item(s)\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@require_auth
async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = context.bot_data.get("download_queue", [])
    if not queue:
        await update.message.reply_text("📭 Fila de downloads vazia.")
        return

    lines = "\n".join(
        f"{i}. `{item['url']}`" for i, item in enumerate(queue, 1)
    )
    text = f"📥 *Fila de Downloads ({len(queue)})*\n\n{lines}"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@require_auth
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🔍 *Como buscar:*\n"
            "`/search Nome da Música - Artista`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = " ".join(context.args)
    await _do_search(update.message, query)

# ═══════════════════════════════════════════════════════════════════
# HANDLER — MENSAGENS (URLs)
# ═══════════════════════════════════════════════════════════════════

@require_auth
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detecta URLs do Deezer enviadas como texto."""
    text = update.message.text or ""

    # Tenta detectar URL do Deezer
    url_type, item_id = detect_url_type(text)

    if not url_type:
        # Trata como busca por texto simples
        await _do_search(update.message, text)
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    if url_type == "genre":
        await _show_genre(update.message, item_id)
        return

    emoji = config.TYPE_EMOJI.get(url_type, "🎵")
    label = config.TYPE_LABEL.get(url_type, "Item")
    info = await build_item_info_text(url_type, item_id)

    await update.message.reply_text(
        f"{emoji} *{label} encontrado!*\n\n{info}\n\n"
        "Deseja iniciar o download?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_confirm_download(url_type, item_id),
    )

# ═══════════════════════════════════════════════════════════════════
# HANDLER — CALLBACKS
# ═══════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Fechar ────────────────────────────────────────────────────
    if data == "close":
        await query.message.delete()
        return

    # ── Ajuda ─────────────────────────────────────────────────────
    if data == "help":
        text = (
            "📖 *Guia Rápido*\n\n"
            "Envie qualquer link do Deezer:\n\n"
            "`deezer.com/track/ID`\n"
            "`deezer.com/album/ID`\n"
            "`deezer.com/playlist/ID`\n"
            "`deezer.com/artist/ID`\n"
            "`deezer.com/genre/ID`\n\n"
            "Ou use `/search artista - música`"
        )
        await query.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Voltar", callback_data="back_start")
            ]]),
        )
        return

    # ── Voltar ao início ──────────────────────────────────────────
    if data == "back_start":
        await query.message.edit_text(
            "🎵 *Music Downloader Bot*\n\n"
            "Envie um link do Deezer ou use os botões abaixo.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main_menu(),
        )
        return

    # ── Status ────────────────────────────────────────────────────
    if data == "status":
        ok = music_dl.logged_in
        space = get_free_space(config.DOWNLOAD_PATH)
        qual = context.user_data.get("quality", config.DEFAULT_QUALITY)
        await query.message.edit_text(
            "📊 *Status do Bot*\n\n"
            f"{'✅' if ok else '❌'} Deezer: "
            f"{'Conectado' if ok else 'Desconectado'}\n"
            f"⚙️ Qualidade: {config.QUALITY_LABELS.get(qual)}\n"
            f"📁 Pasta: `{config.DOWNLOAD_PATH}`\n"
            f"💾 Espaço livre: {space}\n",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Voltar", callback_data="back_start")
            ]]),
        )
        return

    # ── Menu de qualidade ─────────────────────────────────────────
    if data == "menu_quality":
        current = context.user_data.get("quality", config.DEFAULT_QUALITY)
        await query.message.edit_text(
            f"⚙️ *Qualidade de Download*\n\n"
            f"Atual: {config.QUALITY_LABELS.get(current)}\n\n"
            "Selecione:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_quality(back_cb="back_start"),
        )
        return

    # ── Definir qualidade ─────────────────────────────────────────
    if data.startswith("setq_"):
        quality = data.removeprefix("setq_")
        context.user_data["quality"] = quality
        label = config.QUALITY_LABELS.get(quality, quality)
        await query.message.edit_text(
            f"✅ Qualidade alterada para:\n*{label}*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Prompt de busca ───────────────────────────────────────────
    if data == "prompt_search":
        await query.message.edit_text(
            "🔍 *Buscar Música*\n\n"
            "Use o comando:\n"
            "`/search nome da música`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Iniciar download ──────────────────────────────────────────
    if data.startswith("dl_"):
        parts = data.removeprefix("dl_").split("_", 1)
        if len(parts) == 2:
            url_type, item_id = parts
            url = build_deezer_url(url_type, item_id)
            await _execute_download(query.message, context, url, url_type)
        return

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES INTERNAS DE SUPORTE
# ═══════════════════════════════════════════════════════════════════

async def _do_search(message: Message, query: str):
    """Realiza busca e exibe resultados."""
    await message.chat.send_action(ChatAction.TYPING)
    status = await message.reply_text(
        f"🔍 Buscando: *{query}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        tracks = music_dl.search_tracks(query)

        if not tracks:
            await status.edit_text("❌ Nenhum resultado encontrado.")
            return

        lines = []
        for i, t in enumerate(tracks, 1):
            dur = format_duration(t["duration"])
            lines.append(
                f"{i}. 🎵 *{t['title']}*\n"
                f"    👤 {t['artist']} | ⏱ {dur}"
            )

        text = (
            f"🔍 *Resultados para:* `{query}`\n\n"
            + "\n\n".join(lines)
        )

        await status.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_search_results(tracks),
        )

    except Exception as exc:
        logger.error(f"Erro na busca '{query}': {exc}")
        await status.edit_text(f"❌ Erro na busca:\n`{exc}`", parse_mode=ParseMode.MARKDOWN)

async def _show_genre(message: Message, genre_id: str):
    """Exibe artistas de um gênero para seleção de download."""
    status = await message.reply_text("🎼 Carregando gênero...")

    try:
        info = music_dl.get_genre_info(genre_id)
        artists = info["artists"]

        if not artists:
            await status.edit_text("❌ Nenhum artista encontrado para este gênero.")
            return

        artist_lines = "\n".join(f"• {a['name']}" for a in artists)
        text = (
            f"🎼 *Gênero: {info['name']}*\n\n"
            f"🎸 *Artistas em destaque:*\n{artist_lines}\n\n"
            "Selecione um artista para baixar:"
        )

        await status.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_genre_artists(artists),
        )

    except Exception as exc:
        logger.error(f"Erro ao carregar gênero {genre_id}: {exc}")
        await status.edit_text(f"❌ Erro:\n`{exc}`", parse_mode=ParseMode.MARKDOWN)

async def _execute_download(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    url_type: str,
):
    """Executa o download em background e atualiza o status."""
    quality = context.user_data.get("quality", config.DEFAULT_QUALITY)
    bitrate = config.BITRATE_MAP[quality]
    emoji = config.TYPE_EMOJI.get(url_type, "🎵")
    label = config.QUALITY_LABELS.get(quality)

    status_msg = await message.edit_text(
        f"{emoji} *Iniciando download...*\n\n"
        f"🔗 `{url}`\n"
        f"⚙️ Qualidade: {label}\n\n"
        f"⏳ Aguarde...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Enfileira para controle
    queue: list = context.bot_data.setdefault("download_queue", [])
    entry = {"url": url, "quality": quality}
    queue.append(entry)

    try:
        loop = asyncio.get_event_loop()

        last_update = {"i": 0}

        def progress(i: int, total: int):
            last_update["i"] = i
            # Atualização de progresso (fire-and-forget seguro)
            asyncio.run_coroutine_threadsafe(
                status_msg.edit_text(
                    f"{emoji} *Baixando... {i}/{total}*\n\n"
                    f"🔗 `{url}`\n"
                    f"⚙️ {label}\n\n"
                    f"{'▓' * int((i/total)*10)}{'░' * (10 - int((i/total)*10))} "
                    f"{int((i/total)*100)}%",
                    parse_mode=ParseMode.MARKDOWN,
                ),
                loop,
            )

        success, total = await loop.run_in_executor(
            None,
            lambda: music_dl.download(url, bitrate, progress),
        )

        result_icon = "✅" if success == total else "⚠️"
        await status_msg.edit_text(
            f"{result_icon} *Download finalizado!*\n\n"
            f"{emoji} {success}/{total} itens baixados\n"
            f"📁 Pasta: `{config.DOWNLOAD_PATH}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as exc:
        logger.error(f"Erro no download '{url}': {exc}")
        await status_msg.edit_text(
            f"❌ *Erro no download!*\n\n`{exc}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if entry in queue:
            queue.remove(entry)

# ═══════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exceção não tratada: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ocorreu um erro inesperado.\nPor favor, tente novamente."
        )

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    # Validações iniciais
    if not config.TELEGRAM_TOKEN:
        logger.critical("❌ TELEGRAM_TOKEN não configurado.")
        raise SystemExit(1)

    if not config.ARL_TOKEN:
        logger.warning("⚠️ ARL_TOKEN não configurado — downloads desabilitados.")

    # Login no Deezer
    music_dl.login()

    # Cria a aplicação
    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .build()
    )

    # ── Comandos ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("quality", cmd_quality))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("search", cmd_search))

    # ── Mensagens com URL do Deezer ───────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    ))

    # ── Callbacks de botões ───────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Erros ─────────────────────────────────────────────────────
    app.add_error_handler(error_handler)

    logger.info("🤖 Bot iniciado. Aguardando mensagens...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

# 1. Instalar dependências
# pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
# cp .env.example .env
# Edite o .env com seu TELEGRAM_TOKEN e ARL_TOKEN

# 3. Obter o ARL Token:
# - Acesse deezer.com no navegador
# - Abra DevTools > Application > Cookies
# - Copie o valor do cookie "arl"

# 4. Executar
# python bot.py
