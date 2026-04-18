# User Info Bot PRO v8.0

Versão enxuta — sem premium, sem combos, sem importação de banco.
Toda interação acontece em modo *inline* + canal de notificação.

## O que mudou (v7 → v8)
- 🔔 Notificações vão para o **canal** `NOTIFY_CHANNEL_ID` (cards individuais).
- 🔎 Inline aceita **@username** ou **ID numérico**:
  - `@InforUser_Bot @fulano`
  - `@InforUser_Bot 1234567890`
- ❌ Removido: premium, combos, importação de banco, consultas via DM.
- 🖼 Cada usuário tem 1 *card* no canal (foto + caption). Atualizações editam o card.
- ⚙️ Painel `/panel` no canal: oculta globalmente qualquer campo (`nome`, `id`,
  `username`, `phone`, `bio`, `grupos`, `historico`, `foto`).
- 🗑 Usuário pode pedir remoção dos próprios dados:
  - DM ao bot: `/remover`
  - O bot avisa o dono em DM com botões **Remover / Negar**.

## Instalação
```bash
cd "User Info Bot PRO v8.0"
pip install -r requirements.txt
python main.py
```

> Ajuste `NOTIFY_CHANNEL_ID` em `config.py` se o canal mudar.
> O bot precisa ser **administrador do canal** com permissão de postar e editar.

## Comandos do owner (no canal)
| Comando             | Função                                          |
|---------------------|-------------------------------------------------|
| `/scan`             | Força uma varredura imediata                    |
| `/panel`            | Abre o painel de toggles globais                |
| `/hide <campo>`     | Oculta o campo nos cards                        |
| `/show <campo>`     | Mostra o campo nos cards                        |
| `/auth <id\|@user>` | Autoriza usuário a ver telefone via inline      |
| `/unauth <id\|@user>` | Remove autorização de telefone                |
| `/auths`            | Lista todos os autorizados                      |

Campos válidos: `nome id username phone bio grupos historico foto`.

## Regras de visibilidade
- 🔄 **Varredura**: roda manualmente via `/scan` e automaticamente a cada 60 minutos.
- 📺 **Canal**: recebe os cards COMPLETOS (sujeitos ao painel `/panel`).
- 🔎 **Inline (@bot @user / @bot 123)**: mostra todos os dados, mas o **telefone fica restrito** — apenas usuários autorizados via `/auth` (e o dono) o veem.
- 🚫 **DM**: o bot **nunca** consulta dados em DM. Apenas `/start` e `/remover`.


## Estrutura
```
User Info Bot PRO v8.0/
├── main.py
├── config.py
├── db.py
├── format.py
├── profile.py
├── notifier.py
├── scan.py
├── search.py
├── handlers.py
├── requirements.txt
└── data/                   (criado em runtime)
    ├── user_database.json
    ├── card_index.json
    ├── settings.json
    └── monitor.log
```

👨‍💻 Créditos: **Edivaldo Silva** — [@Edkd1](https://t.me/Edkd1)
