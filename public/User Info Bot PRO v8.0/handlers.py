# ══════════════════════════════════════════════
# 🎮  HANDLERS — User Info Bot PRO v8.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
Eventos cobertos:
  • /start em DM (curto, instruções).
  • /remover em DM = pedido de remoção dos dados → notifica owner.
  • InlineQuery: @InforUser_Bot @username  |  @InforUser_Bot 123456789
       → mostra DADOS COMPLETOS (Nome, ID, Username, Bio, Grupos, Histórico).
       → 📱 Telefone APENAS se o solicitante estiver autorizado pelo dono.
  • Em DM o bot NÃO faz consulta de dados. Apenas o canal recebe perfis completos.
  • Comandos do owner no canal de notificação:
       /scan            força varredura imediata
       /panel           painel de toggles globais
       /show <campo>    /hide <campo>   atalhos
       /auth <id|@user> autoriza usuário a ver telefone via inline
       /unauth <id|@user>
       /auths           lista autorizados
  • Callbacks dos cards:
       mng_<uid>        abre painel de toggles do canal
       togg_<campo>     alterna oculto/visível
       del_<uid>        remove o card do canal e do índice
       rmcard_<uid>_<req_id> / rmdeny_<req_id>  (no DM do owner)
"""

import asyncio
from telethon import events, Button

from config import (OWNER_ID, BOT_USERNAME, NOTIFY_CHANNEL_ID,
                    NOTIFY_CHANNEL_LINK,
                    INLINE_USERNAME_RE, INLINE_ID_RE, TOGGLEABLE_FIELDS)
from db import (carregar_dados, salvar_dados, log,
                get_card_msg_id, set_card_msg_id, del_card_msg_id,
                carregar_settings, toggle_field_hidden, is_field_hidden,
                upsert_user, salvar_settings,
                is_phone_authorized, autorizar_phone, desautorizar_phone,
                listar_phone_auth)
from format import to_html, HTML
from profile import montar_card
from search import buscar_com_lookup
from notifier import enviar_ou_editar_card, avisar_owner_remocao
import scan as scan_mod


# ────────────────────────────────────────────────────────────
def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


def _painel_buttons():
    s = carregar_settings()["hidden_global"]
    rows, row = [], []
    for f in TOGGLEABLE_FIELDS:
        marca = "🚫" if s.get(f) else "✅"
        row.append(Button.inline(f"{marca} {f}", f"togg_{f}".encode()))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([Button.url("📺 Abrir canal", NOTIFY_CHANNEL_LINK)])
    return rows


def _painel_text() -> str:
    s = carregar_settings()["hidden_global"]
    linhas = ["⚙️ *PAINEL DE GERENCIAMENTO*",
              "━━━━━━━━━━━━━━━━━━━━",
              "Marque qual campo deve ficar *oculto* nos cards do canal.",
              ""]
    for f in TOGGLEABLE_FIELDS:
        st = "🚫 oculto" if s.get(f) else "✅ visível"
        linhas.append(f"• `{f}` — {st}")
    return "\n".join(linhas)


def _montar_card_inline(uid: str, ent: dict, *, viewer_uid: int) -> str:
    """
    Monta caption COMPLETA para inline.
    Inclui telefone APENAS se viewer estiver autorizado (ou for o owner).
    Não respeita hidden_global do canal — o filtro do canal é separado.
    """
    nome     = ent.get("nome_atual") or "_Sem nome_"
    username = ent.get("username_atual") or ""
    phone    = ent.get("phone") or ""
    bio      = ent.get("bio") or ""
    grupos   = ent.get("grupos") or []
    hist     = ent.get("historico") or []

    pode_ver_phone = (viewer_uid == OWNER_ID) or is_phone_authorized(viewer_uid)

    linhas = ["━━━━━━━━━━━━━━━━━━━━",
              "👤 *DADOS DO USUÁRIO*",
              "━━━━━━━━━━━━━━━━━━━━",
              f"📛 *Nome*: {nome}",
              f"🆔 *ID*: `{uid}`",
              f"🔗 *Username*: {('@'+username) if username else '_(nenhum)_'}"]

    if phone:
        if pode_ver_phone:
            linhas.append(f"📱 *Telefone*: `{phone}`")
        else:
            linhas.append("📱 *Telefone*: 🔒 _restrito_")
    if bio:
        linhas.append(f"📝 *Bio*: {bio}")
    if grupos:
        amostra = ", ".join(grupos[:5])
        extra   = f" *(+{len(grupos)-5})*" if len(grupos) > 5 else ""
        linhas.append(f"📂 *Grupos*: {amostra}{extra}")
    if hist:
        linhas.append("📜 *Últimas mudanças*:")
        for h in hist[-3:]:
            linhas.append(f"  • _{h.get('tipo')}_ `{h.get('de','?')}` ➜ `{h.get('para','?')}`")

    linhas.append(f"\n🕒 _Atualizado: {ent.get('ultima_atualizacao','?')}_")
    if not pode_ver_phone and phone:
        linhas.append("\n_ℹ️ Telefone disponível apenas para usuários autorizados pelo dono._")
    return "\n".join(linhas)


async def _resolver_uid_alvo(user_client, alvo: str):
    """Recebe '@user', 'user' ou '12345' e devolve int(uid)."""
    alvo = alvo.strip().lstrip("@")
    if alvo.isdigit():
        return int(alvo)
    try:
        ent = await user_client.get_entity(alvo)
        return int(ent.id)
    except Exception as e:
        log(f"resolver alvo '{alvo}': {e}")
        return None


# ────────────────────────────────────────────────────────────
def register_handlers(bot, user_client):

    # ─── /start em DM ───
    @bot.on(events.NewMessage(pattern=r'^/start(?:\s|$)', func=lambda e: e.is_private))
    async def cmd_start(event):
        txt = (
            "👋 *User Info Bot PRO v8.0*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Eu monitoro perfis em grupos públicos e publico cards no canal "
            "de notificação do dono.\n\n"
            "🔎 *Como pesquisar (em qualquer chat):*\n"
            f"  `@{BOT_USERNAME} @username`\n"
            f"  `@{BOT_USERNAME} 1234567890`\n\n"
            "🚫 *Não faço consultas por DM.*\n"
            "🗑 *Quer remover seus dados?* Envie `/remover`."
        )
        await event.respond(to_html(txt), parse_mode=HTML, link_preview=False)

    # ─── /remover em DM ───
    @bot.on(events.NewMessage(pattern=r'^/remover(?:\s+(\d+))?$',
                              func=lambda e: e.is_private))
    async def cmd_remover(event):
        sender = await event.get_sender()
        uid_alvo = event.pattern_match.group(1) or str(sender.id)
        await avisar_owner_remocao(bot, sender, uid_alvo)
        await event.respond(to_html(
            "✅ *Pedido enviado ao dono.*\n"
            "Você será notificado se o card for removido."
        ), parse_mode=HTML)

    # ─── Texto livre em DM (NÃO consulta dados) ───
    @bot.on(events.NewMessage(func=lambda e: e.is_private and
                              not (e.text or '').startswith('/')))
    async def dm_text(event):
        if event.sender_id == OWNER_ID:
            return  # owner conversa livremente
        await event.respond(to_html(
            "🚫 *Eu não realizo consultas por DM.*\n\n"
            f"🔎 Use o modo inline em qualquer chat:\n"
            f"`@{BOT_USERNAME} @username` ou `@{BOT_USERNAME} 1234567890`\n\n"
            "🗑 Para pedir remoção dos seus dados envie `/remover`."
        ), parse_mode=HTML)

    # ─── Inline query (lookup público — DADOS COMPLETOS, telefone restrito) ───
    @bot.on(events.InlineQuery)
    async def inline(event):
        q = (event.text or "").strip()
        if not q:
            await event.answer([], switch_pm="Como usar", switch_pm_param="start")
            return
        m_user = INLINE_USERNAME_RE.match(q)
        m_id   = INLINE_ID_RE.match(q)
        if not (m_user or m_id):
            await event.answer([], switch_pm="Use @username ou ID numérico",
                                switch_pm_param="start")
            return

        query = m_user.group(1) if m_user else m_id.group(1)
        viewer_uid = event.sender_id
        results = await buscar_com_lookup(user_client, query)
        articles = []
        for uid, ent in results[:10]:
            nome = ent.get("nome_atual") or "_Sem nome_"
            user = ent.get("username_atual") or ""
            txt  = _montar_card_inline(uid, ent, viewer_uid=viewer_uid)
            articles.append(event.builder.article(
                title=nome[:60] or "Sem nome",
                description=f"@{user}" if user else f"ID {uid}",
                text=to_html(txt), parse_mode=HTML,
            ))

            # Em paralelo: garante card COMPLETO no canal (com telefone)
            asyncio.create_task(enviar_ou_editar_card(
                bot, uid, ent, photo_bytes=ent.pop("_photo_bytes", None),
            ))

        if not articles:
            await event.answer([], switch_pm="Usuário não encontrado",
                                switch_pm_param="start")
            return
        await event.answer(articles, cache_time=0, private=True)

    # ─── Owner: /scan no canal (varredura manual) ───
    @bot.on(events.NewMessage(pattern=r'^/scan(?:\s|$)'))
    async def cmd_scan(event):
        if not _is_owner(event.sender_id):
            return
        if scan_mod.is_scan_running():
            await event.respond("⏳ Varredura já em andamento.")
            return
        await event.respond("🔄 Varredura manual iniciada…")
        asyncio.create_task(scan_mod.executar_varredura(user_client, bot))

    # ─── Owner: /panel ───
    @bot.on(events.NewMessage(pattern=r'^/panel(?:\s|$)'))
    async def cmd_panel(event):
        if not _is_owner(event.sender_id):
            return
        await event.respond(to_html(_painel_text()), parse_mode=HTML,
                            buttons=_painel_buttons())

    # ─── Owner: /hide /show <campo> ───
    @bot.on(events.NewMessage(pattern=r'^/(hide|show)\s+(\w+)$'))
    async def cmd_hideshow(event):
        if not _is_owner(event.sender_id):
            return
        acao, campo = event.pattern_match.group(1), event.pattern_match.group(2)
        if campo not in TOGGLEABLE_FIELDS:
            await event.respond(f"❌ Campo inválido. Use: {', '.join(TOGGLEABLE_FIELDS)}")
            return
        s = carregar_settings()
        s["hidden_global"][campo] = (acao == "hide")
        salvar_settings(s)
        await event.respond(f"✅ `{campo}` agora está "
                            f"{'🚫 oculto' if acao=='hide' else '✅ visível'}.",
                            parse_mode=HTML)

    # ─── Owner: /auth <id|@user> — autoriza ver telefone via inline ───
    @bot.on(events.NewMessage(pattern=r'^/auth(?:\s+(\S+))?$'))
    async def cmd_auth(event):
        if not _is_owner(event.sender_id):
            return
        alvo = event.pattern_match.group(1)
        if not alvo:
            await event.respond("Uso: `/auth <id|@username>`", parse_mode=HTML)
            return
        uid = await _resolver_uid_alvo(user_client, alvo)
        if uid is None:
            await event.respond(f"❌ Não consegui resolver `{alvo}`.", parse_mode=HTML)
            return
        novo = autorizar_phone(uid)
        await event.respond(
            f"✅ `{uid}` {'autorizado a ver telefone' if novo else 'já estava autorizado'}.",
            parse_mode=HTML,
        )

    # ─── Owner: /unauth <id|@user> ───
    @bot.on(events.NewMessage(pattern=r'^/unauth(?:\s+(\S+))?$'))
    async def cmd_unauth(event):
        if not _is_owner(event.sender_id):
            return
        alvo = event.pattern_match.group(1)
        if not alvo:
            await event.respond("Uso: `/unauth <id|@username>`", parse_mode=HTML)
            return
        uid = await _resolver_uid_alvo(user_client, alvo)
        if uid is None:
            await event.respond(f"❌ Não consegui resolver `{alvo}`.", parse_mode=HTML)
            return
        ok = desautorizar_phone(uid)
        await event.respond(
            f"{'🗑 Removido' if ok else 'ℹ️ Não estava na lista'}: `{uid}`",
            parse_mode=HTML,
        )

    # ─── Owner: /auths — lista autorizados ───
    @bot.on(events.NewMessage(pattern=r'^/auths(?:\s|$)'))
    async def cmd_auths(event):
        if not _is_owner(event.sender_id):
            return
        lst = listar_phone_auth()
        if not lst:
            await event.respond("📋 Nenhum usuário autorizado a ver telefone.")
            return
        body = "\n".join(f"• `{x}`" for x in lst)
        await event.respond(to_html(
            f"📋 *Autorizados a ver telefone* ({len(lst)}):\n{body}"
        ), parse_mode=HTML)

    # ─── Callback: togg_<campo> ───
    @bot.on(events.CallbackQuery(pattern=rb"^togg_(\w+)$"))
    async def cb_togg(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        campo = event.pattern_match.group(1).decode()
        if campo not in TOGGLEABLE_FIELDS:
            await event.answer("Campo inválido.", alert=True); return
        novo = toggle_field_hidden(campo)
        await event.answer(f"{campo}: {'oculto' if novo else 'visível'}")
        try:
            await event.edit(to_html(_painel_text()), parse_mode=HTML,
                             buttons=_painel_buttons())
        except Exception:
            pass

    # ─── Callback: mng_<uid> ───
    @bot.on(events.CallbackQuery(pattern=rb"^mng_(\d+)$"))
    async def cb_mng(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        await event.respond(to_html(_painel_text()), parse_mode=HTML,
                            buttons=_painel_buttons())
        await event.answer()

    # ─── Callback: del_<uid> ───
    @bot.on(events.CallbackQuery(pattern=rb"^del_(\d+)$"))
    async def cb_del(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        msg_id = get_card_msg_id(uid)
        if msg_id:
            try:
                await bot.delete_messages(NOTIFY_CHANNEL_ID, msg_id)
            except Exception as e:
                log(f"del card {uid}: {e}")
        del_card_msg_id(uid)
        await event.answer("Card removido.")

    # ─── Callback: rmcard_<uid>_<req_id> ───
    @bot.on(events.CallbackQuery(pattern=rb"^rmcard_(\d+)_(\d+)$"))
    async def cb_rmcard(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        req = int(event.pattern_match.group(2).decode())
        msg_id = get_card_msg_id(uid)
        if msg_id:
            try:
                await bot.delete_messages(NOTIFY_CHANNEL_ID, msg_id)
            except Exception as e:
                log(f"rm card: {e}")
        del_card_msg_id(uid)
        db = carregar_dados()
        db.pop(uid, None)
        salvar_dados(db)
        try:
            await bot.send_message(req, to_html(
                "✅ Seus dados foram removidos do canal."), parse_mode=HTML)
        except Exception:
            pass
        await event.edit("✅ Removido e usuário avisado.")

    @bot.on(events.CallbackQuery(pattern=rb"^rmdeny_(\d+)$"))
    async def cb_rmdeny(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        req = int(event.pattern_match.group(1).decode())
        try:
            await bot.send_message(req, to_html(
                "❌ Pedido de remoção negado pelo dono."), parse_mode=HTML)
        except Exception:
            pass
        await event.edit("❌ Pedido negado.")
