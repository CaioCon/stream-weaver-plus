# ══════════════════════════════════════════════
# ⚙️  CONFIG — User Info Bot PRO v8.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
v8.0 — escopo enxuto:
  • Notificações vão para um CANAL (não mais para DM do owner).
  • Inline lookup aceita @username OU ID numérico:
        @InforUser_Bot @fulano
        @InforUser_Bot 1234567890
  • Sem premium, sem combo, sem importação de banco.
  • Cards individuais por usuário (com foto quando disponível).
  • Painel de gerenciamento dentro do canal de notificação.
  • Pedido de remoção: usuário fala com o bot em DM → bot abre DM com o owner.
"""

import os
import re

# ── Credenciais Telegram ──
API_ID       = 29214781
API_HASH     = "9fc77b4f32302f4d4081a4839cc7ae1f"
PHONE        = "+5588998225077"
BOT_TOKEN    = "8618840827:AAHohLnNTWh_lkP4l9du6KJTaRQcPsNrwV8"
OWNER_ID     = 2061557102
BOT_USERNAME = "InforUser_Bot"

# ── Grupo de notificação (o bot deve ser admin do grupo) ──
# Aceita o ID -100... do supergrupo.
NOTIFY_CHANNEL_ID   = -1003708574604
NOTIFY_CHANNEL_LINK = "https://t.me/c/3708574604"

# Itens por página na paginação de cards (DM do owner)
ITEMS_PER_PAGE = 6

# ── Caminhos ──
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
FOLDER_PATH = os.path.join(BASE_DIR, "data")
FILE_PATH   = os.path.join(FOLDER_PATH, "user_database.json")
LOG_PATH    = os.path.join(FOLDER_PATH, "monitor.log")
CARD_INDEX  = os.path.join(FOLDER_PATH, "card_index.json")  # uid -> message_id no canal
SETTINGS    = os.path.join(FOLDER_PATH, "settings.json")    # painel: campos ocultos globais
PHONE_AUTH  = os.path.join(FOLDER_PATH, "phone_auth.json")  # lista de uids autorizados a ver telefone
SESSION_USER = os.path.join(BASE_DIR, "session_monitor")
SESSION_BOT  = os.path.join(BASE_DIR, "session_bot")

os.makedirs(FOLDER_PATH, exist_ok=True)

# ── Parâmetros ──
SCAN_INTERVAL              = 3600
MAX_HISTORY                = 30
SCRAPE_MSG_LIMIT_PER_GROUP = 400
SCRAPE_CONCURRENCY         = 6

# ── Campos do card que podem ser ocultados globalmente pelo painel ──
# Marcado True no settings.json = oculto no canal
TOGGLEABLE_FIELDS = ["nome", "id", "username", "phone", "bio", "grupos", "historico", "foto"]

DEFAULT_HIDDEN_GLOBAL = {k: False for k in TOGGLEABLE_FIELDS}

# ── Inline: aceita @username OU ID numérico ──
# Telethon InlineQuery já entrega só o "q" sem o @InforUser_Bot.
INLINE_USERNAME_RE = re.compile(r'^@?([A-Za-z][A-Za-z0-9_]{3,31})$')
INLINE_ID_RE       = re.compile(r'^(\d{4,15})$')
