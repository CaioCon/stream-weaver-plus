# ══════════════════════════════════════════════
# 💾  DB — User Info Bot PRO v8.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
import json
import os
from datetime import datetime
from config import (FILE_PATH, LOG_PATH, CARD_INDEX, SETTINGS,
                    DEFAULT_HIDDEN_GLOBAL, MAX_HISTORY)


def _ensure_files():
    if not os.path.exists(FILE_PATH):
        _atomic_write(FILE_PATH, {})
    if not os.path.exists(CARD_INDEX):
        _atomic_write(CARD_INDEX, {})
    if not os.path.exists(SETTINGS):
        _atomic_write(SETTINGS, {"hidden_global": dict(DEFAULT_HIDDEN_GLOBAL)})
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Log iniciado\n")


def _atomic_write(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        return {}


_ensure_files()


# ── Banco de usuários ──
def carregar_dados() -> dict:
    return _read(FILE_PATH)


def salvar_dados(db: dict):
    _atomic_write(FILE_PATH, db)


# ── Índice de cards no canal ──
def carregar_cards() -> dict:
    return _read(CARD_INDEX)


def salvar_cards(idx: dict):
    _atomic_write(CARD_INDEX, idx)


def get_card_msg_id(uid: str):
    return carregar_cards().get(str(uid))


def set_card_msg_id(uid: str, msg_id: int):
    idx = carregar_cards()
    idx[str(uid)] = int(msg_id)
    salvar_cards(idx)


def del_card_msg_id(uid: str):
    idx = carregar_cards()
    idx.pop(str(uid), None)
    salvar_cards(idx)


# ── Settings (campos globais ocultos) ──
def carregar_settings() -> dict:
    s = _read(SETTINGS)
    s.setdefault("hidden_global", dict(DEFAULT_HIDDEN_GLOBAL))
    for k, v in DEFAULT_HIDDEN_GLOBAL.items():
        s["hidden_global"].setdefault(k, v)
    return s


def salvar_settings(s: dict):
    _atomic_write(SETTINGS, s)


def toggle_field_hidden(field: str) -> bool:
    s = carregar_settings()
    cur = bool(s["hidden_global"].get(field, False))
    s["hidden_global"][field] = not cur
    salvar_settings(s)
    return s["hidden_global"][field]


def is_field_hidden(field: str) -> bool:
    return bool(carregar_settings()["hidden_global"].get(field, False))


# ── Helpers ──
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except IOError:
        pass


def iter_usuarios(db: dict):
    for k, v in db.items():
        if not k.startswith("_"):
            yield k, v


def agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def ensure_user_shape(entry: dict):
    entry.setdefault("nome_atual", "")
    entry.setdefault("username_atual", "")
    entry.setdefault("phone", "")
    entry.setdefault("bio", "")
    entry.setdefault("fotos", False)
    entry.setdefault("grupos", [])
    entry.setdefault("historico", [])
    entry.setdefault("primeiro_visto", agora_str())
    entry.setdefault("ultima_atualizacao", agora_str())
    if len(entry["historico"]) > MAX_HISTORY:
        entry["historico"] = entry["historico"][-MAX_HISTORY:]


def upsert_user(db: dict, uid, *, nome="", username="", phone="", bio="",
                fotos=False, grupo=None) -> tuple:
    """Insere ou atualiza usuário. Retorna (entry, mudancas:list, novo:bool)."""
    uid = str(uid)
    novo = uid not in db
    entry = db.setdefault(uid, {})
    ensure_user_shape(entry)
    mudancas = []
    ts = agora_str()

    def _push(tipo, de, para):
        entry["historico"].append({"tipo": tipo, "de": de, "para": para,
                                   "data": ts, "grupo": grupo or "N/A"})
        mudancas.append((tipo, de, para))

    if nome and nome != entry.get("nome_atual"):
        if entry.get("nome_atual"):
            _push("NOME", entry["nome_atual"], nome)
        entry["nome_atual"] = nome
    if username and username != entry.get("username_atual"):
        if entry.get("username_atual"):
            _push("USER", entry["username_atual"], username)
        entry["username_atual"] = username
    if phone and phone != entry.get("phone"):
        if entry.get("phone"):
            _push("PHONE", entry["phone"], phone)
        entry["phone"] = phone
    if bio and bio != entry.get("bio"):
        if entry.get("bio"):
            _push("BIO", entry["bio"], bio)
        entry["bio"] = bio
    if fotos != entry.get("fotos"):
        entry["fotos"] = fotos

    if grupo:
        if grupo not in entry["grupos"]:
            entry["grupos"].append(grupo)

    entry["ultima_atualizacao"] = ts
    return entry, mudancas, novo
