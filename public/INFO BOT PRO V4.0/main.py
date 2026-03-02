# ══════════════════════════════════════════════
# 🚀  INFO BOT PRO V4.0 — MAIN
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
#
# Arquitetura Dual: UserBot + Bot (preservada do EuBot3.py)
# UserBot = conta pessoal (responde replies em grupos)
# Bot = @InforUser_Bot (inline, DM, gestão)
#
# SEM MIGRADOR — Foco em consulta IPTV + CPF +
# sistema de créditos + AutoMs + grupos permitidos
#
# Estrutura modular:
#   main.py        → Bot + UserBot principal
#   grupo.py       → Funções de grupos e varredura
#   consulta.py    → Consulta IPTV + CPF
#   creditos.py    → Sistema de créditos
#   automs.py      → Mensagens automáticas
#   pagina.py      → Paginação
#   botoes.py      → Botões inline
#   aplicativo.py  → API_ID, API_HASH, PHONE
#   token.json     → Token do bot
#
# ══════════════════════════════════════════════

import os
import re
import json
import math
import hashlib
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest

# ── Módulos locais ──
from aplicativo import API_ID, API_HASH, PHONE
from grupo import (
    carregar_dados, salvar_dados, carregar_grupos_db, salvar_grupos_db,
    log, garantir_campos, registrar_interacao,
    consultar_telegram_api, verificar_status_em_grupos,
    buscar_usuario, formatar_perfil, formatar_perfil_api,
    executar_varredura, executar_threads_atualizacao, auto_scanner,
    set_clients, scan_running, scan_stats, thread_scan_active,
    FILE_PATH, GROUPS_DB_PATH, SCAN_INTERVAL, THREAD_SCAN_INTERVAL,
    MAX_HISTORY, BOT_VERSION
)
from botoes import (
    menu_principal_buttons, voltar_button, perfil_buttons,
    perfil_com_api_buttons, resultado_multiplo_buttons,
    set_owner, is_admin
)
from pagina import paginar_buttons, paginar_lista, ITEMS_PER_PAGE
from consulta import (
    check_url, URL_PATTERN, validar_cpf, formatar_cpf,
    detectar_tipo_entrada
)
from creditos import (
    registrar_usuario as registrar_usuario_creditos,
    obter_saldo, tem_creditos, consumir_credito, adicionar_creditos,
    formatar_saldo, formatar_sem_creditos, obter_info_usuarios,
    buscar_usuario_por_username, buscar_usuario_por_id
)
from automs import (
    load_automs, save_automs, add_autom, remove_autom,
    editar_autom, toggle_autom, obter_automs_ativas,
    build_automs_page
)

# ── Configurações ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
GRUPOS_PERMITIDOS_FILE = os.path.join(BASE_DIR, "grupos_permitidos.json")
SESSION_USER = os.path.join(BASE_DIR, "session_userbot")
SESSION_BOT = os.path.join(BASE_DIR, "session_bot")

BOT_CODENAME = "773H Ultra"
OWNER_ID = 2061557102
OWNER_CONTACT = "@Edkd1"
CANAL_RESULTADOS_ID = 0  # 0 = desativado, configure se necessário


def carregar_token() -> str:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("bot_token", "")
        except (json.JSONDecodeError, IOError):
            pass
    return ""


BOT_TOKEN = carregar_token()

if not BOT_TOKEN:
    print("❌ Token não encontrado! Configure token.json")
    exit(1)

if not API_ID or not API_HASH or not PHONE:
    print("❌ Credenciais API não configuradas! Configure aplicativo.py")
    exit(1)

# ── Clientes Telethon (PRESERVADO do EuBot3.py) ──
userbot = TelegramClient(SESSION_USER, API_ID, API_HASH)
bot = TelegramClient(SESSION_BOT, API_ID, API_HASH)

# Configurar módulos
set_owner(OWNER_ID)
set_clients(bot, OWNER_ID)

# ── Estados ──
search_pending = {}
tg_search_pending = {}
creditos_pending = {}  # {chat_id: "aguardando_id_ou_username"}


# ══════════════════════════════════════════════
# 📋  GESTÃO DE GRUPOS PERMITIDOS (PRESERVADO)
# ══════════════════════════════════════════════

