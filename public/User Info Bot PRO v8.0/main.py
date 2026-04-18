# ══════════════════════════════════════════════
# 🚀  MAIN — User Info Bot PRO v8.0
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
Estrutura modular (mesma pasta):
  config.py    credenciais e constantes
  db.py        persistência json (banco + cards + settings)
  format.py    markdown leve → HTML do Telegram
  profile.py   captura via Telethon + montagem do card
  notifier.py  envia/edita cards no canal de notificação
  search.py    busca local + lookup online
  scan.py      varredura periódica de grupos
  handlers.py  comandos + callbacks + inline + DM
  main.py      este arquivo
"""

import asyncio
from telethon import TelegramClient

from config import (API_ID, API_HASH, PHONE, BOT_TOKEN,
                    SESSION_USER, SESSION_BOT, SCAN_INTERVAL)
from db import log
from handlers import register_handlers
import scan as scan_mod


user_client = TelegramClient(SESSION_USER, API_ID, API_HASH)
bot         = TelegramClient(SESSION_BOT,  API_ID, API_HASH)


async def _periodic_scan():
    while True:
        try:
            await asyncio.sleep(SCAN_INTERVAL)
            if not scan_mod.is_scan_running():
                await scan_mod.executar_varredura(user_client, bot)
        except Exception as e:
            log(f"⚠️ periodic_scan: {e}")


async def main():
    log("🚀 Iniciando User Info Bot PRO v8.0")
    await user_client.start(phone=PHONE)
    await bot.start(bot_token=BOT_TOKEN)
    register_handlers(bot, user_client)
    asyncio.create_task(_periodic_scan())
    log("✅ Bot online. Aguardando eventos.")
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot.run_until_disconnected(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("🛑 Encerrado pelo usuário.")
