# ══════════════════════════════════════════════
# 💬  AUTOMS — MENSAGENS AUTOMÁTICAS
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
#
# Sistema de mensagens automáticas para DMs.
# O dono pode criar, editar, revisar, ativar/
# desativar e apagar mensagens automáticas.
#
# Preservado 100% da lógica original do EuBot3.py
# + melhorias profissionais.
# ══════════════════════════════════════════════

import os
import json
import math
from datetime import datetime
from telethon import Button

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOMS_FILE = os.path.join(BASE_DIR, "automs.json")
AUTOMS_PER_PAGE = 5


# ══════════════════════════════════════
# 📁  PERSISTÊNCIA (PRESERVADO)
# ══════════════════════════════════════

def load_automs() -> list:
    """Carrega mensagens automáticas do arquivo JSON."""
    if not os.path.exists(AUTOMS_FILE):
        save_automs([])
        return []
    try:
        with open(AUTOMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_automs(automs: list):
    """Salva mensagens automáticas no arquivo JSON."""
    try:
        with open(AUTOMS_FILE, "w", encoding="utf-8") as f:
            json.dump(automs, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


# ══════════════════════════════════════
# ✏️  OPERAÇÕES CRUD
# ══════════════════════════════════════

def add_autom(title: str, message: str) -> int:
    """Adiciona nova mensagem automática. Retorna total."""
    automs = load_automs()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    automs.append({
        "title": title,
        "message": message,
        "ativo": True,
        "criado_em": agora,
        "editado_em": agora
    })
    save_automs(automs)
    return len(automs)


def remove_autom(index: int) -> dict | None:
    """Remove mensagem automática pelo índice."""
    automs = load_automs()
    if 0 <= index < len(automs):
        removed = automs.pop(index)
        save_automs(automs)
        return removed
    return None


def editar_autom(index: int, title: str = None, message: str = None) -> bool:
    """Edita título e/ou mensagem de uma autom."""
    automs = load_automs()
    if 0 <= index < len(automs):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if title is not None:
            automs[index]["title"] = title
        if message is not None:
            automs[index]["message"] = message
        automs[index]["editado_em"] = agora
        save_automs(automs)
        return True
    return False


def toggle_autom(index: int) -> bool | None:
    """Ativa/desativa uma mensagem automática. Retorna novo estado."""
    automs = load_automs()
    if 0 <= index < len(automs):
        automs[index]["ativo"] = not automs[index].get("ativo", True)
        save_automs(automs)
        return automs[index]["ativo"]
    return None


def obter_automs_ativas() -> list:
    """Retorna apenas as mensagens automáticas ativas."""
    automs = load_automs()
    return [a for a in automs if a.get("ativo", True)]


# ══════════════════════════════════════
# 🎨  PAGINAÇÃO DE AUTOMS (PRESERVADO)
# ══════════════════════════════════════

def build_automs_page(page: int = 0):
    """Constrói página de automs com botões inline."""
    automs = load_automs()
    total = len(automs)
    total_pages = max(1, math.ceil(total / AUTOMS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    start = page * AUTOMS_PER_PAGE
    end = start + AUTOMS_PER_PAGE
    page_automs = automs[start:end]

    text = (
        f"╔══════════════════════════════╗\n"
        f"║  💬 AUTOMS — RESPOSTAS AUTO   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"📊 **Total:** `{total}` mensagem(ns)\n"
        f"📄 **Página:** `{page + 1}/{total_pages}`\n\n"
    )

    if not page_automs:
        text += "📭 Nenhuma mensagem automática cadastrada.\n"
    else:
        for i, am in enumerate(page_automs, start=start + 1):
            preview = am['message'][:50] + "..." if len(am['message']) > 50 else am['message']
            estado = "🟢" if am.get("ativo", True) else "🔴"
            text += f"**{i}.** {estado} 📌 **{am['title']}**\n  _{preview}_\n\n"

    text += "╚══════════════════════════════╝"

    buttons = []
    for idx, am in enumerate(page_automs):
        real_idx = start + idx
        estado = am.get("ativo", True)
        toggle_txt = "🔴 Desativar" if estado else "🟢 Ativar"
        buttons.append([
            Button.inline(f"👁 {am['title'][:12]}", data=f"viewautom:{real_idx}"),
            Button.inline(toggle_txt, data=f"toggleautom:{real_idx}"),
            Button.inline("🗑", data=f"rmautom:{real_idx}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("◀️ Voltar", data=f"autompage:{page - 1}"))
    nav_row.append(Button.inline(f"📄 {page + 1}/{total_pages}", data="noop"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("Avançar ▶️", data=f"autompage:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        Button.inline("➕ Nova Mensagem", data="addautom_prompt"),
        Button.inline("🔄 Atualizar", data="autompage:0")
    ])

    return text, buttons
