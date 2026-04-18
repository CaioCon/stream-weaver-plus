# ══════════════════════════════════════════════
# 🎮  HANDLERS — User Info Bot PRO v8.1
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
Eventos cobertos:
  • /start em DM (curto, instruções).
  • /remover em DM = pedido de remoção dos dados → notifica owner.
  • InlineQuery: @InforUser_Bot @username  |  @InforUser_Bot 123456789
       → mostra DADOS COMPLETOS (Nome, ID, Username, Bio, Grupos, Histórico).
       → 📱 Telefone APENAS se o solicitante estiver autorizado pelo dono.
  • Em DM o bot NÃO faz consulta de dados (somente o owner administra).
  • Comandos do owner no GRUPO de notificação ou em DM:
       /scan            força varredura imediata
       /panel           painel de toggles globais
       /show <campo>    /hide <campo>   atalhos
       /auth <id|@user> autoriza usuário a ver telefone via inline
       /unauth <id|@user>
       /auths           lista autorizados
  • Comandos do owner em DM (gerenciamento das mensagens):
       /cards           lista paginada com TODOS os cards do grupo
                        cada card → editar caption / apagar / republicar
  • Callbacks:
       mng_<uid>             abre painel de toggles globais
       togg_<campo>          alterna oculto/visível
       del_<uid>             apaga o card no grupo + remove do índice
       cards_page_<n>        paginação da lista de cards (DM owner)
       card_view_<uid>       abre painel de gerenciamento de UM card (DM)
       card_edit_<uid>       solicita nova caption (DM)
       card_repub_<uid>      reposta o card (apaga e reenvia)
       card_del_<uid>        apaga o card pelo painel de gerenciamento (DM)
       rmcard_<uid>_<rid> / rmdeny_<rid>  pedidos de remoção do usuário
