<table>
  <tr>
    <td valign="top">
<pre>
      %*-.
      %--****%%%%%%**-
     *%-#*--**%%%%****%%---*%%
     @@@@@%---*%--*%**---*%#*
    -@@####@%-*..--****%#@@@#
   -*%##@@@@@%**-***%#@@@@@@%
 **%%-#@@@@@@@#***%@@@@@@@@@-
%%***%%#%##**-**-*%@@@@@@@%-*
-#*****%%%%---------*#%***-*.
 %%****%%%#*%%%%%%%**%--*--%
 .#*****%%%       ..--**%%*.
  *%%%%**-
</pre>
    </td>
    <td valign="top">

# Surge — Personal Automation Hub

> Plataforma pessoal de automações em Python.  
> **MVP:** `investment_scanner` — monitora B3/global, detecta quedas >= 5% e notifica por e-mail/Telegram.  
> **Arquitetura:** Hexagonal (Ports & Adapters) + DDD tático.

</td>
  </tr>
</table>

## Quickstart (venv)

```powershell
# 1. Criar venv com Python 3.13
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar
pip install -e ".[dev]"

# 3. Configurar
Copy-Item .env.example .env
# edite .env conforme necessário (sem tickers — carteira via CLI)

# 4. Gerenciar carteira (validada via Brapi free, sem hardcode)
python -m src.main portfolio add PETR4.SA --qty 100 --avg 30
python -m src.main portfolio list

# 5. Scans avulsos
python -m src.main scan --portfolio          # só holdings
python -m src.main scan --radar              # mercado (Brapi), exclui carteira
python -m src.main scan --once               # ambos, uma única execução
python -m src.main scan                      # ambos, uma única execução

# 6. Rodar com scheduler (todo dia útil 18h, portfolio + radar)
python -m src.main
# ou via entrypoint:
surge scan --portfolio
surge
```

## Templates e Notificação por E-mail

```powershell
# Visualizar o e-mail de alerta no navegador (sem enviar):
surge test-email --preview

# Enviar e-mail de teste real via SMTP:
surge test-email --send
```

Os templates HTML ficam em `src/investments/assets/templates/` e são renderizados com **Jinja2**.
O design segue estilo Dark Mode financeiro, com badges vermelhos/verdes, tabela responsiva e header com a marca Surge.

## Docker

```powershell
Copy-Item .env.example .env
docker compose -f docker/docker-compose.yml up --build
# Scans avulsos:
docker compose -f docker/docker-compose.yml run --rm surge surge scan --portfolio
docker compose -f docker/docker-compose.yml run --rm surge surge scan --radar
```

## Configuração

| Var | Default | Descrição |
|-----|---------|-----------|
| `SURGE_DROP_THRESHOLD` | `5.0` | Queda % vs fechamento anterior |
| `SURGE_DB_PATH` | `./surge.db` | SQLite |
| `SURGE_TELEGRAM_ENABLED` | `false` | Ativa Telegram |
| `SURGE_EMAIL_ENABLED` | `false` | Ativa e-mail SMTP |
| `SURGE_SMTP_HOST` | — | Servidor SMTP (ex: `smtp.gmail.com`) |
| `SURGE_SMTP_PORT` | `587` | Porta SMTP (TLS) |
| `SURGE_SMTP_USER` | — | Usuário SMTP |
| `SURGE_SMTP_PASSWORD` | — | Senha / App Password |
| `SURGE_EMAIL_FROM` | — | Remetente |
| `SURGE_EMAIL_TO` | — | Destinatário |

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.13+ |
| Arquitetura | Hexagonal (Ports & Adapters) + DDD tático |
| Dados | SQLite via `sqlite3` (stdlib) |
| Config | `pydantic-settings` + `.env` |
| Cotações | `yfinance` + Brapi (fallback composto) |
| Notificação | SMTP (`smtplib`) + Telegram Bot API |
| Templates HTML | **Jinja2** (`src/investments/assets/templates/`) |
| Agendamento | APScheduler |
| Testes | `pytest` + fakes (sem mocks de framework) |
| Qualidade | `ruff` + `black` |
| Deploy | Docker + Docker Compose |

## Arquitetura

```
src/
  investments/   → bounded context de investimentos
    domain/      → models.py e ports.py de carteira, cotações e alertas
    application/ → manage, scan, radar e importação de e-mails
    adapters/    → inbound (IMAP, scheduler) e outbound (Brapi, yfinance, SQLite, notificadores)
    assets/      → templates Jinja2 de alertas financeiros
  memory/        → bounded context de memória semântica
    domain/      → ISemanticMemoryPort
    application/ → salvar preferências e buscar contexto
    adapters/    → FakeSemanticMemoryAdapter provisório
  shared/        → infraestrutura transversal, incluindo config.py
  main.py        → composition root e adapter CLI (portfolio, scan, test-email)
agents/skill/   → instruções para IAs e colaboradores
```
Cada contexto preserva seu próprio hexágono: domínio define portas, aplicação depende apenas delas e adapters implementam detalhes externos. O `main.py` é o único ponto que conhece e compõe os contexts. Sem hardcode: carteira via `surge portfolio add` (SQLite + validação Brapi); radar via Brapi `/api/quote/list`.

Nova automação? Leia `agents/skill/new-automation.md`.

## Testes

```powershell
pytest tests/unit -v
pytest tests/integration -v  # requer rede
ruff check .
black --check .
```

## CI

`ci.yml` roda lint + testes unitários + `docker build` em PR para `main`.

## Roadmap

- [ ] Contas a pagar
- [ ] Faculdade (alertas de tarefas/provas)
- [ ] Agentes de IA (Surge personificado)

### Alertas da carteira

Os alertas gerados pelo scanner da carteira incluem, quando o preço médio foi informado, quantidade, custo da posição, valor atual e P&L não realizado. O Surge apenas notifica: nenhuma ordem de compra ou venda é executada automaticamente.

### Registrar compras por e-mail

Configure uma senha de app do Gmail no `.env` e habilite o IMAP. O scheduler lê mensagens não lidas com assunto iniciado por `SURGE: INVESTIMENTO`:

```text
Assunto: SURGE: INVESTIMENTO

Hoje comprei 10 cotas de PETR4 por R$ 30,00
```

O ativo é validado via Brapi. Compras posteriores consolidam quantidade e preço médio; mensagens válidas são marcadas como lidas. Mensagens de outros assuntos permanecem disponíveis para futuras automações.
