import telebot
import requests
from urllib.parse import urlparse, parse_qs
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import os
import asyncio
from datetime import datetime, timedelta

# ========== DEPENDÊNCIAS OPCIONAIS (Pyrogram) ==========
PYROGRAM_AVAILABLE = False
try:
    from pyrogram import Client
    from pyrogram.enums import ParseMode, ChatType, UserStatus
    from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied, ChannelInvalid
    from dateutil.relativedelta import relativedelta
    PYROGRAM_AVAILABLE = True
except ImportError:
    pass

# Arquivo para salvar configurações
CONFIG_FILE = 'bot_config.json'

# ========== FUNÇÕES DE INFORMAÇÃO DO TELEGRAM ==========
# Créditos: Edivaldo Silva @Edkd1

def get_dc_locations():
    return {
        1: "MIA, Miami, USA, US",
        2: "AMS, Amsterdam, Netherlands, NL",
        3: "MBA, Mumbai, India, IN",
        4: "STO, Stockholm, Sweden, SE",
        5: "SIN, Singapore, SG",
        6: "LHR, London, United Kingdom, GB",
        7: "FRA, Frankfurt, Germany, DE",
        8: "JFK, New York, USA, US",
        9: "HKG, Hong Kong, HK",
        10: "TYO, Tokyo, Japan, JP",
        11: "SYD, Sydney, Australia, AU",
        12: "GRU, São Paulo, Brazil, BR",
        13: "DXB, Dubai, UAE, AE",
        14: "CDG, Paris, France, FR",
        15: "ICN, Seoul, South Korea, KR",
    }

def calculate_account_age(creation_date):
    today = datetime.now()
    delta = relativedelta(today, creation_date)
    years = delta.years
    months = delta.months
    days = delta.days
    return f"{years} anos, {months} meses, {days} dias"

def estimate_account_creation_date(user_id):
    reference_points = [
        (100000000, datetime(2013, 8, 1)),
        (1273841502, datetime(2020, 8, 13)),
        (1500000000, datetime(2021, 5, 1)),
        (2000000000, datetime(2022, 12, 1)),
    ]
    closest_point = min(reference_points, key=lambda x: abs(x[0] - user_id))
    closest_user_id, closest_date = closest_point
    id_difference = user_id - closest_user_id
    days_difference = id_difference / 20000000
    creation_date = closest_date + timedelta(days=days_difference)
    return creation_date

def format_user_status(status):
    if not status:
        return "Desconhecido"
    status_map = {
        UserStatus.ONLINE: "🟢 Online",
        UserStatus.OFFLINE: "⚫ Offline",
        UserStatus.RECENTLY: "🔵 Recentemente online",
        UserStatus.LAST_WEEK: "🟡 Visto na última semana",
        UserStatus.LAST_MONTH: "🟠 Visto no último mês",
        UserStatus.LONG_AGO: "🔴 Visto há muito tempo"
    }
    return status_map.get(status, "Desconhecido")

def get_profile_photo_url(username, size=320):
    if username:
        username = username.strip('@')
        return f"https://t.me/i/userpic/{size}/{username}.jpg"
    return None

def format_usernames_list(usernames):
    if not usernames:
        return []
    formatted_usernames = []
    for username_obj in usernames:
        if hasattr(username_obj, 'username'):
            formatted_usernames.append(f"@{username_obj.username}")
        else:
            formatted_usernames.append(str(username_obj))
    return formatted_usernames

async def get_user_info_pyrogram(pyrogram_client, username):
    """Obtém informações detalhadas de um usuário do Telegram via Pyrogram"""
    try:
        DC_LOCATIONS = get_dc_locations()
        user = await pyrogram_client.get_users(username)
        full_user = await pyrogram_client.get_chat(username)
        bio = getattr(full_user, 'bio', None)

        premium_status = getattr(user, 'is_premium', False)
        dc_location = DC_LOCATIONS.get(user.dc_id, "Desconhecido")
        account_created = estimate_account_creation_date(user.id)
        account_created_str = account_created.strftime("%d/%m/%Y")
        account_age = calculate_account_age(account_created)
        verified_status = getattr(user, 'is_verified', False)
        status = format_user_status(getattr(user, 'status', None))

        flags = "✅ Limpo"
        if getattr(user, 'is_scam', False):
            flags = "🚨 Scam"
        elif getattr(user, 'is_fake', False):
            flags = "⚠️ Fake"

        profile_photo_url = get_profile_photo_url(user.username) if user.username else None
        usernames_list = format_usernames_list(getattr(user, 'usernames', []))

        last_online_date = None
        if hasattr(user, 'last_online_date') and user.last_online_date:
            last_online_date = user.last_online_date.strftime("%d/%m/%Y às %H:%M:%S")

        return {
            "success": True,
            "type": "bot" if user.is_bot else "user",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "usernames": usernames_list,
            "bio": bio,
            "dc_id": user.dc_id,
            "dc_location": dc_location,
            "is_premium": premium_status,
            "is_verified": verified_status,
            "is_bot": user.is_bot,
            "is_scam": getattr(user, 'is_scam', False),
            "is_fake": getattr(user, 'is_fake', False),
            "flags": flags,
            "status": status,
            "last_online_date": last_online_date,
            "account_created": account_created_str,
            "account_age": account_age,
            "profile_photo_url": profile_photo_url,
            "links": {
                "android": f"tg://openmessage?user_id={user.id}",
                "ios": f"tg://user?id={user.id}",
                "permanent": f"tg://user?id={user.id}"
            }
        }
    except (PeerIdInvalid, UsernameNotOccupied, IndexError):
        return {"success": False, "error": "Usuário não encontrado"}
    except Exception as e:
        return {"success": False, "error": f"Erro ao buscar informações: {str(e)}"}

