# ══════════════════════════════════════════════
# 💰  SISTEMA DE CRÉDITOS — INFO BOT PRO V4.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
#
# Cada usuário que interagir com o bot receberá
# 10 créditos iniciais. Créditos são consumidos
# APENAS quando o resultado é entregue com sucesso
# em conversa privada com o bot.
#
# O dono pode adicionar créditos via:
# - Username (@user)
# - ID numérico
# - Mensagem encaminhada
# ══════════════════════════════════════════════

import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDITOS_FILE = os.path.join(BASE_DIR, "creditos_usuarios.json")
USUARIOS_FILE = os.path.join(BASE_DIR, "usuarios_bot.json")

CREDITOS_INICIAIS = 10
OWNER_CONTACT = "@Edkd1"


# ══════════════════════════════════════
# 📁  PERSISTÊNCIA
# ══════════════════════════════════════

def _carregar_creditos() -> dict:
    if os.path.exists(CREDITOS_FILE):
        try:
            with open(CREDITOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _salvar_creditos(db: dict):
    try:
        with open(CREDITOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


def _carregar_usuarios() -> dict:
    if os.path.exists(USUARIOS_FILE):
        try:
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _salvar_usuarios(db: dict):
    try:
        with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


# ══════════════════════════════════════
# 👤  REGISTRO DE USUÁRIO
# ══════════════════════════════════════

def registrar_usuario(user_id: int, nome: str, username: str):
    """Registra usuário no sistema. Cria com créditos iniciais se novo."""
    uid = str(user_id)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Registro de informações do usuário
    usuarios = _carregar_usuarios()
    if uid not in usuarios:
        usuarios[uid] = {
            "id": user_id,
            "nome": nome,
            "username": username,
            "primeiro_contato": agora,
            "ultimo_contato": agora,
            "interacoes": 1
        }
    else:
        usuarios[uid]["nome"] = nome
        usuarios[uid]["username"] = username
        usuarios[uid]["ultimo_contato"] = agora
        usuarios[uid]["interacoes"] = usuarios[uid].get("interacoes", 0) + 1
    _salvar_usuarios(usuarios)

    # Registro de créditos
    creditos = _carregar_creditos()
    if uid not in creditos:
        creditos[uid] = {
            "saldo": CREDITOS_INICIAIS,
            "total_recebido": CREDITOS_INICIAIS,
            "total_consumido": 0,
            "historico": [{
                "data": agora,
                "tipo": "INICIAL",
                "valor": CREDITOS_INICIAIS,
                "saldo_apos": CREDITOS_INICIAIS
            }]
        }
        _salvar_creditos(creditos)
        return True  # Novo usuário
    return False  # Já existia


def obter_saldo(user_id: int) -> int:
    """Retorna saldo de créditos do usuário."""
    uid = str(user_id)
    creditos = _carregar_creditos()
    if uid in creditos:
        return creditos[uid].get("saldo", 0)
    return 0


def tem_creditos(user_id: int) -> bool:
    """Verifica se o usuário tem créditos disponíveis."""
    return obter_saldo(user_id) > 0


def consumir_credito(user_id: int, motivo: str = "consulta") -> bool:
    """Consome 1 crédito do usuário. Retorna True se sucesso."""
    uid = str(user_id)
    creditos = _carregar_creditos()
    if uid not in creditos or creditos[uid].get("saldo", 0) <= 0:
        return False

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    creditos[uid]["saldo"] -= 1
    creditos[uid]["total_consumido"] = creditos[uid].get("total_consumido", 0) + 1
    creditos[uid]["historico"].append({
        "data": agora,
        "tipo": "CONSUMO",
        "valor": -1,
        "motivo": motivo,
        "saldo_apos": creditos[uid]["saldo"]
    })

    # Manter histórico limitado
    if len(creditos[uid]["historico"]) > 100:
        creditos[uid]["historico"] = creditos[uid]["historico"][-100:]

    _salvar_creditos(creditos)
    return True


def adicionar_creditos(user_id: int, quantidade: int, adicionado_por: str = "dono") -> int:
    """Adiciona créditos a um usuário. Retorna novo saldo."""
    uid = str(user_id)
    creditos = _carregar_creditos()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if uid not in creditos:
        creditos[uid] = {
            "saldo": 0,
            "total_recebido": 0,
            "total_consumido": 0,
            "historico": []
        }

    creditos[uid]["saldo"] += quantidade
    creditos[uid]["total_recebido"] = creditos[uid].get("total_recebido", 0) + quantidade
    creditos[uid]["historico"].append({
        "data": agora,
        "tipo": "ADICIONADO",
        "valor": quantidade,
        "por": adicionado_por,
        "saldo_apos": creditos[uid]["saldo"]
    })

    if len(creditos[uid]["historico"]) > 100:
        creditos[uid]["historico"] = creditos[uid]["historico"][-100:]

    _salvar_creditos(creditos)
    return creditos[uid]["saldo"]


# ══════════════════════════════════════
# 🔍  BUSCA DE USUÁRIO POR USERNAME/ID
# ══════════════════════════════════════

def buscar_usuario_por_username(username: str) -> dict | None:
    """Busca usuário pelo username no banco de usuários."""
    username_limpo = username.lower().lstrip('@')
    usuarios = _carregar_usuarios()
    for uid, dados in usuarios.items():
        user_db = dados.get("username", "").lower().lstrip('@')
        if user_db and user_db == username_limpo:
            return {"id": int(uid), **dados}
    return None


def buscar_usuario_por_id(user_id: int) -> dict | None:
    """Busca usuário pelo ID."""
    uid = str(user_id)
    usuarios = _carregar_usuarios()
    if uid in usuarios:
        return {"id": user_id, **usuarios[uid]}
    return None


# ══════════════════════════════════════
# 🎨  FORMATAÇÃO
# ══════════════════════════════════════

def formatar_saldo(user_id: int, nome: str) -> str:
    """Formata mensagem de saldo."""
    saldo = obter_saldo(user_id)
    creditos = _carregar_creditos()
    uid = str(user_id)
    total_r = creditos.get(uid, {}).get("total_recebido", 0)
    total_c = creditos.get(uid, {}).get("total_consumido", 0)

    emoji_saldo = "🟢" if saldo > 3 else "🟡" if saldo > 0 else "🔴"

    texto = (
        f"╔══════════════════════════════╗\n"
        f"║  💰 SEUS CRÉDITOS              ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👤 **Nome:** `{nome}`\n"
        f"{emoji_saldo} **Saldo:** `{saldo}` créditos\n\n"
        f"📊 **Estatísticas:**\n"
        f"├ 📥 Recebidos: `{total_r}`\n"
        f"└ 📤 Consumidos: `{total_c}`\n"
    )

    if saldo <= 0:
        texto += (
            f"\n⚠️ **Créditos esgotados!**\n"
            f"Entre em contato com {OWNER_CONTACT} para adquirir mais.\n"
        )

    texto += f"\n╚══════════════════════════════╝"
    return texto


def formatar_sem_creditos() -> str:
    """Mensagem quando o usuário não tem créditos."""
    return (
        f"╔══════════════════════════════╗\n"
        f"║  🔴 CRÉDITOS INSUFICIENTES     ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"Seus créditos acabaram!\n\n"
        f"📩 Entre em contato com o administrador\n"
        f"para solicitar mais créditos:\n\n"
        f"👤 **Contato:** {OWNER_CONTACT}\n\n"
        f"╚══════════════════════════════╝"
    )


def obter_info_usuarios() -> dict:
    """Retorna estatísticas gerais dos usuários."""
    usuarios = _carregar_usuarios()
    creditos = _carregar_creditos()

    total_usuarios = len(usuarios)
    total_creditos_circulando = sum(c.get("saldo", 0) for c in creditos.values())
    total_consumidos = sum(c.get("total_consumido", 0) for c in creditos.values())

    return {
        "total_usuarios": total_usuarios,
        "total_creditos": total_creditos_circulando,
        "total_consumidos": total_consumidos
    }
