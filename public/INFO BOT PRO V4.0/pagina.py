# ══════════════════════════════════════════════
# 📄  PAGINAÇÃO — INFO BOT PRO V4.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

from telethon import Button

ITEMS_PER_PAGE = 8


def paginar_buttons(prefix: str, page: int, total_pages: int):
    """Gera botões de paginação com navegação."""
    btns = []
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️ Anterior", f"{prefix}_page_{page - 1}".encode()))
    nav.append(Button.inline(f"📄 {page + 1}/{total_pages}", b"noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("Próxima ▶️", f"{prefix}_page_{page + 1}".encode()))
    btns.append(nav)
    btns.append([Button.inline("🔙 Menu Principal", b"cmd_menu")])
    return btns


def calcular_pagina(total: int, page: int) -> tuple:
    """Calcula total de páginas e ajusta página atual.
    
    Returns:
        (page_ajustada, total_pages, inicio, fim)
    """
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = min(page, total_pages - 1)
    inicio = page * ITEMS_PER_PAGE
    fim = inicio + ITEMS_PER_PAGE
    return page, total_pages, inicio, fim


def paginar_lista(lista: list, page: int) -> tuple:
    """Pagina uma lista genérica.
    
    Returns:
        (items_da_pagina, page_ajustada, total_pages)
    """
    page, total_pages, inicio, fim = calcular_pagina(len(lista), page)
    return lista[inicio:fim], page, total_pages