async def get_chat_info_pyrogram(pyrogram_client, username):
    """Obtém informações detalhadas de um canal/grupo do Telegram via Pyrogram"""
    try:
        DC_LOCATIONS = get_dc_locations()
        chat = await pyrogram_client.get_chat(username)

        chat_type_map = {
            ChatType.SUPERGROUP: "supergrupo",
            ChatType.GROUP: "grupo",
            ChatType.CHANNEL: "canal"
        }
        chat_type = chat_type_map.get(chat.type, "desconhecido")
        dc_location = DC_LOCATIONS.get(getattr(chat, 'dc_id', None), "Desconhecido")
        profile_photo_url = get_profile_photo_url(chat.username) if chat.username else None
        usernames_list = format_usernames_list(getattr(chat, 'usernames', []))

        if chat.username:
            join_link = f"t.me/{chat.username}"
        elif chat.id < 0:
            chat_id_str = str(chat.id).replace('-100', '')
            join_link = f"t.me/c/{chat_id_str}/1"
        else:
            join_link = f"tg://resolve?domain={chat.id}"

        flags = "✅ Limpo"
        if getattr(chat, 'is_scam', False):
            flags = "🚨 Scam"
        elif getattr(chat, 'is_fake', False):
            flags = "⚠️ Fake"

        return {
            "success": True,
            "type": chat_type,
            "id": chat.id,
            "title": chat.title,
            "username": chat.username,
            "usernames": usernames_list,
            "description": getattr(chat, 'description', None),
            "dc_id": getattr(chat, 'dc_id', None),
            "dc_location": dc_location,
            "members_count": getattr(chat, 'members_count', None),
            "is_verified": getattr(chat, 'is_verified', False),
            "is_restricted": getattr(chat, 'is_restricted', False),
            "is_scam": getattr(chat, 'is_scam', False),
            "is_fake": getattr(chat, 'is_fake', False),
            "flags": flags,
            "profile_photo_url": profile_photo_url,
            "links": {
                "join": join_link
            }
        }
    except (ChannelInvalid, PeerIdInvalid):
        return {"success": False, "error": "Chat não encontrado ou acesso negado"}
    except Exception as e:
        return {"success": False, "error": f"Erro ao buscar informações: {str(e)}"}

async def get_telegram_info(pyrogram_client, username):
    """Busca informações de qualquer entidade do Telegram"""
    username = username.strip('@').replace('https://', '').replace('http://', '').replace('t.me/', '').replace('/', '').replace(':', '')
    
    user_info = await get_user_info_pyrogram(pyrogram_client, username)
    if user_info["success"]:
        return user_info

    chat_info = await get_chat_info_pyrogram(pyrogram_client, username)
    if chat_info["success"]:
        return chat_info

    return {"success": False, "error": "Entidade não encontrada no Telegram"}

def format_user_response(data):
    """Formata a resposta de informações de usuário para exibição no Telegram"""
    entity_type = data.get("type", "desconhecido")
    
    if entity_type in ["user", "bot"]:
        tipo_emoji = "🤖" if entity_type == "bot" else "👤"
        tipo_texto = "Bot" if entity_type == "bot" else "Usuário"
        
        name = data.get("first_name", "")
        if data.get("last_name"):
            name += f" {data['last_name']}"
        
        text = f"{'▬' * 15}\n"
        text += f"{tipo_emoji} *Informações do {tipo_texto}*\n"
        text += f"{'▬' * 15}\n\n"
        text += f"📛 *Nome:* {name}\n"
        text += f"🆔 *ID:* `{data['id']}`\n"
        
        if data.get("username"):
            text += f"📎 *Username:* @{data['username']}\n"
        
        if data.get("usernames") and len(data["usernames"]) > 0:
            text += f"📋 *Usernames:* {', '.join(data['usernames'])}\n"
        
        if data.get("bio"):
            text += f"📝 *Bio:* {data['bio']}\n"
        
        text += f"\n🌐 *Data Center:* DC{data.get('dc_id', '?')} - {data.get('dc_location', 'Desconhecido')}\n"
        text += f"📅 *Conta criada:* {data.get('account_created', 'Desconhecido')}\n"
        text += f"⏳ *Idade da conta:* {data.get('account_age', 'Desconhecido')}\n"
        text += f"📡 *Status:* {data.get('status', 'Desconhecido')}\n"
        
        if data.get("last_online_date"):
            text += f"🕐 *Último online:* {data['last_online_date']}\n"
        
        text += f"\n💎 *Premium:* {'✅ Sim' if data.get('is_premium') else '❌ Não'}\n"
        text += f"✅ *Verificado:* {'✅ Sim' if data.get('is_verified') else '❌ Não'}\n"
        text += f"🏴 *Flags:* {data.get('flags', 'Limpo')}\n"
        
        if data.get("links"):
            text += f"\n🔗 *Links:*\n"
            text += f"  📱 Android: `{data['links'].get('android', '')}`\n"
            text += f"  🍎 iOS: `{data['links'].get('ios', '')}`\n"
        
        text += f"\n{'▬' * 5}ஜ۩ *@Edkd1* ۩ஜ{'▬' * 5}"
        return text
    
    elif entity_type in ["canal", "grupo", "supergrupo", "channel", "group", "supergroup"]:
        tipo_emoji = "📢" if "canal" in entity_type or "channel" in entity_type else "👥"
        tipo_texto = entity_type.capitalize()
        
        text = f"{'▬' * 15}\n"
        text += f"{tipo_emoji} *Informações do {tipo_texto}*\n"
        text += f"{'▬' * 15}\n\n"
        text += f"📛 *Título:* {data.get('title', 'Sem título')}\n"
        text += f"🆔 *ID:* `{data['id']}`\n"
        
        if data.get("username"):
            text += f"📎 *Username:* @{data['username']}\n"
        
        if data.get("usernames") and len(data["usernames"]) > 0:
            text += f"📋 *Usernames:* {', '.join(data['usernames'])}\n"
        
        if data.get("description"):
            text += f"📝 *Descrição:* {data['description']}\n"
        
        if data.get("members_count"):
            text += f"👥 *Membros:* {data['members_count']:,}\n"
        
        text += f"\n🌐 *Data Center:* DC{data.get('dc_id', '?')} - {data.get('dc_location', 'Desconhecido')}\n"
        text += f"✅ *Verificado:* {'✅ Sim' if data.get('is_verified') else '❌ Não'}\n"
        text += f"🔒 *Restrito:* {'⚠️ Sim' if data.get('is_restricted') else '❌ Não'}\n"
        text += f"🏴 *Flags:* {data.get('flags', 'Limpo')}\n"
        
        if data.get("links"):
            join_link = data['links'].get('join', '')
            if join_link:
                text += f"\n🔗 *Link:* https://{join_link}\n"
        
        text += f"\n{'▬' * 5}ஜ۩ *@Edkd1* ۩ஜ{'▬' * 5}"
        return text
    
    return "❌ Tipo de entidade desconhecido."


class BotConfigGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Bot Telegram - Painel de Controle")
        self.root.geometry("900x750")
        self.root.configure(bg='#1a1a2e')
        self.root.resizable(True, True)
        
        # Variáveis
        self.bot = None
        self.bot_running = False
        self.bot_thread = None
        self.user_logs = []
        self.sent_results = {}
        self.banned_users = set()
        self.admin_users = set()
        self.user_warnings = {}
        self.pyrogram_client = None
        self.pyrogram_loop = None
        
        # Carregar configurações salvas
        self.load_config()
        
        # Criar interface
        self.create_widgets()
        
    def load_config(self):
        """Carrega configurações salvas do arquivo JSON"""
        self.saved_config = {
            'token': '',
            'owner_id': '',
            'results_group_id': '',
            'channel_id': '',
            'api_id': '',
            'api_hash': ''
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.saved_config = json.load(f)
            except:
                pass
                
    def save_config(self):
        """Salva configurações no arquivo JSON"""
        config = {
            'token': self.token_entry.get(),
            'owner_id': self.owner_entry.get(),
            'results_group_id': self.group_entry.get(),
            'channel_id': self.channel_entry.get(),
            'api_id': self.api_id_entry.get(),
            'api_hash': self.api_hash_entry.get()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        self.log_console("✅ Configurações salvas com sucesso!")
        
    def create_widgets(self):
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#1a1a2e', foreground='#ffffff', font=('Segoe UI', 10))
        style.configure('TEntry', fieldbackground='#16213e', foreground='#ffffff', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#e94560')
        style.configure('Required.TLabel', foreground='#e94560')
        style.configure('Optional.TLabel', foreground='#4ecca3')
        
        # Frame principal com scroll
        canvas = tk.Canvas(self.root, bg='#1a1a2e', highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = scrollable_frame
        main_frame_inner = tk.Frame(main_frame, bg='#1a1a2e')
        main_frame_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # ========== HEADER ==========
        header_frame = tk.Frame(main_frame_inner, bg='#1a1a2e')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(header_frame, text="🤖 Bot Telegram - Checker M3U & Info", 
                              font=('Segoe UI', 18, 'bold'), bg='#1a1a2e', fg='#e94560')
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame, text="Painel de Configuração e Controle | Créditos: Edivaldo Silva @Edkd1", 
                                 font=('Segoe UI', 10), bg='#1a1a2e', fg='#888888')
        subtitle_label.pack()
        
        # ========== CONFIGURAÇÕES PRINCIPAIS ==========
        config_frame = tk.LabelFrame(main_frame_inner, text=" ⚙️ Configurações Principais ", 
                                    font=('Segoe UI', 12, 'bold'), bg='#16213e', fg='#ffffff',
                                    relief=tk.RIDGE, bd=2)
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        fields_frame = tk.Frame(config_frame, bg='#16213e')
        fields_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Token do Bot (OBRIGATÓRIO)
        token_frame = tk.Frame(fields_frame, bg='#16213e')
        token_frame.pack(fill=tk.X, pady=5)
        
        token_label = tk.Label(token_frame, text="🔑 Token do Bot:", 
                              font=('Segoe UI', 10, 'bold'), bg='#16213e', fg='#e94560')
        token_label.pack(side=tk.LEFT)
        
        required_label1 = tk.Label(token_frame, text="(OBRIGATÓRIO)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#ff6b6b')
        required_label1.pack(side=tk.LEFT, padx=5)
        
        self.token_entry = tk.Entry(fields_frame, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                   insertbackground='#ffffff', relief=tk.FLAT, width=70)
        self.token_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.token_entry.insert(0, self.saved_config.get('token', ''))
        
        # ID do Dono (OBRIGATÓRIO)
        owner_frame = tk.Frame(fields_frame, bg='#16213e')
        owner_frame.pack(fill=tk.X, pady=5)
        
        owner_label = tk.Label(owner_frame, text="👑 ID do Dono:", 
                              font=('Segoe UI', 10, 'bold'), bg='#16213e', fg='#e94560')
        owner_label.pack(side=tk.LEFT)
        
        required_label2 = tk.Label(owner_frame, text="(OBRIGATÓRIO)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#ff6b6b')
        required_label2.pack(side=tk.LEFT, padx=5)
        
        self.owner_entry = tk.Entry(fields_frame, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                   insertbackground='#ffffff', relief=tk.FLAT, width=70)
        self.owner_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.owner_entry.insert(0, self.saved_config.get('owner_id', ''))
        
        # Separador
        separator = tk.Frame(fields_frame, height=2, bg='#4ecca3')
        separator.pack(fill=tk.X, pady=10)
        
        optional_title = tk.Label(fields_frame, text="📋 Campos Opcionais", 
                                 font=('Segoe UI', 10, 'bold'), bg='#16213e', fg='#4ecca3')
        optional_title.pack(anchor=tk.W, pady=(5, 10))
        
        # ID do Grupo de Resultados (OPCIONAL)
        group_frame = tk.Frame(fields_frame, bg='#16213e')
        group_frame.pack(fill=tk.X, pady=5)
        
        group_label = tk.Label(group_frame, text="📢 ID do Grupo de Resultados:", 
                              font=('Segoe UI', 10), bg='#16213e', fg='#4ecca3')
        group_label.pack(side=tk.LEFT)
        
        optional_label1 = tk.Label(group_frame, text="(opcional)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#888888')
        optional_label1.pack(side=tk.LEFT, padx=5)
        
        self.group_entry = tk.Entry(fields_frame, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                   insertbackground='#ffffff', relief=tk.FLAT, width=70)
        self.group_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.group_entry.insert(0, self.saved_config.get('results_group_id', ''))
        
        # ID do Canal (OPCIONAL)
        channel_frame = tk.Frame(fields_frame, bg='#16213e')
        channel_frame.pack(fill=tk.X, pady=5)
        
        channel_label = tk.Label(channel_frame, text="📺 ID do Canal:", 
                                font=('Segoe UI', 10), bg='#16213e', fg='#4ecca3')
        channel_label.pack(side=tk.LEFT)
        
        optional_label2 = tk.Label(channel_frame, text="(opcional)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#888888')
        optional_label2.pack(side=tk.LEFT, padx=5)
        
        self.channel_entry = tk.Entry(fields_frame, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                     insertbackground='#ffffff', relief=tk.FLAT, width=70)
        self.channel_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.channel_entry.insert(0, self.saved_config.get('channel_id', ''))
        
        # ========== CONFIGURAÇÕES PYROGRAM (para /info) ==========
        pyrogram_frame = tk.LabelFrame(main_frame_inner, text=" 🔍 Configurações de Consulta (/info) ", 
                                       font=('Segoe UI', 12, 'bold'), bg='#16213e', fg='#ffffff',
                                       relief=tk.RIDGE, bd=2)
        pyrogram_frame.pack(fill=tk.X, pady=(0, 15))
        
        pyro_fields = tk.Frame(pyrogram_frame, bg='#16213e')
        pyro_fields.pack(fill=tk.X, padx=15, pady=15)
        
        pyro_info = tk.Label(pyro_fields, 
                            text="⚡ Para usar o comando /info, preencha API ID e API Hash (my.telegram.org)", 
                            font=('Segoe UI', 9), bg='#16213e', fg='#ffd93d', wraplength=700, justify=tk.LEFT)
        pyro_info.pack(anchor=tk.W, pady=(0, 10))
        
        if not PYROGRAM_AVAILABLE:
            pyro_warn = tk.Label(pyro_fields, 
                                text="⚠️ Pyrogram não instalado! Execute: pip install pyrofork python-dateutil TgCrypto", 
                                font=('Segoe UI', 9, 'bold'), bg='#16213e', fg='#ff6b6b', wraplength=700, justify=tk.LEFT)
            pyro_warn.pack(anchor=tk.W, pady=(0, 10))
        
        # API ID
        api_id_frame = tk.Frame(pyro_fields, bg='#16213e')
        api_id_frame.pack(fill=tk.X, pady=5)
        
        api_id_label = tk.Label(api_id_frame, text="🔢 API ID:", 
                               font=('Segoe UI', 10, 'bold'), bg='#16213e', fg='#74b9ff')
        api_id_label.pack(side=tk.LEFT)
        
        optional_label3 = tk.Label(api_id_frame, text="(opcional - para /info)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#888888')
        optional_label3.pack(side=tk.LEFT, padx=5)
        
        self.api_id_entry = tk.Entry(pyro_fields, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                    insertbackground='#ffffff', relief=tk.FLAT, width=70)
        self.api_id_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.api_id_entry.insert(0, self.saved_config.get('api_id', ''))
        
        # API Hash
        api_hash_frame = tk.Frame(pyro_fields, bg='#16213e')
        api_hash_frame.pack(fill=tk.X, pady=5)
        
        api_hash_label = tk.Label(api_hash_frame, text="🔐 API Hash:", 
                                 font=('Segoe UI', 10, 'bold'), bg='#16213e', fg='#74b9ff')
        api_hash_label.pack(side=tk.LEFT)
        
        optional_label4 = tk.Label(api_hash_frame, text="(opcional - para /info)", 
                                  font=('Segoe UI', 8), bg='#16213e', fg='#888888')
        optional_label4.pack(side=tk.LEFT, padx=5)
        
        self.api_hash_entry = tk.Entry(pyro_fields, font=('Consolas', 10), bg='#0f0f23', fg='#ffffff',
                                      insertbackground='#ffffff', relief=tk.FLAT, width=70, show='•')
        self.api_hash_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.api_hash_entry.insert(0, self.saved_config.get('api_hash', ''))
        
        # ========== BOTÕES ==========
        buttons_frame = tk.Frame(main_frame_inner, bg='#1a1a2e')
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = tk.Button(buttons_frame, text="▶️ INICIAR BOT", font=('Segoe UI', 11, 'bold'),
                                  bg='#4ecca3', fg='#000000', activebackground='#3db892',
                                  relief=tk.FLAT, cursor='hand2', command=self.start_bot,
                                  padx=20, pady=10)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(buttons_frame, text="⏹️ PARAR BOT", font=('Segoe UI', 11, 'bold'),
                                 bg='#e94560', fg='#ffffff', activebackground='#c73e54',
                                 relief=tk.FLAT, cursor='hand2', command=self.stop_bot,
                                 state=tk.DISABLED, padx=20, pady=10)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = tk.Button(buttons_frame, text="💾 SALVAR CONFIG", font=('Segoe UI', 11, 'bold'),
                                 bg='#7b68ee', fg='#ffffff', activebackground='#6a5acd',
                                 relief=tk.FLAT, cursor='hand2', command=self.save_config,
                                 padx=20, pady=10)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = tk.Button(buttons_frame, text="🗑️ LIMPAR CONSOLE", font=('Segoe UI', 11, 'bold'),
                                  bg='#ff9f43', fg='#000000', activebackground='#f39c12',
                                  relief=tk.FLAT, cursor='hand2', command=self.clear_console,
                                  padx=20, pady=10)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = tk.Label(buttons_frame, text="⚫ Bot Offline", 
                                    font=('Segoe UI', 10, 'bold'), bg='#1a1a2e', fg='#888888')
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # ========== CONSOLE ==========
        console_frame = tk.LabelFrame(main_frame_inner, text=" 📟 Console ", 
                                     font=('Segoe UI', 12, 'bold'), bg='#16213e', fg='#ffffff',
                                     relief=tk.RIDGE, bd=2)
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.console = scrolledtext.ScrolledText(console_frame, font=('Consolas', 9), 
                                                 bg='#0f0f23', fg='#00ff00',
                                                 insertbackground='#00ff00',
                                                 relief=tk.FLAT, wrap=tk.WORD)
        self.console.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tags para cores no console
        self.console.tag_configure('error', foreground='#ff6b6b')
        self.console.tag_configure('success', foreground='#4ecca3')
        self.console.tag_configure('warning', foreground='#ffd93d')
        self.console.tag_configure('info', foreground='#74b9ff')
        
        # Mensagem inicial
        self.log_console("=" * 60)
        self.log_console("🤖 Bot Telegram - Checker M3U & Telegram Info")
        self.log_console("📌 Créditos: Edivaldo Silva @Edkd1")
        self.log_console("=" * 60)
        self.log_console("")
        self.log_console("📋 Instruções:")
        self.log_console("1. Preencha o Token do Bot (obrigatório)")
        self.log_console("2. Preencha o ID do Dono (obrigatório)")
        self.log_console("3. Preencha os IDs de Grupo/Canal (opcional)")
        self.log_console("4. Para /info: preencha API ID e API Hash (opcional)")
        self.log_console("5. Clique em 'INICIAR BOT' para começar")
        self.log_console("")
        self.log_console("📋 Comandos disponíveis:")
        self.log_console("  /start - Iniciar e ver comandos")
        self.log_console("  /Checker + URL - Verificar lista M3U")
        self.log_console("  /info + @username ou ID - Consultar info do Telegram")
        self.log_console("  /painel - Comandos administrativos")
        self.log_console("  /adms - Lista de administradores")
        self.log_console("")
        
    def log_console(self, message, tag=None):
        """Adiciona mensagem ao console"""
        timestamp = time.strftime('%H:%M:%S')
        self.console.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.console.see(tk.END)
        
    def clear_console(self):
        """Limpa o console"""
        self.console.delete(1.0, tk.END)
        self.log_console("🗑️ Console limpo!")
        
    def validate_fields(self):
        """Valida campos obrigatórios"""
        token = self.token_entry.get().strip()
        owner_id = self.owner_entry.get().strip()
        
        if not token:
            messagebox.showerror("Erro", "O Token do Bot é obrigatório!")
            return False
            
        if not owner_id:
            messagebox.showerror("Erro", "O ID do Dono é obrigatório!")
            return False
            
        try:
            int(owner_id)
        except ValueError:
            messagebox.showerror("Erro", "O ID do Dono deve ser um número!")
            return False
            
        return True
        
    def start_bot(self):
        """Inicia o bot"""
        if not self.validate_fields():
            return
            
        self.bot_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="🟢 Bot Online", fg='#4ecca3')
        
        # Desabilitar campos
        self.token_entry.config(state=tk.DISABLED)
        self.owner_entry.config(state=tk.DISABLED)
        self.group_entry.config(state=tk.DISABLED)
        self.channel_entry.config(state=tk.DISABLED)
        self.api_id_entry.config(state=tk.DISABLED)
        self.api_hash_entry.config(state=tk.DISABLED)
        
        self.log_console("", 'info')
        self.log_console("🚀 Iniciando bot...", 'info')
        
        # Iniciar bot em thread separada
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()
        
    def stop_bot(self):
        """Para o bot"""
        self.bot_running = False
        if self.bot:
            try:
                self.bot.stop_polling()
            except:
                pass
        
        # Parar Pyrogram client
        if self.pyrogram_client and self.pyrogram_loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.pyrogram_client.stop(), self.pyrogram_loop
                )
                future.result(timeout=5)
                self.log_console("🔌 Pyrogram desconectado!", 'info')
            except:
                pass
            self.pyrogram_client = None
                
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="⚫ Bot Offline", fg='#888888')
        
        # Habilitar campos
        self.token_entry.config(state=tk.NORMAL)
        self.owner_entry.config(state=tk.NORMAL)
        self.group_entry.config(state=tk.NORMAL)
        self.channel_entry.config(state=tk.NORMAL)
        self.api_id_entry.config(state=tk.NORMAL)
        self.api_hash_entry.config(state=tk.NORMAL)
        
        self.log_console("⏹️ Bot parado!", 'warning')
    
    def start_pyrogram_client(self):
        """Inicia o cliente Pyrogram em um event loop separado"""
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        bot_token = self.token_entry.get().strip()
        
        if not PYROGRAM_AVAILABLE:
            self.log_console("⚠️ Pyrogram não instalado. Comando /info desabilitado.", 'warning')
            self.log_console("   Instale com: pip install pyrofork python-dateutil TgCrypto", 'warning')
            return False
        
        if not api_id or not api_hash:
            self.log_console("⚠️ API ID ou API Hash não configurados. Comando /info desabilitado.", 'warning')
            return False
        
        try:
            api_id = int(api_id)
        except ValueError:
            self.log_console("❌ API ID deve ser um número!", 'error')
            return False
        
        try:
            self.pyrogram_loop = asyncio.new_event_loop()
            
            def run_pyrogram():
                asyncio.set_event_loop(self.pyrogram_loop)
                self.pyrogram_client = Client(
                    "bot_info_session",
                    api_id=api_id,
                    api_hash=api_hash,
                    bot_token=bot_token,
                    workdir=os.path.dirname(os.path.abspath(__file__)) or ".",
                    in_memory=True
                )
                self.pyrogram_loop.run_until_complete(self.pyrogram_client.start())
                self.log_console("✅ Pyrogram conectado! Comando /info habilitado.", 'success')
                self.pyrogram_loop.run_forever()
            
            pyro_thread = threading.Thread(target=run_pyrogram, daemon=True)
            pyro_thread.start()
            time.sleep(3)  # Aguardar inicialização
            return True
            
        except Exception as e:
            self.log_console(f"❌ Erro ao iniciar Pyrogram: {str(e)}", 'error')
            return False
        
    def run_bot(self):
        """Executa o bot"""
        try:
            API_TOKEN = self.token_entry.get().strip()
            OWNER_ID = int(self.owner_entry.get().strip())
            RESULTS_GROUP_ID = self.group_entry.get().strip() or None
            CHANNEL_ID = self.channel_entry.get().strip() or None
            
            self.admin_users = {OWNER_ID}
            
            self.bot = telebot.TeleBot(API_TOKEN)
            
            self.log_console(f"✅ Token configurado!", 'success')
            self.log_console(f"👑 Dono ID: {OWNER_ID}", 'success')
            
            if RESULTS_GROUP_ID:
                self.log_console(f"📢 Grupo de Resultados: {RESULTS_GROUP_ID}", 'success')
            if CHANNEL_ID:
                self.log_console(f"📺 Canal: {CHANNEL_ID}", 'success')
            
            # Iniciar Pyrogram para /info
            pyrogram_enabled = self.start_pyrogram_client()
                
            self.log_console("", 'info')
            self.log_console("🤖 Bot iniciado com sucesso!", 'success')
            self.log_console("📡 Aguardando comandos...", 'info')
            self.log_console("", 'info')
            
            # ========== FUNÇÕES DO BOT ==========
            
            def check_url(url):
                parsed_url = urlparse(url)
                params = parse_qs(parsed_url.query)
                username = params.get("username", [None])[0]
                password = params.get("password", [None])[0]

                if username and password:
                    host = parsed_url.hostname
                    port = parsed_url.port or ''
                    api_url = f"http://{host}:{port}/player_api.php?username={username}&password={password}"

                    try:
                        api_response = requests.get(api_url, timeout=10).json()
                        return api_response, username, password, host, port
                    except requests.exceptions.RequestException:
                        return None, None, None, None, None
                return None, None, None, None, None
            
            # Comando /Checker
            @self.bot.message_handler(commands=['Checker'])
            def check_m3u_link(message):
                if message.from_user.id in self.banned_users:
                    self.bot.reply_to(message, "❌ Você está banido e não pode usar o bot.")
                    return

                link = message.text.split(maxsplit=1)
                if len(link) < 2:
                    self.bot.reply_to(message, "❌ Por favor, forneça uma URL M3U após o comando /Checker.")
                    return

                url = link[1].strip()
                response_text = ""
                self.bot.reply_to(message, "Processando sua solicitação...")
                
                self.log_console(f"📥 Comando /Checker de {message.from_user.username or message.from_user.id}", 'info')

                user_info = {
                    'user_id': message.from_user.id,
                    'username': message.from_user.username or "Sem nome de usuário",
                    'url': url,
                    'status': "Processando"
                }
                self.user_logs.append(user_info)

                api_response, username, password, host, port = check_url(url)

                if api_response and 'user_info' in api_response and api_response['user_info']['status'] == 'Active':
                    user_info['status'] = "Ativo"
                    server_info = api_response['user_info']

                    created_at = int(server_info['created_at'])
                    exp_date = int(server_info['exp_date'])

                    response_text += (
                        f"*Status:* {server_info['status']}\n"
                        f"*Usuário:* {username}\n"
                        f"*Senha:* {password}\n"
                        f"*Data de criação:* {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))}\n"
                        f"*Data de expiração:* {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp_date))}\n"
                        f"*Conexões máximas:* {server_info['max_connections']}\n"
                        f"*Conexões Ativas:* {server_info['active_cons']}\n"
                    )

                    allowed_formats = server_info.get('allowed_output_formats', [])
                    links_construidos = [
                        f"[{fmt}](http://{host}:{port}/player_api.php?username={username}&password={password}&format={fmt})"
                        for fmt in allowed_formats
                    ]
                    response_text += f"*Links para Formatos de Lista:* " + " | ".join(links_construidos) + "\n"
                    response_text += "\n▬▬▬▬▬ஜ۩𝑬𝒅𝒊𝒗𝒂𝒍𝒅𝒐۩ஜ▬▬▬▬▬\n"

                    live_streams_url = f"{url}&action=get_live_streams"
                    series_url = f"{url}&action=get_series"
                    vod_streams_url = f"{url}&action=get_vod_streams"

                    try:
                        live_streams_response = requests.get(live_streams_url, timeout=10).json()
                        series_response = requests.get(series_url, timeout=10).json()
                        vod_streams_response = requests.get(vod_streams_url, timeout=10).json()

                        live_stream_count = len(live_streams_response)
                        series_count = len(series_response)
                        vod_stream_count = len(vod_streams_response)

                        response_text += (
                            f"*Live Streams:* {live_stream_count}\n"
                            f"*Séries:* {series_count}\n"
                            f"*VOD Streams:* {vod_stream_count}\n"
                        )
                    except:
                        pass

                    result_key = f"{user_info['user_id']}:{url}"
                    current_time = time.time()
                    if result_key in self.sent_results:
                        last_sent_time = self.sent_results[result_key]
                        if current_time - last_sent_time < 12 * 3600:
                            self.bot.reply_to(message, "❌ Este resultado já foi enviado nas últimas 12 horas.")
                            return
                    else:
                        self.sent_results[result_key] = current_time

                    if message.chat.type == 'private' and RESULTS_GROUP_ID:
                        try:
                            self.bot.send_message(RESULTS_GROUP_ID, response_text, parse_mode='Markdown')
                        except Exception as e:
                            self.log_console(f"⚠️ Erro ao enviar para grupo: {e}", 'warning')

                    self.bot.reply_to(message, response_text, parse_mode='Markdown')
                    self.log_console(f"✅ Check concluído para {message.from_user.username or message.from_user.id}", 'success')

                else:
                    self.bot.reply_to(message, "❌ Erro: Nenhuma informação encontrada ou conta inativa.\n")
                    self.log_console(f"❌ Check falhou para {message.from_user.username or message.from_user.id}", 'error')

            # Comando /info - Consulta informações do Telegram
            @self.bot.message_handler(commands=['info'])
            def info_command(message):
                if message.from_user.id in self.banned_users:
                    self.bot.reply_to(message, "❌ Você está banido e não pode usar o bot.")
                    return
                
                if not self.pyrogram_client or not self.pyrogram_loop:
                    self.bot.reply_to(message, 
                        "❌ Comando /info não disponível.\n\n"
                        "Para habilitar, configure:\n"
                        "• API ID e API Hash no painel\n"
                        "• Instale: `pip install pyrofork python-dateutil TgCrypto`",
                        parse_mode='Markdown')
                    return
                
                args = message.text.split(maxsplit=1)
                if len(args) < 2:
                    self.bot.reply_to(message, 
                        "❌ Por favor, forneça um username ou ID.\n\n"
                        "*Uso:*\n"
                        "• `/info @username`\n"
                        "• `/info 123456789`\n"
                        "• `/info t.me/username`",
                        parse_mode='Markdown')
                    return
                
                target = args[1].strip()
                processing_msg = self.bot.reply_to(message, "🔍 Consultando informações...")
                
                self.log_console(f"🔍 Comando /info '{target}' de {message.from_user.username or message.from_user.id}", 'info')
                
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        get_telegram_info(self.pyrogram_client, target),
                        self.pyrogram_loop
                    )
                    result = future.result(timeout=15)
                    
                    if result["success"]:
                        response_text = format_user_response(result)
                        self.bot.edit_message_text(
                            response_text, 
                            chat_id=message.chat.id, 
                            message_id=processing_msg.message_id,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        self.log_console(f"✅ Info consultada: {target} ({result.get('type', 'unknown')})", 'success')
                    else:
                        self.bot.edit_message_text(
                            f"❌ {result.get('error', 'Entidade não encontrada.')}",
                            chat_id=message.chat.id,
                            message_id=processing_msg.message_id
                        )
                        self.log_console(f"❌ Info não encontrada: {target}", 'error')
                        
                except Exception as e:
                    self.bot.edit_message_text(
                        f"❌ Erro ao consultar: {str(e)}",
                        chat_id=message.chat.id,
                        message_id=processing_msg.message_id
                    )
                    self.log_console(f"❌ Erro no /info: {str(e)}", 'error')

            # Comando /painel
            @self.bot.message_handler(commands=['painel'])
            def painel(message):
                self.log_console(f"📋 Comando /painel de {message.from_user.id}", 'info')
                if message.from_user.id == OWNER_ID:
                    self.bot.reply_to(message, "Comandos disponíveis:\n"
                                      "/ban_user + ID - Banir usuário do bot\n"
                                      "/unban_user + ID - Desbanir usuário do bot\n"
                                      "/add_adm + ID - Adicionar novo administrador\n"
                                      "/ban_adm + ID - Banir administrador")
                elif message.from_user.id in self.admin_users:
                    self.bot.reply_to(message, "Comandos disponíveis para administradores:\n"
                                      "/ban_user + ID - Banir usuário do bot\n"
                                      "/unban_user + ID - Desbanir usuário do bot\n"
                                      "/advertencia + ID - Dar advertência ao usuário\n"
                                      "/deletar + URL - Deletar post específico")
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para essa função.")

            # Comando /adms
            @self.bot.message_handler(commands=['adms'])
            def list_admins(message):
                self.log_console(f"👥 Comando /adms de {message.from_user.id}", 'info')
                if message.from_user.id == OWNER_ID or message.from_user.id in self.admin_users:
                    admin_list = ", ".join(str(admin) for admin in self.admin_users)
                    self.bot.reply_to(message, f"Administradores do bot:\n{admin_list}")
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para essa função.")

            # Comando /ban_user
            @self.bot.message_handler(commands=['ban_user'])
            def ban_user(message):
                if message.from_user.id == OWNER_ID or message.from_user.id in self.admin_users:
                    user_id_to_ban = message.text.split(maxsplit=1)
                    if len(user_id_to_ban) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça o ID do usuário que deseja banir.")
                        return
                    self.banned_users.add(int(user_id_to_ban[1]))
                    if RESULTS_GROUP_ID:
                        try:
                            self.bot.send_message(RESULTS_GROUP_ID, f"Usuário com ID {user_id_to_ban[1]} foi banido.")
                        except:
                            pass
                    self.bot.reply_to(message, f"✅ Usuário com ID {user_id_to_ban[1]} foi banido.")
                    self.log_console(f"🚫 Usuário {user_id_to_ban[1]} banido!", 'warning')
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para banir usuários.")

            # Comando /unban_user
            @self.bot.message_handler(commands=['unban_user'])
            def unban_user(message):
                if message.from_user.id == OWNER_ID or message.from_user.id in self.admin_users:
                    user_id_to_unban = message.text.split(maxsplit=1)
                    if len(user_id_to_unban) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça o ID do usuário que deseja desbanir.")
                        return
                    self.banned_users.discard(int(user_id_to_unban[1]))
                    if RESULTS_GROUP_ID:
                        try:
                            self.bot.send_message(RESULTS_GROUP_ID, f"Usuário com ID {user_id_to_unban[1]} foi desbanido.")
                        except:
                            pass
                    self.bot.reply_to(message, f"✅ Usuário com ID {user_id_to_unban[1]} foi desbanido.")
                    self.log_console(f"✅ Usuário {user_id_to_unban[1]} desbanido!", 'success')
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para desbanir usuários.")

            # Comando /add_adm
            @self.bot.message_handler(commands=['add_adm'])
            def add_admin(message):
                if message.from_user.id == OWNER_ID:
                    admin_id_to_add = message.text.split(maxsplit=1)
                    if len(admin_id_to_add) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça o ID do usuário que deseja adicionar como administrador.")
                        return
                    self.admin_users.add(int(admin_id_to_add[1]))
                    if RESULTS_GROUP_ID:
                        try:
                            self.bot.send_message(RESULTS_GROUP_ID, f"Usuário com ID {admin_id_to_add[1]} foi adicionado como administrador.")
                        except:
                            pass
                    self.bot.reply_to(message, f"✅ Usuário com ID {admin_id_to_add[1]} foi adicionado como administrador.")
                    self.log_console(f"👑 Admin {admin_id_to_add[1]} adicionado!", 'success')
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para essa função.")

            # Comando /ban_adm
            @self.bot.message_handler(commands=['ban_adm'])
            def ban_admin(message):
                if message.from_user.id == OWNER_ID:
                    admin_id_to_ban = message.text.split(maxsplit=1)
                    if len(admin_id_to_ban) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça o ID do administrador que deseja banir.")
                        return
                    self.admin_users.discard(int(admin_id_to_ban[1]))
                    if RESULTS_GROUP_ID:
                        try:
                            self.bot.send_message(RESULTS_GROUP_ID, f"Administrador com ID {admin_id_to_ban[1]} foi banido.")
                        except:
                            pass
                    self.bot.reply_to(message, f"✅ Administrador com ID {admin_id_to_ban[1]} foi banido.")
                    self.log_console(f"🚫 Admin {admin_id_to_ban[1]} removido!", 'warning')
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para essa função.")

            # Comando /advertencia
            @self.bot.message_handler(commands=['advertencia'])
            def warn_user(message):
                if message.from_user.id in self.admin_users:
                    user_id_to_warn = message.text.split(maxsplit=1)
                    if len(user_id_to_warn) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça o ID do usuário que deseja advertir.")
                        return
                    user_id = int(user_id_to_warn[1])
                    
                    if user_id not in self.user_warnings:
                        self.user_warnings[user_id] = 0
                    
                    self.user_warnings[user_id] += 1
                    
                    if self.user_warnings[user_id] >= 3:
                        self.banned_users.add(user_id)
                        if RESULTS_GROUP_ID:
                            try:
                                self.bot.send_message(RESULTS_GROUP_ID, f"Usuário com ID {user_id} foi banido após 3 advertências.")
                            except:
                                pass
                        self.bot.reply_to(message, f"✅ Usuário com ID {user_id} foi banido após 3 advertências.")
                        self.log_console(f"🚫 Usuário {user_id} banido por 3 advertências!", 'error')
                        del self.user_warnings[user_id]
                    else:
                        self.bot.reply_to(message, f"✅ Usuário com ID {user_id} recebeu uma advertência. Total de advertências: {self.user_warnings[user_id]}.")
                        self.log_console(f"⚠️ Advertência para {user_id} ({self.user_warnings[user_id]}/3)", 'warning')
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para advertir usuários.")

            # Comando /deletar
            @self.bot.message_handler(commands=['deletar'])
            def delete_post(message):
                if message.from_user.id in self.admin_users:
                    url_to_delete = message.text.split(maxsplit=1)
                    if len(url_to_delete) < 2:
                        self.bot.reply_to(message, "❌ Por favor, forneça a URL do post que deseja deletar.")
                        return
                    
                    url = url_to_delete[1].strip()
                    result_key = f"{message.from_user.id}:{url}"
                    if result_key in self.sent_results:
                        del self.sent_results[result_key]
                        self.bot.reply_to(message, f"✅ O post com URL {url} foi deletado com sucesso.")
                        self.log_console(f"🗑️ Post deletado: {url[:50]}...", 'warning')
                    else:
                        self.bot.reply_to(message, "❌ URL não encontrada nos resultados enviados.")
                else:
                    self.bot.reply_to(message, "❌ Desculpas, mas você não tem permissão para deletar posts.")

            # Comando /start
            @self.bot.message_handler(commands=['start'])
            def start_message(message):
                self.log_console(f"👋 Novo usuário: {message.from_user.username or message.from_user.id}", 'info')
                
                info_status = "✅ Ativo" if pyrogram_enabled else "❌ Desabilitado"
                
                self.bot.reply_to(message, 
                    "🤖 *Bem-vindo ao Bot Checker M3U & Info!*\n\n"
                    "📋 *Comandos disponíveis:*\n"
                    "/Checker + URL - Verificar lista M3U\n"
                    f"/info + @username ou ID - Consultar info do Telegram ({info_status})\n"
                    "/painel - Ver comandos administrativos\n"
                    "/adms - Ver lista de administradores\n\n"
                    "▬▬▬▬▬ஜ۩ *@Edkd1* ۩ஜ▬▬▬▬▬",
                    parse_mode='Markdown'
                )

            # Inicia o polling
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
            
        except Exception as e:
            self.log_console(f"❌ Erro: {str(e)}", 'error')
            self.root.after(0, self.stop_bot)
            
    def run(self):
        """Inicia a aplicação"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Ao fechar a janela"""
        if self.bot_running:
            if messagebox.askokcancel("Sair", "O bot está rodando. Deseja parar e sair?"):
                self.stop_bot()
                self.root.destroy()
        else:
            self.root.destroy()

# Executa a aplicação
if __name__ == "__main__":
    app = BotConfigGUI()
    app.run()
