#!/usr/bin/env python3
# ══════════════════════════════════════════════
# 🎨  RENDERIZADOR & ENVIO — MusicBot Pro v5
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import os
import asyncio
import logging

from telegram import InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode, ChatAction
from telegram.error import BadRequest, RetryAfter, TimedOut

from helpers import cut, cleanup
from database import db_log_sent
from downloader import run_search

log = logging.getLogger("musicbot")


# ══════════════════════════════════════════════
# RENDERIZADOR CENTRAL
# Edita mensagem se edit=True, senão envia nova.
# ══════════════════════════════════════════════
async def render(
    target,
    photo: str,
    caption: str,
    kb: InlineKeyboardMarkup,
    edit: bool = False,
    thread_id: int | None = None,
) -> None:
    """Renderiza mensagem com foto + caption + teclado inline."""
    # ── Editar mensagem existente ─────────────────────────
    if edit and hasattr(target, "chat"):
        try:
            if photo:
                await target.edit_media(
                    InputMediaPhoto(media=photo, caption=caption,
                                    parse_mode=ParseMode.HTML),
                    reply_markup=kb,
                )
                return
            try:
                await target.edit_caption(caption, reply_markup=kb,
                                          parse_mode=ParseMode.HTML)
                return
            except BadRequest:
                await target.edit_text(caption, reply_markup=kb,
                                       parse_mode=ParseMode.HTML)
                return
        except Exception as e:
            log.debug(f"_render edit falhou ({type(e).__name__})")

    # ── Enviar nova mensagem ──────────────────────────────
    extra = {}
    if thread_id:
        extra["message_thread_id"] = thread_id

    if hasattr(target, "reply_photo"):
        if photo:
            try:
                await target.reply_photo(photo=photo, caption=caption,
                                         reply_markup=kb, parse_mode=ParseMode.HTML)
                return
            except Exception:
                pass
        await target.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif isinstance(target, tuple):
        bot, chat_id = target
        if photo:
            try:
                await bot.send_photo(chat_id, photo=photo, caption=caption,
                                     reply_markup=kb, parse_mode=ParseMode.HTML,
                                     **extra)
                return
            except Exception:
                pass
        await bot.send_message(chat_id, caption, reply_markup=kb,
                               parse_mode=ParseMode.HTML, **extra)


# ══════════════════════════════════════════════
# ENVIO DE ÁUDIO
# Arquivo é SEMPRE apagado no finally
# ══════════════════════════════════════════════
async def send_audio(
    bot, chat_id: int, res: dict,
    thread_id: int | None = None,
    log_id: int | None = None,
) -> bool:
    """Envia arquivo de áudio e limpa arquivo local após envio."""
    path = res.get("file", "")
    if not path or not os.path.isfile(path):
        log.error(f"send_audio: arquivo ausente → {path}")
        return False
    try:
        size_mb = os.path.getsize(path) / 1024 / 1024
        if size_mb > 49:
            await bot.send_message(
                chat_id,
                f"⚠️ **{cut(res.get('title', ''))}** — "
                f"arquivo muito grande ({size_mb:.1f} MB).",
                parse_mode=ParseMode.HTML,
                **({"message_thread_id": thread_id} if thread_id else {}),
            )
            return False
        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VOICE)
        with open(path, "rb") as f:
            await bot.send_audio(
                chat_id, audio=f,
                title=res.get("title", ""),
                performer=res.get("artist", ""),
                duration=int(res.get("dur") or 0),
                read_timeout=180, write_timeout=180, connect_timeout=30,
                **({"message_thread_id": thread_id} if thread_id else {}),
            )
        if log_id:
            await run_search(db_log_sent, log_id)
        return True
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        return await send_audio(bot, chat_id, res, thread_id, log_id)
    except TimedOut:
        log.warning("send_audio: timeout")
        return False
    finally:
        cleanup(path)


# ══════════════════════════════════════════════
# BATCH PARALELO
# ══════════════════════════════════════════════
async def batch_download(
    bot, chat_id: int, status_msg,
    items: list[tuple], label: str,
    user_id: int = 0,
    thread_id: int | None = None,
):
    """Baixa e envia múltiplas faixas em paralelo."""
    from downloader import dl_task
    from database import db_log_download

    total = len(items)
    ok = err = 0
    tasks = [asyncio.create_task(dl_task(url, meta)) for url, _, meta in items]

    for i, (task, (_, display, meta)) in enumerate(zip(tasks, items), 1):
        bar = "█" * round((i - 1) / total * 10) + "░" * (10 - round((i - 1) / total * 10))
        try:
            await status_msg.edit_text(
                f"⏬ **{cut(label, 40)}**\n\n"
                f"🎵 `{cut(display, 46)}`\n"
                f"`[{bar}]` {i}/{total} ({round((i - 1) / total * 100)}%)",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

        log_id = 0
        if user_id:
            log_id = await run_search(db_log_download, user_id, meta)

        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VOICE)
        res = await task

        if res["ok"]:
            sent = await send_audio(bot, chat_id, res, thread_id, log_id)
            ok += sent
            err += (not sent)
        else:
            err += 1
            try:
                await bot.send_message(
                    chat_id,
                    f"❌ `{cut(display)}`\n"
                    f"  _{cut(res['error'], 120)}_",
                    parse_mode=ParseMode.HTML,
                    **({"message_thread_id": thread_id} if thread_id else {}),
                )
            except Exception:
                pass

    icon = "✅" if not err else ("⚠️" if ok else "❌")
    try:
        await status_msg.edit_text(
            f"{icon} **{cut(label, 40)}**\n"
            f"✅ {ok} enviada(s)" + (f"  ❌ {err} erro(s)" if err else ""),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
