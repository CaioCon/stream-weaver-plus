# ══════════════════════════════════════════════
# 🔄  MIGRADOR IPTV — INFO BOT PRO V4.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ⚡ Powered by 773H Ultra
#
# Estado isolado por usuário — nenhum interfere
# no processo do outro. Botões inline para
# parar | pausar | continuar com paginação.
# ══════════════════════════════════════════════

import os
import json
import asyncio
import requests
import threading
import random
import ssl
import logging
import re
from datetime import datetime

from requests.packages.urllib3.exceptions import InsecureRequestWarning

# ── SSL / Requests Config (preservado 100%) ──
try:
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = (
        "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:"
        "TLS_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:"
        "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:"
        "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:"
        "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:"
        "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:"
        "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:"
        "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA:"
        "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA:"
        "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:"
        "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA:"
        "TLS_RSA_WITH_AES_128_GCM_SHA256:"
        "TLS_RSA_WITH_AES_256_GCM_SHA384:"
        "TLS_RSA_WITH_AES_128_CBC_SHA:"
        "TLS_RSA_WITH_AES_256_CBC_SHA:"
        "TLS_RSA_WITH_3DES_EDE_CBC_SHA:"
        "TLS13-CHACHA20-POLY1305-SHA256:"
        "TLS13-AES-128-GCM-SHA256:"
        "TLS13-AES-256-GCM-SHA384:ECDHE:!COMP:"
        "TLS13-AES-256-GCM-SHA384:"
        "TLS13-CHACHA20-POLY1305-SHA256:"
        "TLS13-AES-128-GCM-SHA256"
    )
except Exception:
    pass

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
logging.captureWarnings(True)

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

# ── Caminhos ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(BASE_DIR, "hosts.txt")
MIGRADOR_DATA_DIR = os.path.join(BASE_DIR, "migrador_dados")
USERS_LOG_FILE = os.path.join(BASE_DIR, "usuarios_interacoes.json")

os.makedirs(MIGRADOR_DATA_DIR, exist_ok=True)

# ── User-Agents rotativos (preservado 100%) ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/605.1.15 Version/16.3 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 SamsungBrowser/22.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Brave/1.60",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OPR/105.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (compatible; YandexBrowser/23.9)"
]

ITEMS_PER_PAGE_MIGRADOR = 5


# ══════════════════════════════════════════════
# 📁  ESTADO POR USUÁRIO — ISOLAMENTO TOTAL
# ══════════════════════════════════════════════

class EstadoMigracao:
    """Estado de migração isolado por usuário."""

    def __init__(self, user_id: int, username: str, password: str,
                 user_name: str = "", user_username: str = ""):
        self.user_id = user_id
        self.username = username       # credencial IPTV
        self.password = password       # credencial IPTV
        self.user_name = user_name     # nome do solicitante
        self.user_username = user_username  # @username solicitante
        self.hits = 0
        self.fails = 0
        self.total_hosts = 0
        self.processados = 0
        self.resultados = []           # lista de hits
        self.status = "executando"     # executando | pausado | parado | finalizado
        self.inicio = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.msg_id = None             # ID da mensagem de progresso
        self.chat_id = None
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()        # Não pausado por padrão
        self._stop_event = threading.Event()

    @property
    def progresso(self) -> int:
        if self.total_hosts == 0:
            return 0
        return min(100, int((self.processados / self.total_hosts) * 100))

    def pausar(self):
        self.status = "pausado"
        self._pause_event.clear()

    def continuar(self):
        self.status = "executando"
        self._pause_event.set()

    def parar(self):
        self.status = "parado"
        self._stop_event.set()
        self._pause_event.set()  # Desbloqueia se pausado

    @property
    def parado(self) -> bool:
        return self._stop_event.is_set()

    def aguardar_pause(self):
        """Bloqueia a thread se estiver pausado."""
        self._pause_event.wait()

    def add_hit(self, resultado: dict):
        with self._lock:
            self.hits += 1
            self.resultados.append(resultado)

    def add_fail(self):
        with self._lock:
            self.fails += 1

    def incrementar(self):
        with self._lock:
            self.processados += 1


# Estado global de migrações por user_id
_migracoes_ativas: dict[int, EstadoMigracao] = {}
_migracoes_lock = threading.Lock()


