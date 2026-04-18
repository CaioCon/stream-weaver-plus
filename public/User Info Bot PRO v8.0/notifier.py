# ══════════════════════════════════════════════
# 🔔  NOTIFIER — Cards no canal de notificação
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
Toda notificação vai para o canal NOTIFY_CHANNEL_ID.
Cada usuário tem 1 card no canal; novas alterações editam o card.
"""

import io
from telethon import Button
from config import NOTIFY_CHANNEL_ID, OWNER_ID
from db import log, get_card_msg_id, set_card_msg_id, is_field_hidden
from profile import montar_card
from format import to_html, HTML


def _gerencia_buttons(uid: str):
    """Botões de gerenciamento que aparecem abaixo de cada card."""
    return [
        [Button.inline("👁 Ocultar/mostrar campos", f"mng_{uid}".encode())],
        [Button.inline("🗑 Apagar card", f"del_{uid}".encode())],
    ]


async def enviar_ou_editar_card(bot, uid: str, dados: dict, *,
                                 photo_bytes: bytes = None) -> int:
    """
    Posta um card novo (com foto se houver) ou edita o existente.
    Retorna o message_id do card.
    """
    uid = str(uid)
    caption_md = montar_card(uid, dados)
    caption    = to_html(caption_md)
    botoes     = _gerencia_buttons(uid)
    msg_id     = get_card_msg_id(uid)

    show_photo = bool(photo_bytes) and not is_field_hidden("foto")

    try:
        if msg_id:
            # Editar caption (não dá pra trocar foto via edit_message no Telethon
            # de modo confiável; mantemos a mídia original).
            try:
                await bot.edit_message(NOTIFY_CHANNEL_ID, msg_id,
                                       caption, parse_mode=HTML, buttons=botoes)
                return msg_id
            except Exception as e:
                log(f"⚠️ edit card {uid} falhou ({e}); reenviando.")
                try:
                    await bot.delete_messages(NOTIFY_CHANNEL_ID, msg_id)
                except Exception:
                    pass

        if show_photo:
            file = io.BytesIO(photo_bytes)
            file.name = f"{uid}.jpg"
            sent = await bot.send_file(
                NOTIFY_CHANNEL_ID, file=file,
                caption=caption, parse_mode=HTML, buttons=botoes,
            )
        else:
            sent = await bot.send_message(
                NOTIFY_CHANNEL_ID, caption, parse_mode=HTML,
                buttons=botoes, link_preview=False,
            )
        set_card_msg_id(uid, sent.id)
        return sent.id
    except Exception as e:
        log(f"❌ enviar_card({uid}): {e}")
        return 0


async def avisar_owner_remocao(bot, requisitante, uid_alvo: str):
    """Quando um usuário pede em DM a remoção dos próprios dados,
    avisa o owner (em DM)."""
    nome = (requisitante.first_name or "") + " " + (requisitante.last_name or "")
    nome = nome.strip() or "_(sem nome)_"
    user = f"@{requisitante.username}" if requisitante.username else "_(sem username)_"
    txt = (
        "🚨 *PEDIDO DE REMOÇÃO DE DADOS*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Solicitante*: {nome}\n"
        f"🆔 *ID*: `{requisitante.id}`\n"
        f"🔗 *Username*: {user}\n\n"
        f"🎯 *Card alvo*: `{uid_alvo}`\n\n"
        "_Use os botões abaixo para confirmar._"
    )
    botoes = [[
        Button.inline("✅ Remover card", f"rmcard_{uid_alvo}_{requisitante.id}".encode()),
        Button.inline("❌ Negar", f"rmdeny_{requisitante.id}".encode()),
    ]]
    try:
        await bot.send_message(OWNER_ID, to_html(txt),
                               parse_mode=HTML, buttons=botoes)
    except Exception as e:
        log(f"❌ avisar_owner_remocao: {e}")