def load_groups() -> list:
    """Carrega grupos permitidos para consulta."""
    if not os.path.exists(GRUPOS_PERMITIDOS_FILE):
        save_groups([])
        return []
    try:
        with open(GRUPOS_PERMITIDOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_groups(groups: list):
    try:
        with open(GRUPOS_PERMITIDOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(groups, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


def is_group_allowed(chat_id: int) -> bool:
    groups = load_groups()
    return any(g["id"] == chat_id for g in groups)


def add_group(chat_id: int, name: str) -> bool:
    groups = load_groups()
    if any(g["id"] == chat_id for g in groups):
        return False
    groups.append({"id": chat_id, "name": name, "adicionado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
    save_groups(groups)
    return True


def remove_group(chat_id: int) -> bool:
    groups = load_groups()
    new_groups = [g for g in groups if g["id"] != chat_id]
    if len(new_groups) == len(groups):
        return False
    save_groups(new_groups)
    return True


def build_groups_page(page: int = 0):
    """Constrói página de grupos com botões inline. (PRESERVADO)"""
    groups = load_groups()
    total = len(groups)
    total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_groups = groups[start:end]

    text = (
        f"╔══════════════════════════════╗\n"
        f"║  📋 GRUPOS PERMITIDOS          ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"📊 **Total:** `{total}` grupo(s)\n"
        f"📄 **Página:** `{page + 1}/{total_pages}`\n\n"
    )

    if not page_groups:
        text += "📭 Nenhum grupo cadastrado.\n"
    else:
        for i, g in enumerate(page_groups, start=start + 1):
            text += f"**{i}.** `{g['id']}` — {g['name']}\n"

    text += f"\n╚══════════════════════════════╝"

    buttons = []
    for g in page_groups:
        buttons.append([Button.inline(f"🗑 Remover: {g['name'][:20]}", data=f"rmgrp:{g['id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("◀️ Voltar", data=f"grppage:{page - 1}"))
    nav_row.append(Button.inline(f"📄 {page + 1}/{total_pages}", data="noop"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("Avançar ▶️", data=f"grppage:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        Button.inline("➕ Adicionar Grupo", data="addgrp"),
        Button.inline("🔄 Atualizar", data="grppage:0")
    ])

    return text, buttons


# ══════════════════════════════════════════════
# 🤖  BOT — HANDLERS DE COMANDO
# ══════════════════════════════════════════════

@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    await registrar_interacao(event)
    sender = await event.get_sender()
    uid = sender.id if sender else 0
    nome = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Sem nome"
    username_tg = f"@{sender.username}" if sender.username else "Nenhum"

    # Registrar no sistema de créditos
    is_novo = registrar_usuario_creditos(uid, nome, username_tg)
    saldo = obter_saldo(uid)

    db = carregar_dados()
    user_info = ""
    uid_str = str(uid)
    if uid_str in db:
        d = db[uid_str]
        user_info = f"""
━━━━━━━━━━━━━━━━━━━━━
📌 **Seu Perfil no Sistema:**
├ 👤 `{d.get('nome_atual', 'N/A')}`
├ 📂 Grupos: **{len(d.get('grupos', []))}** | 👑 Admin: **{len(d.get('grupos_admin', []))}**
├ 📝 Alterações: **{len(d.get('historico', []))}**
└ 💰 Créditos: **{saldo}**"""

    novo_text = "\n\n🎉 **Bem-vindo!** Você recebeu **10 créditos** iniciais!" if is_novo else ""

    await event.respond(
        f"""╔══════════════════════════════════╗
║  🕵️ **Info Bot Pro v{BOT_VERSION}**          ║
║  _{BOT_CODENAME}_                     ║
╚══════════════════════════════════╝

🔍 **Busque** por ID, @username ou nome
🌐 **Consulte** URLs IPTV inline ou no privado
📄 **CPF** — Consulta de CPF
📊 **Monitore** alterações em tempo real
💰 **Créditos** — Sistema de créditos por consulta
💬 **AutoMs** — Respostas automáticas em DMs
{user_info}{novo_text}

━━━━━━━━━━━━━━━━━━━━━
👨‍💻 _Créditos: Edivaldo Silva {OWNER_CONTACT}_
⚡ _Powered by {BOT_CODENAME}_
━━━━━━━━━━━━━━━━━━━━━""",
        parse_mode='md', buttons=menu_principal_buttons(uid))


@bot.on(events.NewMessage(pattern='/menu'))
async def cmd_menu_msg(event):
    await registrar_interacao(event)
    await cmd_start(event)


@bot.on(events.NewMessage(pattern='/id'))
async def cmd_get_id(event):
    await registrar_interacao(event)
    chat = await event.get_chat()
    sender = await event.get_sender()
    chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'N/A')
    await event.reply(
        f"🆔 **Chat:** `{event.chat_id}`\n"
        f"📋 **Nome:** {chat_name}\n"
        f"👤 **Seu ID:** `{sender.id if sender else 'N/A'}`",
        parse_mode='md'
    )


@bot.on(events.NewMessage(pattern='/help'))
async def cmd_help(event):
    await registrar_interacao(event)
    is_owner = (event.sender_id == OWNER_ID)

    text = (
        "╔══════════════════════════════╗\n"
        "║  📖 COMANDOS DO BOT           ║\n"
        "╚══════════════════════════════╝\n\n"
        "🔹 `/start` — Menu inicial\n"
        "🔹 `/help` — Esta mensagem\n"
        "🔹 `/creditos` — Ver seus créditos\n"
        "🔹 Envie uma **URL IPTV** no privado para consultar\n"
        "🔹 Use **Inline:** `@InforUser_Bot URL`\n"
    )

    if is_owner:
        text += (
            "\n"
            "👑 **COMANDOS DO DONO:**\n"
            "🔹 `/grupos` — Painel de gestão de grupos\n"
            "🔹 `/addgrupo <id>` — Adicionar grupo por ID\n"
            "🔹 `/status` — Status do sistema\n"
            "🔹 `/automs` — Gerenciar mensagens automáticas\n"
            "🔹 `/addautom Título | Mensagem` — Adicionar autom\n"
            "🔹 `/addcreditos` — Adicionar créditos a um usuário\n"
        )

    text += "\n╚══════════════════════════════╝"
    await event.reply(text, parse_mode='md')


@bot.on(events.NewMessage(pattern='/creditos'))
async def cmd_creditos(event):
    await registrar_interacao(event)
    sender = await event.get_sender()
    nome = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Sem nome"
    registrar_usuario_creditos(sender.id, nome,
                               f"@{sender.username}" if sender.username else "Nenhum")
    await event.reply(
        formatar_saldo(sender.id, nome),
        parse_mode='md', buttons=voltar_button()
    )


@bot.on(events.NewMessage(pattern=r'/buscar\s+(.+)'))
async def cmd_buscar_text(event):
    await registrar_interacao(event)
    query = event.pattern_match.group(1).strip()

    results = buscar_usuario(query)

    if not results:
        await event.reply("🔎 _Não encontrado no banco. Consultando API..._", parse_mode='md')
        dados_api = await consultar_telegram_api(userbot, query)
        if dados_api:
            uid = str(dados_api["id"])
            db = carregar_dados()
            if uid in db:
                status = await verificar_status_em_grupos(userbot, dados_api["id"])
                db[uid]["grupos_admin"] = [{"grupo": g["grupo"], "cargo": g["cargo"]} for g in status["admin_em"]]
                db[uid]["grupos_banido"] = [{"grupo": g["grupo"]} for g in status["banido_de"]]
                salvar_dados(db)
                await event.reply(
                    formatar_perfil(db[uid]), parse_mode='md',
                    buttons=perfil_com_api_buttons(uid)
                )
            else:
                await event.reply(
                    formatar_perfil_api(dados_api), parse_mode='md',
                    buttons=voltar_button()
                )
            return
        await event.reply(
            "❌ **Nenhum usuário encontrado.**\n💡 Tente ID, @username ou nome.",
            parse_mode='md', buttons=voltar_button()
        )
        return

    if len(results) == 1:
        uid = str(results[0]["id"])
        await event.reply(
            formatar_perfil(results[0]), parse_mode='md',
            buttons=perfil_buttons(uid)
        )
    else:
        text = f"🔍 **{len(results)} resultados para** `{query}`:\n\n"
        await event.reply(text, parse_mode='md', buttons=resultado_multiplo_buttons(results))


# ── Gestão de grupos via bot ──

@bot.on(events.NewMessage(pattern=r'^/grupos$'))
async def bot_grupos(event):
    if event.sender_id != OWNER_ID:
        await event.reply("⛔ Apenas o dono pode gerenciar grupos.")
        return
    text, buttons = build_groups_page(0)
    await event.reply(text, buttons=buttons, parse_mode='md')


@bot.on(events.NewMessage(pattern=r'^/addgrupo\s+(-?\d+)(?:\s+(.+))?$'))
async def bot_add_group(event):
    if event.sender_id != OWNER_ID:
        return
    gid = int(event.pattern_match.group(1))
    name = event.pattern_match.group(2)

    # Se nome não foi fornecido, tenta resolver automaticamente
    if not name:
        try:
            entity = await bot.get_entity(gid)
            name = getattr(entity, 'title', None) or getattr(entity, 'first_name', f"Grupo {gid}")
        except Exception:
            name = f"Grupo {gid}"
    name = name.strip()

    added = add_group(gid, name)
    if added:
        await event.reply(
            f"✅ **Grupo adicionado!**\n"
            f"📋 **Nome:** {name}\n"
            f"🆔 **ID:** `{gid}`\n\n"
            f"Todos os membros agora podem consultar URLs.\nUse /grupos para ver a lista.",
            parse_mode='md'
        )
    else:
        await event.reply(f"⚠️ Grupo `{gid}` já está cadastrado.", parse_mode='md')


@bot.on(events.NewMessage(pattern=r'^/status$'))
async def bot_status(event):
    if event.sender_id != OWNER_ID:
        return
    groups = load_groups()
    automs = load_automs()
    info_cred = obter_info_usuarios()
    db = carregar_dados()

    await event.reply(
        f"╔══════════════════════════════╗\n"
        f"║  📊 STATUS DO SISTEMA          ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"✅ **Bot + UserBot Online**\n"
        f"📋 **Grupos permitidos:** `{len(groups)}`\n"
        f"💬 **AutoMs:** `{len(automs)}`\n"
        f"👥 **Usuários registrados:** `{info_cred['total_usuarios']}`\n"
        f"💰 **Créditos em circulação:** `{info_cred['total_creditos']}`\n"
        f"📤 **Consultas realizadas:** `{info_cred['total_consumidos']}`\n"
        f"📦 **Banco de dados:** `{len(db)}` registros\n"
        f"🕐 `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`\n\n"
        f"╚══════════════════════════════╝",
        parse_mode='md'
    )


# ── AutoMs via bot ──

@bot.on(events.NewMessage(pattern=r'^/automs$'))
async def bot_automs(event):
    if event.sender_id != OWNER_ID:
        return
    text, buttons = build_automs_page(0)
    await event.reply(text, buttons=buttons, parse_mode='md')


@bot.on(events.NewMessage(pattern=r'^/addautom\s+(.+)$'))
async def bot_add_autom(event):
    if event.sender_id != OWNER_ID:
        return
    text = event.pattern_match.group(1).strip()
    if '|' not in text:
        await event.reply(
            "❌ **Formato inválido!**\n\n"
            "Use: `/addautom Título | Mensagem completa`",
            parse_mode='md'
        )
        return

    parts = text.split('|', 1)
    title = parts[0].strip()
    message = parts[1].strip()

    if not title or not message:
        await event.reply("❌ Título e mensagem não podem estar vazios.", parse_mode='md')
        return

    count = add_autom(title, message)
    await event.reply(
        f"✅ **AutoM adicionada!**\n\n"
        f"📌 **Título:** {title}\n"
        f"💬 **Preview:** {message[:80]}{'...' if len(message) > 80 else ''}\n"
        f"📊 **Total:** `{count}` mensagem(ns)\n\n"
        f"Use /automs para gerenciar.",
        parse_mode='md'
    )


# ── Créditos — Dono adiciona via /addcreditos ──

@bot.on(events.NewMessage(pattern=r'^/addcreditos$'))
async def cmd_addcreditos(event):
    if event.sender_id != OWNER_ID:
        return
    creditos_pending[event.chat_id] = "aguardando"
    await event.reply(
        "╔══════════════════════════════╗\n"
        "║  💰 ADICIONAR CRÉDITOS         ║\n"
        "╚══════════════════════════════╝\n\n"
        "Envie de uma das formas:\n\n"
        "• **@username** do usuário\n"
        "• **ID numérico** do usuário\n"
        "• **Encaminhe** uma mensagem do usuário\n\n"
        "💡 _Depois enviarei a quantidade de créditos._\n\n"
        "╚══════════════════════════════╝",
        parse_mode='md', buttons=voltar_button()
    )


# ══════════════════════════════════════════════
# 🔘  HANDLERS DE CALLBACK — BOT
# ══════════════════════════════════════════════

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    import grupo
    data = event.data.decode()
    chat_id = event.chat_id
    sender_id = event.sender_id

    try:
        message = await event.get_message()

        if data == "cmd_menu":
            await message.edit(
                f"╔══════════════════════════════════╗\n"
                f"║  🕵️ **Info Bot Pro v{BOT_VERSION}**          ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"Selecione uma opção:",
                parse_mode='md', buttons=menu_principal_buttons(sender_id)
            )

        elif data == "cmd_buscar":
            search_pending[chat_id] = True
            await message.edit(
                "🔍 **Modo de Busca Ativo**\n\n"
                "• 🔢 **ID** — ex: `123456789`\n"
                "• 🆔 **@username** — ex: `@exemplo`\n"
                "• 📛 **Nome** — ex: `João`\n\n"
                "💡 _Busca no banco local primeiro, depois API!_\n\n"
                "_Aguardando..._",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_tg_search":
            tg_search_pending[chat_id] = True
            await message.edit(
                "🌐 **Consulta Direta — API Telegram**\n\n"
                "• 🔢 **ID numérico**\n"
                "• 🆔 **@username**\n\n"
                "⚡ _Salva automaticamente no banco_\n\n"
                "_Aguardando..._",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_creditos":
            sender = await event.get_sender()
            nome = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Sem nome"
            await message.edit(
                formatar_saldo(sender_id, nome),
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_stats":
            db = carregar_dados()
            groups_db = carregar_grupos_db()
            total_users = len(db)
            total_changes = sum(len(d.get("historico", [])) for d in db.values())
            total_names = sum(1 for d in db.values() for h in d.get("historico", []) if h["tipo"] == "NOME")
            total_usernames = sum(1 for d in db.values() for h in d.get("historico", []) if h["tipo"] == "USER")
            with_history = sum(1 for d in db.values() if d.get("historico"))
            total_admins = sum(1 for d in db.values() if d.get("grupos_admin"))
            total_bans = sum(len(d.get("grupos_banido", [])) for d in db.values())
            total_groups_db = len(groups_db)
            info_cred = obter_info_usuarios()
            last = grupo.scan_stats.get("last_scan", "Nunca")

            await message.edit(
                f"╔══════════════════════════╗\n"
                f"║  📊 **ESTATÍSTICAS**       ║\n"
                f"╚══════════════════════════╝\n\n"
                f"👥 **Banco:** **{total_users}** usuários | **{total_groups_db}** grupos\n"
                f"├ 🔔 Alterações: **{total_changes}** (📛 {total_names} | 🆔 {total_usernames})\n"
                f"├ 👑 Admins: **{total_admins}** | 🚫 Bans: **{total_bans}**\n"
                f"└ 📊 Com hist: **{with_history}**\n\n"
                f"💰 **Créditos:**\n"
                f"├ 👤 Usuários: **{info_cred['total_usuarios']}**\n"
                f"├ 💎 Em circulação: **{info_cred['total_creditos']}**\n"
                f"└ 📤 Consumidos: **{info_cred['total_consumidos']}**\n\n"
                f"⚙️ Última varredura: `{last}`\n"
                f"💾 Banco: **{os.path.getsize(FILE_PATH) // 1024 if os.path.exists(FILE_PATH) else 0} KB**",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_scan":
            if not is_admin(sender_id):
                await event.answer("🔒 Apenas o administrador.", alert=True)
                return
            if grupo.scan_running:
                await event.answer("⏳ Já em andamento!", alert=True)
            else:
                await event.answer("🔄 Varredura iniciada!")
                asyncio.create_task(executar_varredura(userbot, notify_chat=chat_id))

        elif data == "cmd_groups" or data.startswith("groups_page_"):
            if not is_admin(sender_id):
                await event.answer("🔒 Apenas o administrador.", alert=True)
                return
            page = int(data.split("_")[-1]) if data.startswith("groups_page_") else 0
            groups_db = carregar_grupos_db()
            all_groups = sorted(groups_db.values(), key=lambda x: x.get("nome", ""))
            chunk, page, total_pages = paginar_lista(all_groups, page)

            if not chunk:
                text = "📂 **Nenhum grupo registrado.**\nInicie uma varredura."
            else:
                text = f"📂 **Grupos Monitorados** (pág. {page + 1}/{total_pages})\n\n"
                for g in chunk:
                    icon = "✅" if g.get("scan_possivel") else "🔒"
                    text += f"{icon} **{g.get('nome', '?')}**\n   👥 {g.get('membros_coletados', 0)} | `{g.get('ultimo_scan', 'Nunca')}`\n\n"
            await message.edit(text, parse_mode='md', buttons=paginar_buttons("groups", page, total_pages))

        elif data == "cmd_threads":
            if not is_admin(sender_id):
                await event.answer("🔒", alert=True)
                return
            await message.edit(
                f"🧵 **Threads:** {'✅ ATIVAS' if grupo.thread_scan_active else '❌ PAUSADAS'}\n"
                f"⏱️ Intervalo: **{THREAD_SCAN_INTERVAL // 60} min**\n\n"
                f"_Varrem todos os grupos em segundo plano._",
                parse_mode='md', buttons=[
                    [Button.inline(
                        "⏸️ Pausar" if grupo.thread_scan_active else "▶️ Ativar",
                        b"toggle_threads"
                    )],
                    [Button.inline("🔙 Menu", b"cmd_menu")]
                ]
            )

        elif data == "toggle_threads":
            if not is_admin(sender_id):
                await event.answer("🔒", alert=True)
                return
            grupo.thread_scan_active = not grupo.thread_scan_active
            await event.answer(
                f"Threads {'ativadas ✅' if grupo.thread_scan_active else 'pausadas ⏸️'}!",
                alert=True
            )

        elif data == "cmd_recent" or data.startswith("recent_page_"):
            page = int(data.split("_")[-1]) if data.startswith("recent_page_") else 0
            db = carregar_dados()
            all_changes = []
            for uid, dados in db.items():
                for h in dados.get("historico", []):
                    all_changes.append({**h, "uid": uid, "nome": dados["nome_atual"]})
            all_changes.sort(key=lambda x: x["data"], reverse=True)
            chunk, page, total_pages = paginar_lista(all_changes, page)

            if not chunk:
                text = "📋 **Nenhuma alteração registrada.**"
            else:
                text = f"📋 **Últimas Alterações** (pág. {page + 1}/{total_pages})\n\n"
                for c in chunk:
                    emoji = "📛" if c["tipo"] == "NOME" else "🆔"
                    text += f"{emoji} `{c['data']}`\n   👤 {c['nome']} — {c['de']} ➜ {c['para']}\n\n"
            await message.edit(text, parse_mode='md', buttons=paginar_buttons("recent", page, total_pages))

        elif data == "cmd_export":
            if not is_admin(sender_id):
                await event.answer("🔒", alert=True)
                return
            if os.path.exists(FILE_PATH):
                await bot.send_file(
                    chat_id, FILE_PATH,
                    caption=f"📤 **Banco exportado!** 👥 {len(carregar_dados())} usuários",
                    parse_mode='md'
                )
                await event.answer("✅ Enviado!")
            else:
                await event.answer("❌ Banco vazio!", alert=True)

        elif data == "cmd_config":
            await message.edit(
                f"⚙️ **Configurações**\n\n"
                f"🔄 Varredura: **{SCAN_INTERVAL // 60} min**\n"
                f"🧵 Threads: **{THREAD_SCAN_INTERVAL // 60} min** "
                f"({'✅' if grupo.thread_scan_active else '❌'})\n"
                f"📜 Máx hist: **{MAX_HISTORY}** | 📄 Pág: **{ITEMS_PER_PAGE}**\n"
                f"💰 Créditos iniciais: **10**",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_about":
            await message.edit(
                f"╔══════════════════════════════════╗\n"
                f"║  ℹ️ **SOBRE O BOT**                ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"🕵️ **Info Bot Pro v{BOT_VERSION}** — _{BOT_CODENAME}_\n\n"
                f"• 🔍 Busca local + 🌐 API Telegram\n"
                f"• 📡 Varredura automática + 🧵 Threads\n"
                f"• 🌐 Consulta IPTV + Inline Mode\n"
                f"• 📄 Consulta de CPF\n"
                f"• 💰 Sistema de créditos\n"
                f"• 💬 Mensagens automáticas (AutoMs)\n"
                f"• 📋 Gestão de grupos permitidos\n"
                f"• 📤 Exportação de dados\n\n"
                f"⚡ Telethon asyncio | 💾 JSON persistente\n\n"
                f"👤 **Dono:** Edivaldo Silva\n"
                f"🆔 **ID:** `{OWNER_ID}`\n"
                f"👨‍💻 {OWNER_CONTACT} | v{BOT_VERSION}",
                parse_mode='md', buttons=voltar_button()
            )

        # ── Grupos permitidos — Callbacks ──

        elif data.startswith("grppage:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            page = int(data.split(":")[1])
            text, buttons = build_groups_page(page)
            await message.edit(text, buttons=buttons, parse_mode='md')

        elif data.startswith("rmgrp:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            gid = int(data.split(":")[1])
            removed = remove_group(gid)
            if removed:
                await event.answer(f"✅ Grupo {gid} removido!", alert=True)
            else:
                await event.answer(f"❌ Grupo {gid} não encontrado.", alert=True)
            text, buttons = build_groups_page(0)
            await message.edit(text, buttons=buttons, parse_mode='md')

        elif data == "addgrp":
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            await event.answer()
            await event.reply(
                "╔══════════════════════════════╗\n"
                "║  ➕ ADICIONAR GRUPO            ║\n"
                "╚══════════════════════════════╝\n\n"
                "Envie apenas o **ID do grupo**:\n"
                "`/addgrupo -100123456`\n\n"
                "💡 O nome será detectado automaticamente!\n"
                "Use `/id` dentro do grupo para descobrir o ID.",
                parse_mode='md'
            )

        # ── AutoMs — Callbacks ──

        elif data.startswith("autompage:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            page = int(data.split(":")[1])
            text, buttons = build_automs_page(page)
            await message.edit(text, buttons=buttons, parse_mode='md')

        elif data.startswith("viewautom:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            idx = int(data.split(":")[1])
            automs = load_automs()
            if 0 <= idx < len(automs):
                am = automs[idx]
                estado = "🟢 Ativa" if am.get("ativo", True) else "🔴 Inativa"
                await event.answer()
                await event.reply(
                    f"╔══════════════════════════════╗\n"
                    f"║  📌 AUTOM #{idx + 1}                 ║\n"
                    f"╚══════════════════════════════╝\n\n"
                    f"📋 **Título:** {am['title']}\n"
                    f"📊 **Estado:** {estado}\n\n"
                    f"💬 **Mensagem:**\n{am['message']}\n\n"
                    f"╚══════════════════════════════╝",
                    parse_mode='md'
                )
            else:
                await event.answer("❌ Mensagem não encontrada.", alert=True)

        elif data.startswith("toggleautom:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            idx = int(data.split(":")[1])
            novo_estado = toggle_autom(idx)
            if novo_estado is not None:
                await event.answer(
                    f"{'🟢 Ativada' if novo_estado else '🔴 Desativada'}!", alert=True
                )
                text, buttons = build_automs_page(0)
                await message.edit(text, buttons=buttons, parse_mode='md')
            else:
                await event.answer("❌ Não encontrada.", alert=True)

        elif data.startswith("rmautom:"):
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            idx = int(data.split(":")[1])
            removed = remove_autom(idx)
            if removed:
                await event.answer(f"✅ AutoM '{removed['title']}' removida!", alert=True)
            else:
                await event.answer("❌ Não encontrada.", alert=True)
            text, buttons = build_automs_page(0)
            await message.edit(text, buttons=buttons, parse_mode='md')

        elif data == "addautom_prompt":
            if sender_id != OWNER_ID:
                await event.answer("⛔ Sem permissão.", alert=True)
                return
            await event.answer()
            await event.reply(
                "╔══════════════════════════════╗\n"
                "║  ➕ ADICIONAR AUTOM            ║\n"
                "╚══════════════════════════════╝\n\n"
                "Envie no formato:\n"
                "`/addautom Título da Mensagem | Conteúdo completo`\n\n"
                "💡 Separe título e mensagem com `|`\n\n"
                "╚══════════════════════════════╝",
                parse_mode='md'
            )

        # ── Perfis — Callbacks (PRESERVADOS) ──

        elif data.startswith("profile_"):
            uid = data.replace("profile_", "")
            db = carregar_dados()
            if uid in db:
                await message.edit(
                    formatar_perfil(db[uid]), parse_mode='md',
                    buttons=perfil_buttons(uid)
                )
            else:
                await event.answer("❌ Não encontrado.")

        elif data.startswith("apilookup_"):
            uid = data.replace("apilookup_", "")
            await event.answer("🌐 Consultando...")
            dados_api = await consultar_telegram_api(userbot, uid)
            if dados_api:
                status = await verificar_status_em_grupos(userbot, int(uid))
                db = carregar_dados()
                if uid in db:
                    db[uid]["grupos_admin"] = [{"grupo": g["grupo"], "cargo": g["cargo"]} for g in status["admin_em"]]
                    db[uid]["grupos_banido"] = [{"grupo": g["grupo"]} for g in status["banido_de"]]
                    db[uid]["dados_api"] = dados_api
                    salvar_dados(db)
                await message.edit(
                    formatar_perfil_api(dados_api), parse_mode='md',
                    buttons=[
                        [Button.inline("👤 Perfil Completo", f"profile_{uid}".encode())],
                        [Button.inline("🔙 Menu", b"cmd_menu")]
                    ]
                )
            else:
                await message.edit(
                    "❌ **Não foi possível consultar.**", parse_mode='md',
                    buttons=[
                        [Button.inline("👤 Perfil Local", f"profile_{uid}".encode())],
                        [Button.inline("🔙 Menu", b"cmd_menu")]
                    ]
                )

        elif data.startswith("apiview_"):
            uid = data.replace("apiview_", "")
            db = carregar_dados()
            if uid in db and "dados_api" in db[uid]:
                await message.edit(
                    formatar_perfil_api(db[uid]["dados_api"]), parse_mode='md',
                    buttons=[
                        [Button.inline("👤 Perfil", f"profile_{uid}".encode()),
                         Button.inline("🔄 Atualizar", f"apilookup_{uid}".encode())],
                        [Button.inline("🔙 Menu", b"cmd_menu")]
                    ]
                )

        elif data.startswith("gadmin_"):
            parts = data.split("_")
            uid, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
            db = carregar_dados()
            if uid not in db:
                await event.answer("❌"); return
            lista = db[uid].get("grupos_admin", [])
            chunk, page, total_pages = paginar_lista(lista, page)
            text = f"👑 **Admin** — `{db[uid]['nome_atual']}`\nPág. {page+1}/{total_pages}\n\n"
            for g in chunk:
                e = "👑" if g.get("cargo") == "Criador" else "🛡️"
                text += f"{e} **{g.get('grupo', '?')}** — _{g.get('cargo', 'Admin')}_\n"
            if not chunk: text += "_Nenhum._"
            btns = paginar_buttons(f"gadmin_{uid}", page, total_pages)
            btns.insert(0, [Button.inline("👤 Perfil", f"profile_{uid}".encode())])
            await message.edit(text, parse_mode='md', buttons=btns)

        elif data.startswith("gban_"):
            parts = data.split("_")
            uid, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
            db = carregar_dados()
            if uid not in db:
                await event.answer("❌"); return
            lista = db[uid].get("grupos_banido", [])
            chunk, page, total_pages = paginar_lista(lista, page)
            text = f"🚫 **Bans** — `{db[uid]['nome_atual']}`\nPág. {page+1}/{total_pages}\n\n"
            for g in chunk:
                text += f"🚫 **{g.get('grupo', '?')}**\n"
            if not chunk: text += "_Nenhum ban._"
            btns = paginar_buttons(f"gban_{uid}", page, total_pages)
            btns.insert(0, [Button.inline("👤 Perfil", f"profile_{uid}".encode())])
            await message.edit(text, parse_mode='md', buttons=btns)

        elif data.startswith("gmember_"):
            parts = data.split("_")
            uid, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
            db = carregar_dados()
            if uid not in db:
                await event.answer("❌"); return
            lista = db[uid].get("grupos", [])
            chunk, page, total_pages = paginar_lista(lista, page)
            text = f"📂 **Grupos** — `{db[uid]['nome_atual']}`\nPág. {page+1}/{total_pages}\n\n"
            for g in chunk:
                text += f"📂 {g}\n"
            if not chunk: text += "_Nenhum._"
            btns = paginar_buttons(f"gmember_{uid}", page, total_pages)
            btns.insert(0, [Button.inline("👤 Perfil", f"profile_{uid}".encode())])
            await message.edit(text, parse_mode='md', buttons=btns)

        elif data.startswith("hist_"):
            parts = data.split("_")
            uid, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
            db = carregar_dados()
            if uid not in db:
                await event.answer("❌"); return
            historico = list(reversed(db[uid].get("historico", [])))
            chunk, page, total_pages = paginar_lista(historico, page)
            text = f"📜 **Histórico** — `{db[uid]['nome_atual']}`\nPág. {page+1}/{total_pages}\n\n"
            for h in chunk:
                emoji = "📛" if h.get("tipo") == "NOME" else "🆔"
                text += f"{emoji} `{h['data']}`\n   {h['de']} ➜ {h['para']}\n   📍 _{h.get('grupo', 'N/A')}_\n\n"
            if not chunk: text += "_Nenhum registro._"
            btns = paginar_buttons(f"hist_{uid}", page, total_pages)
            btns.insert(0, [Button.inline("👤 Perfil", f"profile_{uid}".encode())])
            await message.edit(text, parse_mode='md', buttons=btns)

        elif data == "noop":
            await event.answer()
        else:
            await event.answer("⚠️ Ação não reconhecida.")

        try:
            await event.answer()
        except:
            pass

    except Exception as e:
        log(f"❌ Callback error: {e}")
        try:
            await event.answer("❌ Erro interno.")
        except:
            pass


# ══════════════════════════════════════════════
# 💬  BOT — CONSULTA NO PRIVADO (PRESERVADO)
# ══════════════════════════════════════════════

@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.raw_text.startswith('/')))
async def bot_private_handler(event):
    """Processa mensagens privadas: URL, CPF, busca, créditos, AutoMs."""
    await registrar_interacao(event)
    sender = await event.get_sender()
    if not sender:
        return

    uid = sender.id
    nome = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Sem nome"
    username_tg = f"@{sender.username}" if sender.username else "Nenhum"
    registrar_usuario_creditos(uid, nome, username_tg)

    texto = event.raw_text.strip()

    # ── Modo adicionar créditos (dono) ──
    if event.chat_id in creditos_pending and uid == OWNER_ID:
        estado = creditos_pending[event.chat_id]

        if estado == "aguardando":
            # Mensagem encaminhada?
            if event.forward and event.forward.sender_id:
                target_id = event.forward.sender_id
                target_info = buscar_usuario_por_id(target_id)
                target_nome = target_info["nome"] if target_info else f"ID {target_id}"
                creditos_pending[event.chat_id] = {"target_id": target_id, "target_nome": target_nome}
                await event.reply(
                    f"👤 **Usuário:** `{target_nome}` (`{target_id}`)\n\n"
                    f"💰 Quantos créditos deseja adicionar?",
                    parse_mode='md'
                )
                return

            # Username?
            if texto.startswith('@'):
                target_info = buscar_usuario_por_username(texto)
                if target_info:
                    creditos_pending[event.chat_id] = {"target_id": target_info["id"], "target_nome": target_info["nome"]}
                    await event.reply(
                        f"👤 **Usuário:** `{target_info['nome']}` (`{target_info['id']}`)\n\n"
                        f"💰 Quantos créditos deseja adicionar?",
                        parse_mode='md'
                    )
                else:
                    await event.reply("❌ Usuário não encontrado no banco.", parse_mode='md')
                return

            # ID?
            if texto.isdigit():
                target_id = int(texto)
                target_info = buscar_usuario_por_id(target_id)
                target_nome = target_info["nome"] if target_info else f"ID {target_id}"
                creditos_pending[event.chat_id] = {"target_id": target_id, "target_nome": target_nome}
                await event.reply(
                    f"👤 **Usuário:** `{target_nome}` (`{target_id}`)\n\n"
                    f"💰 Quantos créditos deseja adicionar?",
                    parse_mode='md'
                )
                return

            await event.reply("❌ Envie @username, ID ou encaminhe uma mensagem.", parse_mode='md')
            return

        elif isinstance(estado, dict) and "target_id" in estado:
            if texto.isdigit():
                qtd = int(texto)
                if qtd <= 0 or qtd > 10000:
                    await event.reply("❌ Valor inválido (1-10000).", parse_mode='md')
                    return
                novo_saldo = adicionar_creditos(estado["target_id"], qtd, f"dono_{OWNER_ID}")
                del creditos_pending[event.chat_id]
                await event.reply(
                    f"✅ **Créditos adicionados!**\n\n"
                    f"👤 **Para:** `{estado['target_nome']}` (`{estado['target_id']}`)\n"
                    f"💰 **Adicionado:** `+{qtd}`\n"
                    f"💎 **Novo saldo:** `{novo_saldo}`",
                    parse_mode='md', buttons=voltar_button()
                )
                return
            await event.reply("❌ Envie um número válido.", parse_mode='md')
            return

    # ── Modo busca pendente ──
    if event.chat_id in search_pending:
        del search_pending[event.chat_id]
        results = buscar_usuario(texto)
        if not results:
            await event.reply("🔎 _Consultando API..._", parse_mode='md')
            dados_api = await consultar_telegram_api(userbot, texto)
            if dados_api:
                uid_r = str(dados_api["id"])
                await event.reply(
                    formatar_perfil_api(dados_api), parse_mode='md',
                    buttons=voltar_button()
                )
            else:
                await event.reply("❌ **Nenhum resultado.**", parse_mode='md', buttons=voltar_button())
        elif len(results) == 1:
            uid_r = str(results[0]["id"])
            await event.reply(formatar_perfil(results[0]), parse_mode='md', buttons=perfil_buttons(uid_r))
        else:
            await event.reply(
                f"🔍 **{len(results)} resultados:**",
                parse_mode='md', buttons=resultado_multiplo_buttons(results)
            )
        return

    # ── Modo consulta API pendente ──
    if event.chat_id in tg_search_pending:
        del tg_search_pending[event.chat_id]
        dados_api = await consultar_telegram_api(userbot, texto)
        if dados_api:
            await event.reply(formatar_perfil_api(dados_api), parse_mode='md', buttons=voltar_button())
        else:
            await event.reply("❌ **Não encontrado.**", parse_mode='md', buttons=voltar_button())
        return

    # ── Detectar tipo de entrada ──
    tipo = detectar_tipo_entrada(texto)

    if tipo == "url":
        # Verificar permissão (dono sempre pode)
        if uid != OWNER_ID:
            allowed = False
            groups = load_groups()
            for g in groups:
                try:
                    participant = await bot(GetParticipantRequest(g["id"], uid))
                    if participant:
                        allowed = True
                        break
                except (UserNotParticipantError, Exception):
                    continue

            if not allowed:
                await event.reply(
                    "⛔ **Acesso negado.**\n\n"
                    "Você precisa ser membro de um grupo autorizado para usar este bot.",
                    parse_mode='md'
                )
                return

        # Verificar créditos
        if uid != OWNER_ID and not tem_creditos(uid):
            await event.reply(formatar_sem_creditos(), parse_mode='md')
            return

        # Processar consulta
        processing_msg = await event.reply(
            f"╔══════════════════════════════╗\n"
            f"║  ⏳ PROCESSANDO CONSULTA      ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"👤 **Solicitante:** {nome}\n"
            f"🆔 **ID:** `{uid}`\n"
            f"📡 Aguarde...",
            parse_mode='md'
        )

        loop = asyncio.get_event_loop()
        result, error = await loop.run_in_executor(None, check_url, texto)

        if error:
            await processing_msg.edit(
                f"╔══════════════════════════════╗\n"
                f"║  ❌ CONSULTA FALHOU            ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"👤 **Solicitante:** {nome}\n"
                f"🆔 **ID:** `{uid}`\n\n"
                f"{error}",
                parse_mode='md'
            )
            return

        # Consumir crédito APENAS no sucesso
        if uid != OWNER_ID:
            consumir_credito(uid, "consulta_iptv_privado")

        saldo = obter_saldo(uid)
        user_tag = f"@{sender.username}" if sender.username else f"`{uid}`"
        header = (
            f"👤 **Solicitante:** {nome}\n"
            f"🆔 **ID:** `{uid}`\n"
            f"📎 **User:** {user_tag}\n"
            f"💰 **Créditos restantes:** `{saldo}`\n\n"
        )
        await processing_msg.edit(header + result, parse_mode='md')

        # Enviar para canal de resultados
        if CANAL_RESULTADOS_ID:
            try:
                channel_msg = (
                    f"📨 **Consulta via Bot (Privado)**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **De:** {nome} ({user_tag})\n"
                    f"🆔 **ID:** `{uid}`\n"
                    f"🕐 **Data:** `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n{result}"
                )
                await bot.send_message(CANAL_RESULTADOS_ID, channel_msg, parse_mode='md')
            except Exception as e:
                log(f"[!] Erro ao enviar ao canal: {e}")

    elif tipo == "cpf":
        # CPF — consulta processada via Pydroid
        cpf_formatado = formatar_cpf(texto)
        if validar_cpf(texto):
            await event.reply(
                f"╔══════════════════════════════╗\n"
                f"║  📄 CPF DETECTADO              ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"📋 **CPF:** `{cpf_formatado}`\n"
                f"✅ **Formato válido**\n\n"
                f"💡 _A consulta é processada externamente._\n"
                f"_Processando via Pydroid..._\n\n"
                f"╚══════════════════════════════╝",
                parse_mode='md', buttons=voltar_button()
            )
        else:
            await event.reply(
                f"❌ **CPF inválido:** `{cpf_formatado}`\n"
                f"Verifique os dígitos e tente novamente.",
                parse_mode='md'
            )

    else:
        # Texto genérico — enviar AutoMs se ativas e não é o dono
        if uid != OWNER_ID:
            automs = obter_automs_ativas()
            if automs:
                for am in automs:
                    await event.reply(
                        f"💬 **{am['title']}**\n\n{am['message']}",
                        parse_mode='md'
                    )
                return
        # Se for o dono ou sem automs, ignora


# ══════════════════════════════════════════════
# 🌐  BOT — INLINE MODE (PRESERVADO do EuBot3.py)
# ══════════════════════════════════════════════

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Modo inline: @InforUser_Bot URL"""
    query = event.text.strip()

    if not query:
        await event.answer(
            results=[],
            switch_pm="Envie uma URL IPTV para consultar",
            switch_pm_param="start"
        )
        return

    match = re.search(URL_PATTERN, query)
    if not match:
        await event.answer(
            results=[],
            switch_pm="URL inválida. Envie uma URL IPTV válida.",
            switch_pm_param="start"
        )
        return

    url = match.group(1)

    # Verificar permissão
    if event.sender_id == OWNER_ID:
        allowed = True
    else:
        allowed = False
        groups = load_groups()
        for g in groups:
            try:
                participant = await bot(GetParticipantRequest(g["id"], event.sender_id))
                if participant:
                    allowed = True
                    break
            except (UserNotParticipantError, Exception):
                continue

    if not allowed:
        await event.answer(
            results=[],
            switch_pm="⛔ Sem permissão. Entre em um grupo autorizado.",
            switch_pm_param="start"
        )
        return

    # Verificar créditos
    if event.sender_id != OWNER_ID and not tem_creditos(event.sender_id):
        await event.answer(
            results=[],
            switch_pm=f"🔴 Créditos esgotados. Contate {OWNER_CONTACT}",
            switch_pm_param="start"
        )
        return

    # Executar consulta
    loop = asyncio.get_event_loop()
    result, error = await loop.run_in_executor(None, check_url, url)

    if error:
        result_id = hashlib.md5(url.encode()).hexdigest()
        builder = event.builder
        article = builder.article(
            title="❌ Consulta Falhou",
            description=error[:100],
            text=error,
            parse_mode='md'
        )
        await event.answer([article])
        return

    # Consumir crédito no sucesso
    if event.sender_id != OWNER_ID:
        consumir_credito(event.sender_id, "consulta_iptv_inline")

    result_id = hashlib.md5(url.encode()).hexdigest()
    builder = event.builder
    article = builder.article(
        title="✅ Resultado IPTV",
        description="Clique para enviar o resultado",
        text=result,
        parse_mode='md'
    )
    await event.answer([article])

    # Enviar para canal
    if CANAL_RESULTADOS_ID:
        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', '') or ''
            sender_username = getattr(sender, 'username', None)
            user_tag = f"@{sender_username}" if sender_username else f"`{event.sender_id}`"
            channel_msg = (
                f"📨 **Consulta via Inline**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **De:** {sender_name} ({user_tag})\n"
                f"🆔 **ID:** `{event.sender_id}`\n"
                f"🕐 **Data:** `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n{result}"
            )
            await bot.send_message(CANAL_RESULTADOS_ID, channel_msg, parse_mode='md')
        except Exception as e:
            log(f"[!] Erro ao enviar ao canal (inline): {e}")


# ══════════════════════════════════════════════
# 📡  USERBOT — CONSULTA VIA REPLY EM GRUPOS
# ══════════════════════════════════════════════

@userbot.on(events.NewMessage(incoming=True))
async def handle_incoming_reply(event):
    """Responde consultas quando alguém responde minha mensagem com URL. (PRESERVADO)"""
    if not event.is_reply:
        return

    replied = await event.get_reply_message()
    if not replied or not replied.out:
        return

    # Verifica se o grupo é permitido
    if event.is_group or event.is_channel:
        if not is_group_allowed(event.chat_id):
            return

    match = re.search(URL_PATTERN, event.raw_text)
    if not match:
        return

    url = match.group(1)

    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', '') or ''
    sender_last = getattr(sender, 'last_name', '') or ''
    sender_username = getattr(sender, 'username', None)
    sender_id = sender.id

    # Registrar no sistema de créditos
    registrar_usuario_creditos(
        sender_id,
        f"{sender_name} {sender_last}".strip() or "Sem nome",
        f"@{sender_username}" if sender_username else "Nenhum"
    )

    processing_msg = await event.reply(
        f"╔══════════════════════════════╗\n"
        f"║  ⏳ PROCESSANDO CONSULTA      ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👤 **Solicitante:** {sender_name} {sender_last}\n"
        f"🆔 **ID:** `{sender_id}`\n"
        f"📡 Aguarde..."
    )

    loop = asyncio.get_event_loop()
    result, error = await loop.run_in_executor(None, check_url, url)

    if error:
        await processing_msg.edit(
            f"╔══════════════════════════════╗\n"
            f"║  ❌ CONSULTA FALHOU            ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"👤 **Solicitante:** {sender_name} {sender_last}\n"
            f"🆔 **ID:** `{sender_id}`\n\n"
            f"{error}"
        )
        return

    user_tag = f"@{sender_username}" if sender_username else f"`{sender_id}`"
    header = (
        f"👤 **Solicitante:** {sender_name} {sender_last}\n"
        f"🆔 **ID:** `{sender_id}`\n"
        f"📎 **User:** {user_tag}\n\n"
    )
    await processing_msg.edit(header + result, parse_mode='md')

    # Envia para o canal
    if CANAL_RESULTADOS_ID:
        try:
            channel_msg = (
                f"📨 **Nova Consulta**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **De:** {sender_name} {sender_last} ({user_tag})\n"
                f"🆔 **ID:** `{sender_id}`\n"
                f"💬 **Grupo:** `{event.chat_id}`\n"
                f"🕐 **Data:** `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n{result}"
            )
            await userbot.send_message(CANAL_RESULTADOS_ID, channel_msg, parse_mode='md')
        except Exception as e:
            log(f"[!] Erro ao enviar ao canal: {e}")


@userbot.on(events.NewMessage(outgoing=True))
async def handle_self_reply(event):
    """Permite o próprio dono testar respondendo suas próprias mensagens. (PRESERVADO)"""
    if not event.is_reply:
        return
    replied = await event.get_reply_message()
    if not replied or not replied.out:
        return
    if "RESULTADO DA CONSULTA" in event.raw_text or "PROCESSANDO" in event.raw_text:
        return

    match = re.search(URL_PATTERN, event.raw_text)
    if not match:
        return

    url = match.group(1)
    me = await userbot.get_me()

    processing_msg = await event.reply(
        f"╔══════════════════════════════╗\n"
        f"║  ⏳ PROCESSANDO (TESTE)       ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👤 **Dono:** {me.first_name or ''}\n"
        f"📡 Aguarde..."
    )

    loop = asyncio.get_event_loop()
    result, error = await loop.run_in_executor(None, check_url, url)

    if error:
        await processing_msg.edit(
            f"╔══════════════════════════════╗\n"
            f"║  ❌ CONSULTA FALHOU            ║\n"
            f"╚══════════════════════════════╝\n\n{error}"
        )
        return

    me_tag = f"@{me.username}" if me.username else f"`{me.id}`"
    header = (
        f"👤 **Dono:** {me.first_name or ''}\n"
        f"🆔 **ID:** `{me.id}`\n\n"
    )
    await processing_msg.edit(header + result, parse_mode='md')


# ══════════════════════════════════════════════
# 🤖  USERBOT — COMANDOS DO DONO
# ══════════════════════════════════════════════

@userbot.on(events.NewMessage(pattern=r'^[!/]grupos$', outgoing=True))
async def ub_cmd_grupos(event):
    text, buttons = build_groups_page(0)
    await event.reply(text, buttons=buttons, parse_mode='md')


@userbot.on(events.NewMessage(pattern=r'^[!/]addgrupo\s+(-?\d+)(?:\s+(.+))?$', outgoing=True))
async def ub_add_group(event):
    gid = int(event.pattern_match.group(1))
    name = event.pattern_match.group(2)
    if not name:
        try:
            entity = await userbot.get_entity(gid)
            name = getattr(entity, 'title', None) or f"Grupo {gid}"
        except Exception:
            name = f"Grupo {gid}"
    name = name.strip()
    added = add_group(gid, name)
    if added:
        await event.reply(f"✅ Grupo **{name}** (`{gid}`) adicionado!", parse_mode='md')
    else:
        await event.reply(f"⚠️ Grupo `{gid}` já cadastrado.", parse_mode='md')


@userbot.on(events.NewMessage(pattern=r'^[!/]id$', outgoing=True))
async def ub_get_id(event):
    chat = await event.get_chat()
    chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'N/A')
    await event.reply(
        f"🆔 **Chat:** `{event.chat_id}`\n📋 **Nome:** {chat_name}",
        parse_mode='md'
    )


@userbot.on(events.NewMessage(pattern=r'^[!/]help$', outgoing=True))
async def ub_help(event):
    await event.reply(
        "╔══════════════════════════════╗\n"
        "║  📖 COMANDOS DO USERBOT       ║\n"
        "╚══════════════════════════════╝\n\n"
        "🔹 `/grupos` — Gestão de grupos\n"
        "🔹 `/addgrupo <id>` — Adicionar grupo\n"
        "🔹 `/id` — Ver ID do chat\n"
        "🔹 `/status` — Status\n"
        "🔹 `/help` — Ajuda\n\n"
        "📡 Responda minha mensagem com URL para consultar.\n\n"
        "╚══════════════════════════════╝",
        parse_mode='md'
    )


@userbot.on(events.NewMessage(pattern=r'^[!/]status$', outgoing=True))
async def ub_status(event):
    me = await userbot.get_me()
    groups = load_groups()
    automs = load_automs()
    info_cred = obter_info_usuarios()

    await event.reply(
        f"╔══════════════════════════════╗\n"
        f"║  📊 STATUS DO SISTEMA          ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"✅ **Userbot + Bot Online**\n"
        f"👤 {me.first_name} (@{me.username or 'N/A'})\n"
        f"📋 **Grupos:** `{len(groups)}`\n"
        f"💬 **AutoMs:** `{len(automs)}`\n"
        f"👥 **Usuários:** `{info_cred['total_usuarios']}`\n"
        f"💰 **Créditos:** `{info_cred['total_creditos']}`\n"
        f"🕐 `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`\n\n"
        f"╚══════════════════════════════╝",
        parse_mode='md'
    )


# Callbacks do userbot para grupos
@userbot.on(events.CallbackQuery(pattern=r'^grppage:(\d+)$'))
async def ub_callback_page(event):
    me = await userbot.get_me()
    if event.sender_id != me.id:
        return
    page = int(event.pattern_match.group(1))
    text, buttons = build_groups_page(page)
    await event.edit(text, buttons=buttons, parse_mode='md')


@userbot.on(events.CallbackQuery(pattern=r'^rmgrp:(-?\d+)$'))
async def ub_callback_remove(event):
    me = await userbot.get_me()
    if event.sender_id != me.id:
        return
    gid = int(event.pattern_match.group(1))
    remove_group(gid)
    text, buttons = build_groups_page(0)
    await event.edit(text, buttons=buttons, parse_mode='md')


@userbot.on(events.CallbackQuery(pattern=r'^addgrp$'))
async def ub_callback_add(event):
    me = await userbot.get_me()
    if event.sender_id != me.id:
        return
    await event.answer()
    await event.reply(
        "Envie: `/addgrupo -100123456`\n"
        "💡 O nome será detectado automaticamente!",
        parse_mode='md'
    )


@userbot.on(events.CallbackQuery(pattern=r'^noop$'))
async def ub_callback_noop(event):
    await event.answer()


# ══════════════════════════════════════════════
# 🚀  INICIALIZAÇÃO (USERBOT + BOT JUNTOS)
# ══════════════════════════════════════════════

async def main():
    # Inicia o Userbot (conta pessoal)
    await userbot.start(phone=PHONE)
    me = await userbot.get_me()
    print("╔══════════════════════════════╗")
    print("║  ✅ USERBOT ONLINE            ║")
    print("╚══════════════════════════════╝")
    print(f"  👤 {me.first_name} (@{me.username or 'N/A'})")
    print(f"  🆔 {me.id}")
    print(f"  📋 Grupos permitidos: {len(load_groups())}")
    print(f"  💬 AutoMs: {len(load_automs())}")
    print("═══════════════════════════════")

    # Inicia o Bot (via token)
    await bot.start(bot_token=BOT_TOKEN)
    bot_me = await bot.get_me()
    print("╔══════════════════════════════╗")
    print("║  🤖 BOT ONLINE               ║")
    print("╚══════════════════════════════╝")
    print(f"  🤖 {bot_me.first_name} (@{bot_me.username or 'N/A'})")
    print(f"  🆔 {bot_me.id}")
    print("═══════════════════════════════")

    info = obter_info_usuarios()
    print()
    print("🚀 Sistema completo rodando!")
    print(f"  UserBot + Bot + Inline + AutoMs + Créditos")
    print(f"  👥 {info['total_usuarios']} usuários | 💰 {info['total_creditos']} créditos")
    print()
    print(f"  👤 Dono: Edivaldo Silva")
    print(f"  🆔 ID: {OWNER_ID}")
    print(f"  👨‍💻 {OWNER_CONTACT}")
    print()

    # Roda ambos simultaneamente + varredura + threads
    await asyncio.gather(
        userbot.run_until_disconnected(),
        bot.run_until_disconnected(),
        auto_scanner(userbot),
        executar_threads_atualizacao(userbot)
    )


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
