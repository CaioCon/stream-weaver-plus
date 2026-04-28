# Deezer Bot — v12 (Mega Power) — pella.app edition

Código **100% preservado** do repositório original  
`https://github.com/ContaTreino/bot_painel_2.py` (`bot_painel2.py`),
com apenas estas mudanças cirúrgicas:

## ✨ Mudanças aplicadas

### 1. Sem comandos com "/"
Removidos: `/addgroup`, `/rmgroup`, `/setopic`.  
Mantido apenas `/start` (necessário para iniciar conversa com qualquer bot do Telegram).

Todo o gerenciamento agora é **100% via botões inline com paginação**, já presentes no bot original:

- **Painel admin** → `👥 Grupos/Tópicos`
  - `➕ Adicionar grupo (ID)` — pede o ID via prompt inline
  - `➖ Remover grupo` — pede o ID via prompt inline
  - `📌 Definir tópico` — encaminhe uma mensagem do tópico **OU** envie `chat_id topic_id`
  - `🔄 Atualizar` — recarrega lista paginada de grupos/tópicos
- **Painel admin** → `🛡 Permissões`
  - Liberar/remover usuários para **Explorar** e **Busca por termo** (também paginado)

### 2. Pasta `grupos/` na pasta do bot
- Criada automaticamente em `BASE_DIR / "grupos"`.
- `groups_config.json` agora vive em `grupos/groups_config.json`.
- **Migração automática**: se já existir um `groups_config.json` antigo na raiz do bot, ele é movido para `grupos/` no primeiro start (sem perda de dados).

### 3. Tudo salvo na **mesma pasta** do bot
Já era assim no original (`BASE_DIR = Path(__file__).resolve().parent`), mantido intacto:
- `.env`
- `arl_user.txt`
- `users_info.json`
- `admin_config.json`
- `permissions.json`
- `grupos/groups_config.json`  ← novo path
- `downloads/`  ← arquivos baixados
- `dz_bot_v12.session`

### 4. Reconhecimento de tópicos (já existia, mantido)
- `_event_topic_id(event)` extrai o `topic_id` da mensagem (suporta forum topics).
- `_set_target(uid, chat_id, topic_id)` memoriza onde o usuário fez a busca.
- Todos os envios (`_send_card`, `send_menu`, downloads, etc.) usam `reply_to=topic_id`, garantindo que **a resposta cai no tópico correto** do grupo correto.
- Em DM apenas o owner pode usar; em grupos só responde nos pares (chat, tópico) autorizados.

### 5. Reconhecimento do dono
- `OWNER_ID` é lido do `.env`.
- `_is_owner(event)` é usado em todo handler privilegiado.
- Owner tem acesso ao painel completo (`👤 Owner` no menu) e bypassa restrições de grupo/tópico.

## ▶️ Como rodar (Termux / Linux)

```bash
cd "public/bot_painel2"
python3 bot_painel2.py
```

As dependências (`telethon`, `requests`, `urllib3`, `python-dotenv`, `mutagen`, `deezer-py`, `deemix`) são instaladas automaticamente no primeiro start.

## ⚙️ `.env` esperado (na pasta do bot)

```
API_ID=123456
API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BOT_TOKEN=123:ABC...
OWNER_ID=123456789
CHANNEL_ID=0
```

## 📌 Configurando os grupos pelo bot (sem comandos "/")

1. Abra DM com o bot e envie `/start` → aparece o menu inline.
2. Toque em **`👤 Owner`** → **`👥 Grupos/Tópicos`**.
3. **`➕ Adicionar grupo (ID)`** → envie `-1003708574604` (ou o ID do seu grupo).
4. **`📌 Definir tópico`** → envie `-1003708574604 2407` (chat_id seguido do topic_id), ou encaminhe uma mensagem do próprio tópico.
5. Pronto — o bot só responderá naquele tópico, e todas as buscas/cards/downloads acionados de lá voltam no mesmo tópico.
