# ══════════════════════════════════════════════
# 🎨  FORMAT — Markdown leve → HTML do Telegram
# 👨‍💻 Créditos: Edivaldo Silva @Edkd1
# ══════════════════════════════════════════════
import re
from html import escape as _esc

HTML = "html"

_TOKEN_RE = re.compile(
    r"```(.+?)```"
    r"|`([^`\n]+)`"
    r"|\*\*([^*\n]+?)\*\*"
    r"|__([^_\n]+?)__"
    r"|\*([^*\n]+?)\*"
    r"|_([^_\n]+?)_"
    r"|\[([^\]]+)\]\(([^)]+)\)",
    re.DOTALL,
)


def to_html(text: str) -> str:
    if not text:
        return ""
    out, last = [], 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > last:
            out.append(_esc(text[last:m.start()]))
        if m.group(1) is not None:   out.append(f"<pre>{_esc(m.group(1))}</pre>")
        elif m.group(2) is not None: out.append(f"<code>{_esc(m.group(2))}</code>")
        elif m.group(3) is not None: out.append(f"<b>{_esc(m.group(3))}</b>")
        elif m.group(4) is not None: out.append(f"<b>{_esc(m.group(4))}</b>")
        elif m.group(5) is not None: out.append(f"<b>{_esc(m.group(5))}</b>")
        elif m.group(6) is not None: out.append(f"<i>{_esc(m.group(6))}</i>")
        elif m.group(7) is not None:
            out.append(f'<a href="{_esc(m.group(8), quote=True)}">{_esc(m.group(7))}</a>')
        last = m.end()
    if last < len(text):
        out.append(_esc(text[last:]))
    return "".join(out)


__all__ = ["to_html", "HTML"]
