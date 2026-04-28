# Deezer Bot — bot_painel2 (melhorias)

Baseado em `https://github.com/ContaTreino/bot_painel_2.py` (`bot_painel2.py`).
Mantém 100% das funcionalidades originais e acrescenta suporte robusto a
**grupos com tópicos**, **reconhecimento do dono** e **busca livre em DM**.

## O que mudou

### 1. Tópicos de grupo (Forum Topics)
- `_event_topic_id` agora cobre todos os casos do Telethon:
  flag `forum_topic`, `reply_to_top_id`, `reply_to_msg_id` (1ª msg do tópico)
  e `MessageActionTopicCreate`.
- Cada grupo pode ter **vários tópicos autorizados** (lista `topic_ids`),
  mantendo retrocompatibilidade com o campo legado `topic_id`.
- Se a busca chega no tópico **A** do grupo, a resposta vai no tópico **A**.
  Se chega no tópico **B**, vai no tópico **B**.
- Roteamento de respostas agora é por `(uid, chat_id)`, evitando colisão
  quando o mesmo usuário interage em vários grupos.

### 2. Reconhecimento do dono
- `is_owner(uid)` centraliza a checagem (`OWNER_ID` no `.env`).
- Comando `/whoami` mostra: seu ID, ID do chat, tópico atual e se você
  é o dono — ideal para descobrir IDs antes de autorizar grupos/tópicos.

### 3. Autorização de grupos/tópicos
Comandos do dono (no DM ou no próprio grupo):
| Comando | O que faz |
|---|---|
| `/addgroup [chat_id]` | Autoriza um grupo (sem restrição de tópico). |
| `/rmgroup <chat_id>` | Remove o grupo. |
| `/setopic [chat_id topic_id]` | Define **um** tópico (substitui). |
| `/addtopic [chat_id topic_id]` | **Adiciona** um tópico (mantém os outros). |
| `/rmtopic <chat_id> <topic_id>` | Remove apenas um tópico. |
| `/listgroups` | Lista todos os grupos e tópicos autorizados. |
| `/whoami` | Mostra IDs do contexto atual. |

Sem argumentos, os comandos usam o chat/tópico onde foram enviados.
Você também pode **encaminhar** uma mensagem do tópico depois de clicar
em "Definir tópico" no painel `/start → ⚙️ → 👥 Grupos`.

Exemplo do enunciado:
```
/addgroup -1234567890        # grupo A
/addtopic -1234567890 2407   # tópico do grupo A

/addgroup -1234567891        # grupo B
/addtopic -1234567891 3208876
```

### 4. Buscas
- **DM**: qualquer usuário pode enviar termos OU links Deezer e receber
  resultados. Recursos premium/admin continuam restritos.
- **Grupo**: só funciona em grupos (e tópicos) autorizados. Buscas e
  resultados ficam confinados ao tópico de origem.
- **Grupo não autorizado**: o bot fica em silêncio total (não responde nem
  vaza erros).

## .env esperado
```
API_ID=123456
API_HASH=abc...
BOT_TOKEN=123:abc
OWNER_ID=111222333
CHANNEL_ID=0           # opcional
```

## Como rodar (Termux/Linux)
```
cd public/bot_painel2
python3 bot_painel2.py
```
As dependências (`telethon`, `deemix`, etc.) são instaladas automaticamente
no primeiro start.
