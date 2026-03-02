# ══════════════════════════════════════════════
# 🔍  CONSULTA IPTV — INFO BOT PRO V4.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
#
# Funções de consulta IPTV preservadas 100% do
# EuBot3.py original + melhorias profissionais.
# ══════════════════════════════════════════════

import os
import re
import random
import socket
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from requests.sessions import Session

# ── URL Pattern ──
URL_PATTERN = r'(https?://[^\s]+)'


# ══════════════════════════════════════
# 🔧  FUNÇÕES AUXILIARES (PRESERVADAS)
# ══════════════════════════════════════

def format_date(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return "N/D"


def fetch_data(session, url):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (Linux; Android 10)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6)",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64)"
    ]
    headers = {'User-Agent': random.choice(user_agents)}
    try:
        response = session.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def is_port_open(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            return sock.connect_ex((host, port)) == 0
    except socket.error:
        return False


def get_host_ip(host):
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


# ══════════════════════════════════════
# 🌐  CONSULTA URL IPTV (PRESERVADA)
# ══════════════════════════════════════

def check_url(url):
    """Consulta completa de URL IPTV — preservada 100% do EuBot3.py."""
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    port = parsed_url.port or 80
    query_params = parse_qs(parsed_url.query)
    username = query_params.get('username', [None])[0]
    password = query_params.get('password', [None])[0]

    if not (host and username and password):
        return None, "❌ URL inválida. Faltam parâmetros (username/password)."

    ip_address = get_host_ip(host)
    if not ip_address:
        return None, f"❌ Não foi possível resolver o host: {host}"

    if not is_port_open(host, port):
        return None, f"❌ Porta {port} fechada em {host}"

    api_url = f'http://{host}:{port}/player_api.php?username={username}&password={password}'

    try:
        with Session() as session:
            data = fetch_data(session, api_url)
            if not data:
                return None, "❌ Servidor OFF ou sem resposta."

            user_info = data.get('user_info', {})
            if user_info.get('auth') == 0:
                return None, "❌ Credenciais inválidas (auth=0)."

            live = fetch_data(session, f'{api_url}&action=get_live_streams')
            vod = fetch_data(session, f'{api_url}&action=get_vod_streams')
            series = fetch_data(session, f'{api_url}&action=get_series')

            total_canais = len(live) if live else 0
            total_vods = len(vod) if vod else 0
            total_series = len(series) if series else 0

            return build_result(data, total_canais, total_vods, total_series, ip_address), None
    except Exception as e:
        return None, f"❌ Erro: {str(e)}"


def build_result(data, total_canais, total_vods, total_series, ip_address):
    """Formata resultado da consulta IPTV — preservado 100%."""
    ui = data['user_info']
    si = data['server_info']

    server = si.get('url', 'N/D')
    port = si.get('port', 'N/D')
    username = ui.get('username', 'N/D')
    password = ui.get('password', 'N/D')
    status = ui.get('status', 'N/D')
    creation = format_date(ui.get('created_at', 0))
    expiration = format_date(ui.get('exp_date', 0))
    max_conn = ui.get('max_connections', 'N/D')
    active_conn = ui.get('active_cons', 'N/D')
    formats = ', '.join(ui.get('allowed_output_formats', []))
    timezone = si.get('timezone', 'N/D')
    https_port = si.get('https_port', 'N/D')
    protocol = si.get('server_protocol', 'N/D')
    rtmp_port = si.get('rtmp_port', 'N/D')
    time_now = si.get('time_now', 'N/D')

    status_emoji = "✅" if status == "Active" else "❌"

    m3u_link = f"http://{server}:{port}/get.php?username={username}&password={password}&type=m3u"

    result = (
        f"╔══════════════════════════════╗\n"
        f"║  {status_emoji} RESULTADO DA CONSULTA     ║\n"
        f"╚══════════════════════════════╝\n"
        f"\n"
        f"📊 **Status:** `{status}`\n"
        f"👤 **Usuário:** `{username}`\n"
        f"🔑 **Senha:** `{password}`\n"
        f"\n"
        f"📅 **Criação:** `{creation}`\n"
        f"⏰ **Expiração:** `{expiration}`\n"
        f"\n"
        f"🔗 **Conexões:** `{active_conn}/{max_conn}`\n"
        f"\n"
        f"🌐 **Host:** `{server}`\n"
        f"🔌 **Porta:** `{port}`\n"
        f"📡 **IP:** `{ip_address}`\n"
        f"🔒 **HTTPS:** `{https_port}`\n"
        f"📶 **Protocolo:** `{protocol}`\n"
        f"📺 **RTMP:** `{rtmp_port}`\n"
        f"🕐 **Hora:** `{time_now}`\n"
        f"🌍 **Timezone:** `{timezone}`\n"
        f"\n"
        f"📂 **Formato:** `{formats}`\n"
        f"📺 **Canais:** `{total_canais}`\n"
        f"🎬 **Filmes:** `{total_vods}`\n"
        f"🎭 **Séries:** `{total_series}`\n"
        f"\n"
        f"🔗 **M3U:**\n`{m3u_link}`\n"
        f"\n"
        f"╚══════════════════════════════╝"
    )
    return result


# ══════════════════════════════════════
# 📄  CONSULTA CPF
# ══════════════════════════════════════

CPF_PATTERN = r'^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$'


def validar_cpf(cpf_str: str) -> bool:
    """Valida formato de CPF."""
    cpf = re.sub(r'\D', '', cpf_str)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False
    # Validação dos dígitos verificadores
    for i in range(9, 11):
        soma = sum(int(cpf[j]) * ((i + 1) - j) for j in range(i))
        digito = (soma * 10 % 11) % 10
        if int(cpf[i]) != digito:
            return False
    return True


def formatar_cpf(cpf_str: str) -> str:
    """Formata CPF como XXX.XXX.XXX-XX."""
    cpf = re.sub(r'\D', '', cpf_str)
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf_str


def detectar_tipo_entrada(texto: str) -> str:
    """Detecta se a entrada é URL, CPF ou texto genérico."""
    texto = texto.strip()
    if re.match(URL_PATTERN, texto):
        return "url"
    cpf_limpo = re.sub(r'\D', '', texto)
    if len(cpf_limpo) == 11 and cpf_limpo.isdigit():
        return "cpf"
    return "texto"
