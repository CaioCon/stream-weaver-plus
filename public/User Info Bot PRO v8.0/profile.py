# ══════════════════════════════════════════════
# 🧬  PROFILE — captura via Telethon + cards
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
import io
from telethon.tl.functions.users import GetFullUserRequest
from db import log, is_field_hidden


async def obter_perfil_completo(client, user_id) -> dict:
    """Retorna dict { bio, phone, fotos, restricoes, photo_bytes }."""
    extras = {"bio": "", "phone": "", "fotos": False,
              "restricoes": "Nenhuma", "photo_bytes": None}
    try:
        full = await client(GetFullUserRequest(user_id))
        extras["bio"] = (getattr(full.full_user, 'about', '') or "").strip()
        try:
            buf = io.BytesIO()
            await client.download_profile_photo(user_id, file=buf)
            data = buf.getvalue()
            if data:
                extras["fotos"] = True
                extras["photo_bytes"] = data
        except Exception:
            pass
        raw_user = full.users[0] if full.users else None
        if raw_user:
            extras["phone"]      = getattr(raw_user, 'phone', '') or ""
            extras["restricoes"] = str(getattr(raw_user, 'restriction_reason', '') or "Nenhuma")
    except Exception as e:
        log(f"⚠️ Perfil indisponível para {user_id}: {e}")
    return extras


# ── Card individual por usuário (caption do canal) ──
def montar_card(uid: str, dados: dict, *, mostrar_oculto_owner: bool = False) -> str:
    """
    Gera o caption do card. Respeita 'hidden_global' do painel.
    Se `mostrar_oculto_owner=True`, mostra os campos com marca [oculto].
    """
    def _campo(field: str, valor: str, label: str, *, mono=False) -> str:
        if not valor:
            return ""
        oculto = is_field_hidden(field)
        if oculto and not mostrar_oculto_owner:
            return ""
        v = f"`{valor}`" if mono else valor
        marca = " _(oculto)_" if oculto else ""
        return f"{label}: {v}{marca}\n"

    nome     = dados.get("nome_atual") or "_Sem nome_"
    username = dados.get("username_atual") or ""
    phone    = dados.get("phone") or ""
    bio      = dados.get("bio") or ""
    grupos   = dados.get("grupos") or []
    hist     = dados.get("historico") or []

    linhas = ["━━━━━━━━━━━━━━━━━━━━",
              "👤 *PERFIL DETECTADO*",
              "━━━━━━━━━━━━━━━━━━━━"]
    linhas.append(_campo("nome", nome, "📛 *Nome*"))
    linhas.append(_campo("id", str(uid), "🆔 *ID*", mono=True))
    if username:
        linhas.append(_campo("username", f"@{username}", "🔗 *Username*"))
    linhas.append(_campo("phone", phone, "📱 *Telefone*", mono=True))
    if bio:
        linhas.append(_campo("bio", bio, "📝 *Bio*"))

    if grupos and not is_field_hidden("grupos"):
        amostra = ", ".join(grupos[:5])
        extra   = f" *(+{len(grupos)-5})*" if len(grupos) > 5 else ""
        linhas.append(f"📂 *Grupos*: {amostra}{extra}\n")
    elif grupos and mostrar_oculto_owner:
        linhas.append(f"📂 *Grupos*: _{len(grupos)} (oculto)_\n")

    if hist and not is_field_hidden("historico"):
        ult = hist[-3:]
        linhas.append("📜 *Últimas mudanças*:")
        for h in ult:
            linhas.append(f"  • _{h.get('tipo')}_ `{h.get('de','?')}` ➜ `{h.get('para','?')}`")
        linhas.append("")

    linhas.append(f"🕒 _Atualizado: {dados.get('ultima_atualizacao','?')}_")
    return "\n".join([l for l in linhas if l])