def obter_migracao(user_id: int) -> EstadoMigracao | None:
    with _migracoes_lock:
        return _migracoes_ativas.get(user_id)


def registrar_migracao(estado: EstadoMigracao):
    with _migracoes_lock:
        _migracoes_ativas[estado.user_id] = estado


def remover_migracao(user_id: int):
    with _migracoes_lock:
        _migracoes_ativas.pop(user_id, None)


# ══════════════════════════════════════════════
# 💾  LOG DE INTERAÇÕES (TODOS OS USUÁRIOS)
# ══════════════════════════════════════════════

def _carregar_interacoes() -> dict:
    if os.path.exists(USERS_LOG_FILE):
        try:
            with open(USERS_LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _salvar_interacoes(data: dict):
    try:
        with open(USERS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


def registrar_usuario_interacao(user_id: int, nome: str, username: str, acao: str):
    """Salva localmente todas as interações de usuários."""
    db = _carregar_interacoes()
    uid = str(user_id)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if uid not in db:
        db[uid] = {
            "id": user_id,
            "nome": nome,
            "username": username,
            "primeira_interacao": agora,
            "interacoes": []
        }
    else:
        db[uid]["nome"] = nome
        db[uid]["username"] = username

    db[uid]["interacoes"].append({
        "data": agora,
        "acao": acao
    })

    # Manter no máximo 100 interações por usuário
    if len(db[uid]["interacoes"]) > 100:
        db[uid]["interacoes"] = db[uid]["interacoes"][-100:]

    _salvar_interacoes(db)


# ══════════════════════════════════════════════
# 🔧  FUNÇÕES DO MIGRADOR (PRESERVADAS 100%)
# ══════════════════════════════════════════════

def nova_session():
    s = requests.Session()
    s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    return s


def carregar_hosts() -> list:
    if not os.path.exists(HOSTS_FILE):
        return []
    with open(HOSTS_FILE, "r", encoding="utf-8") as f:
        return list(dict.fromkeys([h.strip() for h in f if h.strip()]))


def formatar_data_ts(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return "N/A"


def contar_conteudo(base_url, user, pwd) -> tuple:
    def req(action):
        s = nova_session()
        try:
            r = s.get(
                f"{base_url}?username={user}&password={pwd}&action={action}",
                timeout=7
            )
            return len(r.json())
        except Exception:
            return 0
        finally:
            s.close()
    return req("get_live_streams"), req("get_vod_streams"), req("get_series")


def converter_para_player_api(url_original: str) -> tuple:
    """Converte qualquer formato de URL IPTV para player_api.php."""
    try:
        url_original = url_original.strip()
        url_limpa = url_original.replace("http://", "").replace("https://", "")
        protocolo = "https://" if "https://" in url_original else "http://"

        if "player_api.php" in url_original:
            partes = url_original.split("player_api.php")[0]
            base = partes.rstrip("/")
            if "username=" in url_original and "password=" in url_original:
                params = url_original.split("?")[1] if "?" in url_original else ""
                user, pwd = "", ""
                for p in params.split("&"):
                    if p.startswith("username="):
                        user = p.split("=", 1)[1]
                    elif p.startswith("password="):
                        pwd = p.split("=", 1)[1]
                return f"{base}/player_api.php", user, pwd
            return None, None, None

        if "get.php" in url_original:
            partes = url_original.split("get.php")[0]
            base = partes.rstrip("/")
            if "username=" in url_original and "password=" in url_original:
                params = url_original.split("?")[1] if "?" in url_original else ""
                user, pwd = "", ""
                for p in params.split("&"):
                    if p.startswith("username="):
                        user = p.split("=", 1)[1]
                    elif p.startswith("password="):
                        pwd = p.split("=", 1)[1]
                return f"{base}/player_api.php", user, pwd
            return None, None, None

        if "/live/" in url_original or "/movie/" in url_original or "/series/" in url_original:
            segmentos = url_limpa.split("/")
            if len(segmentos) >= 4:
                host_port = segmentos[0]
                tipo_idx = -1
                for i, seg in enumerate(segmentos):
                    if seg in ("live", "movie", "series"):
                        tipo_idx = i
                        break
                if tipo_idx >= 0 and len(segmentos) > tipo_idx + 2:
                    user = segmentos[tipo_idx + 1]
                    pwd = segmentos[tipo_idx + 2]
                    base = f"{protocolo}{host_port}"
                    return f"{base}/player_api.php", user, pwd
            return None, None, None

        if ".m3u" in url_original and "username=" in url_original:
            partes = url_original.split("?")[0]
            base = partes.rsplit("/", 1)[0] if "/" in partes else partes
            params = url_original.split("?")[1] if "?" in url_original else ""
            user, pwd = "", ""
            for p in params.split("&"):
                if p.startswith("username="):
                    user = p.split("=", 1)[1]
                elif p.startswith("password="):
                    pwd = p.split("=", 1)[1]
            if user and pwd:
                return f"{base}/player_api.php", user, pwd

        return None, None, None
    except Exception:
        return None, None, None


def obter_stream_base(server, username, password) -> str | None:
    """Obtém a URL base do stream."""
    s = nova_session()
    try:
        server_clean = server.replace("http://", "").replace("https://", "")
        base_url = f"http://{server_clean}/player_api.php"
        streams_url = f"{base_url}?username={username}&password={password}&action=get_live_streams"
        try:
            r = s.get(streams_url, timeout=7)
            streams = r.json()
        except Exception:
            return None

        if not streams or not isinstance(streams, list):
            return None

        formatos = ["ts", "m3u8"]
        for stream in streams[:5]:
            stream_id = stream.get("stream_id")
            if not stream_id:
                continue
            for fmt in formatos:
                stream_url = f"http://{server_clean}/live/{username}/{password}/{stream_id}.{fmt}"
                try:
                    r2 = s.get(stream_url, timeout=6, stream=True, allow_redirects=True)
                    url_final = r2.url
                    r2.close()
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url_final)
                        if parsed.scheme and parsed.hostname:
                            if parsed.port:
                                return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                            else:
                                return f"{parsed.scheme}://{parsed.hostname}"
                    except Exception:
                        url_sem_proto = url_final.split("://", 1)
                        if len(url_sem_proto) == 2:
                            proto = url_sem_proto[0]
                            resto = url_sem_proto[1]
                            servidor_porta = resto.split("/", 1)[0]
                            return f"{proto}://{servidor_porta}"
                except Exception:
                    continue
        return None
    except Exception:
        return None
    finally:
        s.close()


def dados_completos(userinfo, criado, expira) -> bool:
    campos = [
        userinfo.get("username"),
        userinfo.get("password"),
        criado, expira,
        userinfo.get("max_connections"),
        userinfo.get("active_cons")
    ]
    for c in campos:
        if c is None or str(c).strip() == "" or str(c) == "N/A":
            return False
    return True


def testar_servidor(server: str, username: str, password: str, estado: EstadoMigracao) -> dict | None:
    """Testa um servidor IPTV — função principal do migrador."""
    # Verifica pausa/stop
    estado.aguardar_pause()
    if estado.parado:
        return None

    server = server.replace("http://", "").replace("https://", "")
    base_url = f"http://{server}/player_api.php"
    auth_url = f"{base_url}?username={username}&password={password}"

    s = nova_session()
    try:
        r = s.get(auth_url, timeout=8)
        data = r.json()
    except Exception:
        estado.add_fail()
        estado.incrementar()
        return None
    finally:
        s.close()

    if "user_info" not in data or data["user_info"].get("auth") != 1:
        estado.add_fail()
        estado.incrementar()
        return None

    userinfo = data["user_info"]
    serverinfo = data.get("server_info", {})
    criado = formatar_data_ts(userinfo.get("created_at", 0))
    expira = formatar_data_ts(userinfo.get("exp_date", 0))
    live, vod, series = contar_conteudo(base_url, username, password)
    url_server = serverinfo.get("url", "N/A")

    def safe(v):
        return str(v) if v is not None else "N/A"

    m3u_link = (
        f"http://{server}/get.php?username={safe(userinfo.get('username'))}"
        f"&password={safe(userinfo.get('password'))}&type=m3u"
    )

    # Obter stream base
    stream_base = obter_stream_base(server, username, password)

    resultado = {
        "server": server,
        "username": safe(userinfo.get('username')),
        "password": safe(userinfo.get('password')),
        "criado": criado,
        "expira": expira,
        "max_conn": safe(userinfo.get('max_connections')),
        "active_conn": safe(userinfo.get('active_cons')),
        "live": live,
        "vod": vod,
        "series": series,
        "url_server": url_server,
        "m3u_link": m3u_link,
        "stream_base": stream_base,
        "timezone": safe(serverinfo.get('timezone')),
        "hora_atual": safe(serverinfo.get('time_now'))
    }

    estado.add_hit()
    estado.incrementar()
    return resultado


def worker_migracao(hosts_bloco: list, username: str, password: str, estado: EstadoMigracao):
    """Worker thread do migrador — com suporte a pausa/stop."""
    for srv in hosts_bloco:
        if estado.parado:
            break
        resultado = testar_servidor(srv, username, password, estado)
        # resultado já é adicionado dentro de testar_servidor via estado.add_hit()


# ══════════════════════════════════════════════
# 🎨  FORMATAÇÃO PROFISSIONAL
# ══════════════════════════════════════════════

def barra_progresso(pct: int) -> str:
    """Gera barra de progresso visual."""
    total = 20
    preenchido = int(total * pct / 100)
    vazio = total - preenchido
    barra = "█" * preenchido + "░" * vazio
    return f"[{barra}] {pct}%"


def formatar_cabecalho_migracao(estado: EstadoMigracao) -> str:
    """Formata cabeçalho da migração com dados do solicitante."""
    status_emoji = {
        "executando": "🔄",
        "pausado": "⏸️",
        "parado": "⏹️",
        "finalizado": "✅"
    }
    emoji = status_emoji.get(estado.status, "🔄")
    status_txt = estado.status.upper()

    return f"""══════════════════════════════

👤 **Usuário solicitante:**
╔══════════
║ 📛 Nome: `{estado.user_name}`
║ 🔢 ID: `{estado.user_id}`
║ 🆔 Username: `{estado.user_username}`
╚══════════

╔══════════════════════════════╗
║  {emoji} **MIGRAÇÃO IPTV {status_txt}**  ║
╚══════════════════════════════╝

👤 User/Pass: `{estado.username}:{estado.password}`
🔄 MIGRAÇÃO EM: Processando...

✅️ HITS: **{estado.hits}** | ❌️ OFF: **{estado.fails}**

⏳ {barra_progresso(estado.progresso)}

══════════════════════════════"""


def formatar_resultado_hit(resultado: dict) -> str:
    """Formata um resultado hit completo."""
    stream_line = f"\n🔰 **URL BASE:** `{resultado['stream_base']}`" if resultado.get('stream_base') else ""

    return f"""╔══════════════════════════════╗
║  🟢 **HIT — SERVIDOR ATIVO**    ║
╚══════════════════════════════╝

👤 **Usuário:** `{resultado['username']}`
🔑 **Senha:** `{resultado['password']}`
📅 **Criado:** `{resultado['criado']}`
⏰ **Expira:** `{resultado['expira']}`
🔗 **Conexões Max:** `{resultado['max_conn']}`
📡 **Conexões Ativas:** `{resultado['active_conn']}`
📺 **Canais:** {resultado['live']}
🎬 **Filmes:** {resultado['vod']}
📺 **Séries:** {resultado['series']}
🌍 **Timezone:** `{resultado['timezone']}`
🕒 **Hora Atual:** `{resultado['hora_atual']}`
🌐 **HOST:** `{resultado['server']}`
🔎 **URL:** `{resultado['url_server']}`
🔗 **M3U:** `{resultado['m3u_link']}`{stream_line}

▬▬▬ஜ۩𝑬𝒅𝒊𝒗𝒂𝒍𝒅𝒐۩ஜ▬▬▬"""


def formatar_resumo_final(estado: EstadoMigracao) -> str:
    """Formata resumo final da migração."""
    status = "FINALIZADA" if estado.status == "finalizado" else "INTERROMPIDA"

    return f"""══════════════════════════════

👤 **Solicitante:** `{estado.user_name}` (`{estado.user_id}`)

╔══════════════════════════════╗
║  {'✅' if estado.status == 'finalizado' else '⏹️'} **MIGRAÇÃO {status}!**    ║
╚══════════════════════════════╝

📊 **Resultado Final:**
├ ✅ Hits: **{estado.hits}**
├ ❌ Fails: **{estado.fails}**
├ 📡 Total processado: **{estado.processados}**
└ {barra_progresso(estado.progresso)}

👤 User/Pass: `{estado.username}:{estado.password}`
🕐 Início: `{estado.inicio}`
🕐 Fim: `{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}`

══════════════════════════════
_👨‍💻 Créditos: Edivaldo Silva @Edkd1_
_⚡ Powered by 773H Ultra_"""


def formatar_pagina_resultados(estado: EstadoMigracao, page: int) -> tuple:
    """Retorna (texto, total_pages) com resultados paginados."""
    total = len(estado.resultados)
    total_pages = max(1, (total + ITEMS_PER_PAGE_MIGRADOR - 1) // ITEMS_PER_PAGE_MIGRADOR)
    page = min(page, total_pages - 1)
    inicio = page * ITEMS_PER_PAGE_MIGRADOR
    fim = inicio + ITEMS_PER_PAGE_MIGRADOR
    chunk = estado.resultados[inicio:fim]

    text = (
        f"📋 **Resultados da Migração** — Pág. {page + 1}/{total_pages}\n"
        f"👤 Solicitante: `{estado.user_name}` | Total Hits: **{total}**\n\n"
    )

    for i, r in enumerate(chunk, inicio + 1):
        stream_info = f" | 🔰 `{r['stream_base']}`" if r.get('stream_base') else ""
        text += (
            f"**{i}.** `{r['server']}`\n"
            f"   👤 `{r['username']}:{r['password']}`\n"
            f"   📅 Expira: `{r['expira']}` | "
            f"📺 {r['live']} | 🎬 {r['vod']} | 📺 {r['series']}{stream_info}\n\n"
        )

    if not chunk:
        text += "_Nenhum resultado encontrado._\n"

    return text, page, total_pages


# ══════════════════════════════════════════════
# 💾  SALVAR RESULTADOS LOCALMENTE
# ══════════════════════════════════════════════

def salvar_resultados_usuario(estado: EstadoMigracao):
    """Salva resultados da migração em arquivo local do usuário."""
    user_dir = os.path.join(MIGRADOR_DATA_DIR, str(estado.user_id))
    os.makedirs(user_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = os.path.join(user_dir, f"migracao_{timestamp}.txt")

    try:
        with open(arquivo, 'w', encoding='utf-8') as f:
            f.write(f"═══ MIGRAÇÃO IPTV ═══\n")
            f.write(f"Solicitante: {estado.user_name} ({estado.user_id})\n")
            f.write(f"Credenciais: {estado.username}:{estado.password}\n")
            f.write(f"Início: {estado.inicio}\n")
            f.write(f"Fim: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Hits: {estado.hits} | Fails: {estado.fails}\n")
            f.write(f"{'═' * 40}\n\n")

            for r in estado.resultados:
                f.write(formatar_resultado_hit(r) + "\n\n")
    except IOError:
        pass

    # Salvar também um JSON estruturado
    json_file = os.path.join(user_dir, f"migracao_{timestamp}.json")
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "user_id": estado.user_id,
                "user_name": estado.user_name,
                "credenciais": f"{estado.username}:{estado.password}",
                "inicio": estado.inicio,
                "fim": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "hits": estado.hits,
                "fails": estado.fails,
                "resultados": estado.resultados
            }, f, indent=2, ensure_ascii=False)
    except IOError:
        pass


# ══════════════════════════════════════════════
# 🚀  EXECUÇÃO DA MIGRAÇÃO (ASYNC)
# ══════════════════════════════════════════════

async def executar_migracao(bot_client, estado: EstadoMigracao):
    """Executa migração IPTV completa com atualização em tempo real."""
    from botoes import migrador_controle_buttons, voltar_button
    from grupo import log

    hosts = carregar_hosts()
    if not hosts:
        await bot_client.send_message(
            estado.chat_id,
            "❌ **Nenhum servidor encontrado!**\n\n"
            "📁 Adicione servidores ao arquivo `hosts.txt`.",
            parse_mode='md'
        )
        remover_migracao(estado.user_id)
        return

    estado.total_hosts = len(hosts)
    registrar_migracao(estado)

    log(f"🔄 Migração iniciada por {estado.user_name} ({estado.user_id}): {estado.username}:***")

    # Mensagem inicial de progresso
    msg = await bot_client.send_message(
        estado.chat_id,
        formatar_cabecalho_migracao(estado),
        parse_mode='md',
        buttons=migrador_controle_buttons(estado.user_id)
    )
    estado.msg_id = msg.id

    # Executar em threads
    partes = 10
    tamanho = max(1, len(hosts) // partes)
    threads = []

    for i in range(partes):
        bloco = hosts[i * tamanho:(i + 1) * tamanho]
        if bloco:
            t = threading.Thread(
                target=worker_migracao,
                args=(bloco, estado.username, estado.password, estado)
            )
            t.start()
            threads.append(t)

    resto = hosts[partes * tamanho:]
    if resto:
        t = threading.Thread(
            target=worker_migracao,
            args=(resto, estado.username, estado.password, estado)
        )
        t.start()
        threads.append(t)

    # Atualizar progresso a cada 5 segundos
    ultimo_progresso = -1
    while any(t.is_alive() for t in threads):
        await asyncio.sleep(5)

        if estado.parado:
            break

        if estado.progresso != ultimo_progresso:
            ultimo_progresso = estado.progresso
            try:
                await bot_client.edit_message(
                    estado.chat_id, estado.msg_id,
                    formatar_cabecalho_migracao(estado),
                    parse_mode='md',
                    buttons=migrador_controle_buttons(estado.user_id)
                )
            except Exception:
                pass

    # Aguardar todas finalizarem
    def join_all():
        for t in threads:
            t.join(timeout=30)

    await asyncio.get_event_loop().run_in_executor(None, join_all)

    # Finalizar
    if estado.status != "parado":
        estado.status = "finalizado"

    # Atualizar mensagem final
    try:
        await bot_client.edit_message(
            estado.chat_id, estado.msg_id,
            formatar_cabecalho_migracao(estado),
            parse_mode='md',
            buttons=migrador_controle_buttons(estado.user_id)
        )
    except Exception:
        pass

    # Enviar todos os resultados completos
    for r in estado.resultados:
        try:
            await bot_client.send_message(
                estado.chat_id,
                formatar_resultado_hit(r),
                parse_mode='md'
            )
            await asyncio.sleep(0.5)  # Anti-flood
        except Exception:
            pass

    # Resumo final
    await bot_client.send_message(
        estado.chat_id,
        formatar_resumo_final(estado),
        parse_mode='md',
        buttons=[
            [__import__('telethon', fromlist=['Button']).Button.inline(
                "📋 Ver Resultados", f"migra_res_{estado.user_id}_0".encode()
            )] if estado.resultados else [],
            [__import__('telethon', fromlist=['Button']).Button.inline(
                "🔙 Menu Principal", b"cmd_menu"
            )]
        ]
    )

    # Salvar resultados localmente
    salvar_resultados_usuario(estado)
    registrar_usuario_interacao(
        estado.user_id, estado.user_name, estado.user_username,
        f"Migração finalizada: {estado.hits} hits / {estado.fails} fails"
    )

    log(f"✅ Migração finalizada para {estado.user_name}: {estado.hits} hits, {estado.fails} fails")
    remover_migracao(estado.user_id)


# ══════════════════════════════════════════════
# 🔍  DETECÇÃO DE CREDENCIAIS / CPF
# ══════════════════════════════════════════════

def extrair_cpf(texto: str) -> str:
    """Extrai CPF de uma mensagem."""
    match = re.search(r'(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2})', texto)
    if match:
        return re.sub(r'[.\-/\s]', '', match.group(1))
    match = re.search(r'(\d{11})', texto)
    if match:
        return match.group(1)
    return ""


def extrair_credenciais(texto: str) -> tuple:
    """Extrai credenciais no formato user:pass."""
    texto = texto.strip()
    if ":" in texto:
        partes = texto.split(":", 1)
        user = partes[0].strip()
        pwd = partes[1].strip()
        if user and pwd and " " not in user:
            return user, pwd
    return None, None


def detectar_formato_resposta(texto: str) -> str:
    """Detecta se a resposta é CPF ou credencial IPTV.
    Retorna: 'cpf', 'credencial', ou 'desconhecido'
    """
    texto = texto.strip()

    # Tenta CPF primeiro
    cpf = extrair_cpf(texto)
    if cpf and len(cpf) == 11:
        return "cpf"

    # Tenta credencial
    user, pwd = extrair_credenciais(texto)
    if user and pwd:
        return "credencial"

    return "desconhecido"
