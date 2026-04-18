# ══════════════════════════════════════════════
# 📡  SCAN — varredura periódica de grupos
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
import asyncio
from telethon.errors import FloodWaitError

from config import SCRAPE_CONCURRENCY, SCRAPE_MSG_LIMIT_PER_GROUP
from db import (carregar_dados, salvar_dados, log, agora_str, upsert_user)
from profile import obter_perfil_completo
from notifier import enviar_ou_editar_card


_scan_running = False
scan_stats = {"last_scan": None, "users_scanned": 0,
              "groups_scanned": 0, "changes_detected": 0}


def is_scan_running() -> bool:
    return _scan_running


async def _processar_grupo(user_client, bot, dialog, db, sem):
    async with sem:
        gid = dialog.id
        gname = dialog.name or str(gid)
        try:
            participants = await user_client.get_participants(dialog.entity, limit=None)
        except FloodWaitError as e:
            log(f"⏱ FloodWait {e.seconds}s @ {gname}")
            await asyncio.sleep(e.seconds + 1)
            return 0, 0
        except Exception as e:
            log(f"⚠️ get_participants {gname}: {e}")
            return 0, 0

        novos_ou_alterados = 0
        for p in participants:
            if getattr(p, "bot", False) or getattr(p, "deleted", False):
                continue
            uid = p.id
            nome = ((p.first_name or "") + " " + (p.last_name or "")).strip()
            extras = await obter_perfil_completo(user_client, uid)
            entry, mudancas, novo = upsert_user(
                db, uid,
                nome=nome,
                username=p.username or "",
                phone=extras["phone"],
                bio=extras["bio"],
                fotos=extras["fotos"],
                grupo=gname,
            )
            if novo or mudancas:
                novos_ou_alterados += 1
                scan_stats["changes_detected"] += 1
                # Atualiza o card no canal
                await enviar_ou_editar_card(bot, str(uid), entry,
                                             photo_bytes=extras.get("photo_bytes"))
        return len(participants), novos_ou_alterados


async def executar_varredura(user_client, bot):
    global _scan_running, scan_stats
    if _scan_running:
        return
    _scan_running = True
    scan_stats = {"last_scan": agora_str(), "users_scanned": 0,
                  "groups_scanned": 0, "changes_detected": 0}
    db = carregar_dados()
    log("🔄 Varredura iniciada")
    try:
        sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)
        tarefas = []
        async for dialog in user_client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                tarefas.append(_processar_grupo(user_client, bot, dialog, db, sem))
        for fut in asyncio.as_completed(tarefas):
            try:
                vistos, _ = await fut
                scan_stats["users_scanned"] += vistos
                scan_stats["groups_scanned"] += 1
            except Exception as e:
                log(f"⚠️ tarefa scan: {e}")
        salvar_dados(db)
        log(f"✅ Varredura: {scan_stats['groups_scanned']} grupos, "
            f"{scan_stats['users_scanned']} usuários, "
            f"{scan_stats['changes_detected']} mudanças")
    finally:
        _scan_running = False
