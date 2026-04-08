#!/usr/bin/env python3
"""
══════════════════════════════════════════════
🎵  MusicBot Pro v5 — Entry Point
👨‍💻 Créditos: Edivaldo Silva @Edkd1
══════════════════════════════════════════════

 ✅ SQLite DB — /sdcard/Usuário bot Music/musicbot.db
 ✅ /settopic — configura tópico do grupo
 ✅ Responde APENAS no tópico configurado
 ✅ Downloads rastreados no DB, arquivo apagado após envio
 ✅ Discografia completa com 3 fallbacks
 ✅ Paginação Álbuns ↔ Músicas ↔ Artista
 ✅ Concorrência total (concurrent_updates=True)
"""

import sys
import logging

# ── Bootstrap (instala dependências) ──────────
from config import bootstrap, BOT_TOKEN, AUDIO_QUALITY, MAX_DL_SLOTS, HAS_FFMPEG, HAS_ARIA2C, DB_PATH, CACHE_DIR
bootstrap()

from rich.logging import RichHandler
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from database import db_init
from downloader import run_search, init_semaphore, SEARCH_POOL, DL_POOL, _STRATEGIES
from handlers import (
    cmd_start, cmd_buscar, cmd_settopic, cmd_settings,
    handle_msg, handle_cb, error_handler,
)

# ── Logging ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO, format="%(message)s",
    handlers=[RichHandler(show_path=False, rich_tracebacks=True)],
)
log = logging.getLogger("musicbot")
for _n in ("httpx", "telegram", "urllib3", "asyncio"):
    logging.getLogger(_n).setLevel(logging.WARNING)


# ══════════════════════════════════════════════
# INICIALIZAÇÃO
# ══════════════════════════════════════════════
async def _on_init(app) -> None:
    init_semaphore()
    await run_search(db_init)
    await app.bot.set_my_commands([
        BotCommand("start", "🎵 Início"),
        BotCommand("buscar", "🔍 Buscar artista, álbum ou música"),
        BotCommand("settopic", "📌 Configurar tópico do grupo"),
        BotCommand("settings", "⚙️ Configurações (owner)"),
    ])
    log.info(
        f"\n✅ MusicBot Pro v5\n"
        f"   DB         : {DB_PATH}\n"
        f"   cache      : {CACHE_DIR}\n"
        f"   ffmpeg     : {HAS_FFMPEG}\n"
        f"   aria2c     : {HAS_ARIA2C}\n"
        f"   qualidade  : {AUDIO_QUALITY} kbps\n"
        f"   estratégias: {len(_STRATEGIES)}\n"
        f"   DL slots   : {MAX_DL_SLOTS}\n"
        f"   search pool: {SEARCH_POOL._max_workers}w\n"
        f"   dl pool    : {DL_POOL._max_workers}w"
    )


def main():
    if BOT_TOKEN == "SEU_TOKEN_AQUI":
        sys.exit("❌ Configure BOT_TOKEN no topo do arquivo config.py.")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(180)
        .connect_timeout(30)
        .concurrent_updates(True)
        .post_init(_on_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CommandHandler("settopic", cmd_settopic))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

# ┌─────────────────────────────────────────────────────┐
# │ INSTALAÇÃO:                                         │
# │   pip install -r requirements.txt                   │
# │   python main.py                                    │
# │                                                     │
# │ TÓPICOS:                                            │
# │ 1. Abra o tópico desejado no grupo                  │
# │ 2. Digite /settopic (sendo admin)                   │
# │ 3. Bot confirma com o ID do tópico                  │
# │ 4. Bot ignora QUALQUER mensagem fora do tópico      │
# │                                                     │
# │ Para alterar → /settopic em outro tópico             │
# │ Para remover → /settopic clear                       │
# └─────────────────────────────────────────────────────┘
