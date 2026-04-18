# ══════════════════════════════════════════════
# 🔍  SEARCH — local + lookup via Telethon
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
"""
Busca por @username OU ID numérico.
1) Tenta no banco local.
2) Se nada, faz lookup via user_client e cadastra o usuário.
"""

from db import carregar_dados, salvar_dados, log, iter_usuarios, upsert_user
from profile import obter_perfil_completo


def buscar_local(query: str):
    db = carregar_dados()
    q = query.lstrip("@").lower()
    is_id = q.isdigit()
    out = []
    for uid, ent in iter_usuarios(db):
        if is_id and uid == q:
            out.append((uid, ent)); break
        if not is_id and (ent.get("username_atual", "").lower() == q):
            out.append((uid, ent)); break
    return out


async def buscar_com_lookup(user_client, query: str):
    """Retorna lista de tuplas (uid, entry). Faz upsert no banco se achar online."""
    res = buscar_local(query)
    if res:
        return res
    q = query.lstrip("@")
    try:
        target = int(q) if q.isdigit() else q
        ent_tg = await user_client.get_entity(target)
    except Exception as e:
        log(f"lookup '{query}' falhou: {e}")
        return []

    uid = ent_tg.id
    nome = ((getattr(ent_tg, "first_name", "") or "") + " " +
            (getattr(ent_tg, "last_name", "") or "")).strip()
    extras = await obter_perfil_completo(user_client, uid)
    db = carregar_dados()
    entry, _mudancas, _novo = upsert_user(
        db, uid,
        nome=nome,
        username=getattr(ent_tg, "username", "") or "",
        phone=extras["phone"],
        bio=extras["bio"],
        fotos=extras["fotos"],
        grupo="Lookup",
    )
    salvar_dados(db)
    # Devolve também os bytes da foto pra quem quiser postar card
    entry["_photo_bytes"] = extras.get("photo_bytes")
    return [(str(uid), entry)]