"""

import asyncio
from telethon import events, Button

from config import (OWNER_ID, BOT_USERNAME, NOTIFY_CHANNEL_ID,
                    NOTIFY_CHANNEL_LINK, ITEMS_PER_PAGE,
                    INLINE_USERNAME_RE, INLINE_ID_RE, TOGGLEABLE_FIELDS)
from db import (carregar_dados, salvar_dados, log,
                carregar_cards, get_card_msg_id, set_card_msg_id, del_card_msg_id,
                carregar_settings, toggle_field_hidden, is_field_hidden,
                upsert_user, salvar_settings, iter_usuarios,
                is_phone_authorized, autorizar_phone, desautorizar_phone,
                listar_phone_auth)
from format import to_html, HTML
from profile import montar_card
from search import buscar_com_lookup
from notifier import enviar_ou_editar_card, avisar_owner_remocao
import scan as scan_mod


# Estado em memória — owner em DM aguardando entrada de texto p/ editar caption
# {owner_id: {"action": "edit_caption", "uid": "<uid>"}}
_pending_dm = {}


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
    rows.append([Button.url("📺 Abrir grupo", NOTIFY_CHANNEL_LINK)])
    return rows


def _painel_text() -> str:
    s = carregar_settings()["hidden_global"]
    linhas = ["⚙️ *PAINEL DE GERENCIAMENTO*",
              "━━━━━━━━━━━━━━━━━━━━",
              "Marque qual campo deve ficar *oculto* nos cards do grupo.",
              ""]
    for f in TOGGLEABLE_FIELDS:
        st = "🚫 oculto" if s.get(f) else "✅ visível"
        linhas.append(f"• `{f}` — {st}")
    return "\n".join(linhas)


def _montar_card_inline(uid: str, ent: dict, *, viewer_uid: int) -> str:
    """Caption COMPLETA para inline (telefone restrito a autorizados)."""
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
    alvo = alvo.strip().lstrip("@")
    if alvo.isdigit():
        return int(alvo)
    try:
        ent = await user_client.get_entity(alvo)
        return int(ent.id)
    except Exception as e:
        log(f"resolver alvo '{alvo}': {e}")
        return None


# ── Paginação dos cards do grupo (DM owner) ──
def _listar_cards_publicados() -> list:
    """Retorna lista de tuplas (uid, msg_id, label) ordenada por nome."""
    idx  = carregar_cards()
    db   = carregar_dados()
    out  = []
    for uid, msg_id in idx.items():
        ent  = db.get(uid, {})
        nome = ent.get("nome_atual") or "?"
        user = ent.get("username_atual") or ""
        label = f"{nome} | @{user}" if user else f"{nome} | {uid}"
        out.append((uid, msg_id, label))
    out.sort(key=lambda x: x[2].lower())
    return out


def _cards_page(page: int):
    """Monta texto+botões da página `page` da lista de cards."""
    cards       = _listar_cards_publicados()
    total       = len(cards)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    inicio      = page * ITEMS_PER_PAGE
    chunk       = cards[inicio:inicio + ITEMS_PER_PAGE]

    txt = (f"🗂 *CARDS PUBLICADOS NO GRUPO*\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"Total: *{total}*  •  Página *{page+1}/{total_pages}*\n\n"
           "Toque em um card para gerenciar (editar / apagar).")
    btns = []
    for uid, msg_id, label in chunk:
        btns.append([Button.inline(f"👤 {label[:48]}",
                                   f"card_view_{uid}".encode())])
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"cards_page_{page-1}".encode()))
    nav.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"cards_page_{page+1}".encode()))
    if len(nav) > 1:
        btns.append(nav)
    btns.append([Button.url("📺 Abrir grupo", NOTIFY_CHANNEL_LINK)])
    return txt, btns


def _card_manage_buttons(uid: str):
    return [
        [Button.inline("✏️ Editar legenda", f"card_edit_{uid}".encode())],
        [Button.inline("♻️ Republicar card", f"card_repub_{uid}".encode())],
        [Button.inline("🗑 Apagar card",     f"card_del_{uid}".encode())],
        [Button.inline("⬅️ Voltar à lista",  b"cards_page_0")],
    ]


def _card_manage_text(uid: str) -> str:
    db   = carregar_dados()
    ent  = db.get(uid, {})
    nome = ent.get("nome_atual") or "?"
    user = ent.get("username_atual") or ""
    msg  = get_card_msg_id(uid)
    return ("🛠 *GERENCIAR CARD*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📛 *Nome*: {nome}\n"
            f"🆔 *ID*: `{uid}`\n"
            f"🔗 *Username*: {('@'+user) if user else '_(nenhum)_'}\n"
            f"💬 *msg_id no grupo*: `{msg}`\n\n"
            "Escolha uma ação:")


# ────────────────────────────────────────────────────────────
def register_handlers(bot, user_client):

    # ─── /start em DM ───
    @bot.on(events.NewMessage(pattern=r'^/start(?:\s|$)', func=lambda e: e.is_private))
    async def cmd_start(event):
        is_own = _is_owner(event.sender_id)
        if is_own:
            txt = (
                "👋 *User Info Bot PRO v8.1 — modo dono*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Comandos disponíveis aqui no DM:\n"
                "• `/cards` — lista paginada dos cards publicados\n"
                "• `/scan` — varredura imediata\n"
                "• `/panel` — painel de campos ocultos\n"
                "• `/auth <id|@user>` — libera telefone\n"
                "• `/unauth <id|@user>` — revoga\n"
                "• `/auths` — lista autorizados\n\n"
                f"📺 Grupo de notificação: {NOTIFY_CHANNEL_LINK}"
            )
        else:
            txt = (
                "👋 *User Info Bot PRO v8.1*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
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
        if _is_owner(event.sender_id):
            return
        sender = await event.get_sender()
        uid_alvo = event.pattern_match.group(1) or str(sender.id)
        await avisar_owner_remocao(bot, sender, uid_alvo)
        await event.respond(to_html(
            "✅ *Pedido enviado ao dono.*\n"
            "Você será notificado se o card for removido."
        ), parse_mode=HTML)

    # ─── Texto livre em DM ───
    @bot.on(events.NewMessage(func=lambda e: e.is_private and
                              not (e.text or '').startswith('/')))
    async def dm_text(event):
        # Owner pode estar no fluxo de edição de caption
        if event.sender_id == OWNER_ID:
            st = _pending_dm.get(OWNER_ID)
            if st and st.get("action") == "edit_caption":
                uid    = st["uid"]
                msg_id = get_card_msg_id(uid)
                if not msg_id:
                    _pending_dm.pop(OWNER_ID, None)
                    await event.respond("❌ Card não encontrado mais.")
                    return
                nova = event.text or ""
                try:
                    await bot.edit_message(NOTIFY_CHANNEL_ID, msg_id,
                                            to_html(nova), parse_mode=HTML)
                    await event.respond("✅ Legenda atualizada no grupo.")
                except Exception as e:
                    await event.respond(f"❌ Falha ao editar: `{e}`",
                                        parse_mode=HTML)
                _pending_dm.pop(OWNER_ID, None)
                return
            return  # owner conversa livremente
        await event.respond(to_html(
            "🚫 *Eu não realizo consultas por DM.*\n\n"
            f"🔎 Use o modo inline em qualquer chat:\n"
            f"`@{BOT_USERNAME} @username` ou `@{BOT_USERNAME} 1234567890`\n\n"
            "🗑 Para pedir remoção dos seus dados envie `/remover`."
        ), parse_mode=HTML)

    # ─── Inline query ───
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
            asyncio.create_task(enviar_ou_editar_card(
                bot, uid, ent, photo_bytes=ent.pop("_photo_bytes", None),
            ))

        if not articles:
            await event.answer([], switch_pm="Usuário não encontrado",
                                switch_pm_param="start")
            return
        await event.answer(articles, cache_time=0, private=True)

    # ─── Owner: /scan ───
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

    # ─── Owner: /cards (paginado, em DM) ───
    @bot.on(events.NewMessage(pattern=r'^/cards(?:\s|$)'))
    async def cmd_cards(event):
        if not _is_owner(event.sender_id):
            return
        txt, btns = _cards_page(0)
        await event.respond(to_html(txt), parse_mode=HTML, buttons=btns)

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

    # ─── Owner: /auth ───
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

    # ─── Callback: noop (ignora) ───
    @bot.on(events.CallbackQuery(pattern=rb"^noop$"))
    async def cb_noop(event):
        await event.answer()

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

    # ─── Callback: del_<uid> (botão abaixo do card no grupo) ───
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

    # ─── Callbacks de paginação/gerenciamento (DM owner) ───
    @bot.on(events.CallbackQuery(pattern=rb"^cards_page_(\d+)$"))
    async def cb_cards_page(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        page = int(event.pattern_match.group(1).decode())
        txt, btns = _cards_page(page)
        try:
            await event.edit(to_html(txt), parse_mode=HTML, buttons=btns)
        except Exception:
            await event.respond(to_html(txt), parse_mode=HTML, buttons=btns)
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"^card_view_(\d+)$"))
    async def cb_card_view(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        try:
            await event.edit(to_html(_card_manage_text(uid)), parse_mode=HTML,
                             buttons=_card_manage_buttons(uid))
        except Exception:
            await event.respond(to_html(_card_manage_text(uid)), parse_mode=HTML,
                                buttons=_card_manage_buttons(uid))
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"^card_edit_(\d+)$"))
    async def cb_card_edit(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        _pending_dm[OWNER_ID] = {"action": "edit_caption", "uid": uid}
        await event.answer()
        await event.respond(to_html(
            f"✏️ *Edição de legenda* — card `{uid}`\n\n"
            "Envie agora a *nova legenda* (Markdown leve suportado).\n"
            "Para cancelar, envie `/cancel`."
        ), parse_mode=HTML)

    @bot.on(events.NewMessage(pattern=r'^/cancel$', func=lambda e: e.is_private))
    async def cmd_cancel(event):
        if event.sender_id != OWNER_ID:
            return
        if _pending_dm.pop(OWNER_ID, None):
            await event.respond("✋ Edição cancelada.")

    @bot.on(events.CallbackQuery(pattern=rb"^card_repub_(\d+)$"))
    async def cb_card_repub(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        msg_id = get_card_msg_id(uid)
        if msg_id:
            try:
                await bot.delete_messages(NOTIFY_CHANNEL_ID, msg_id)
            except Exception:
                pass
            del_card_msg_id(uid)
        db = carregar_dados()
        ent = db.get(uid)
        if not ent:
            await event.answer("Usuário não está no banco.", alert=True); return
        await enviar_ou_editar_card(bot, uid, ent)
        await event.answer("♻️ Card republicado.")

    @bot.on(events.CallbackQuery(pattern=rb"^card_del_(\d+)$"))
    async def cb_card_del(event):
        if not _is_owner(event.sender_id):
            await event.answer("Apenas o dono.", alert=True); return
        uid = event.pattern_match.group(1).decode()
        msg_id = get_card_msg_id(uid)
        if msg_id:
            try:
                await bot.delete_messages(NOTIFY_CHANNEL_ID, msg_id)
            except Exception as e:
                log(f"card_del {uid}: {e}")
        del_card_msg_id(uid)
        await event.answer("🗑 Card apagado.")
        txt, btns = _cards_page(0)
        try:
            await event.edit(to_html(txt), parse_mode=HTML, buttons=btns)
        except Exception:
            pass

    # ─── Pedido de remoção (usuário) ───
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
                "✅ Seus dados foram removidos do grupo."), parse_mode=HTML)
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
