# ══════════════════════════════════════════════
# ⚙️  CREDENCIAIS DA API TELEGRAM
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════

import json
import os

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aplicativo_config.json")

# Valores padrão — substitua ou use aplicativo_config.json
_DEFAULTS = {
    "api_id": 0,
    "api_hash": "",
    "phone": ""
}


def _carregar_config() -> dict:
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _config():
    cfg = _DEFAULTS.copy()
    cfg.update(_carregar_config())
    return cfg


def salvar_config(api_id: int, api_hash: str, phone: str):
    """Salva credenciais no arquivo de configuração."""
    data = {"api_id": api_id, "api_hash": api_hash, "phone": phone}
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Acesso direto ──
API_ID: int = _config()["api_id"]
API_HASH: str = _config()["api_hash"]
PHONE: str = _config()["phone"]
