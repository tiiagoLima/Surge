<table>

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

# 7. Iniciar o Bot Interativo no Telegram (Finanças)
python -m src.main bot
# ou via entrypoint:
surge bot
```

## Bot Interativo no Telegram (Finanças e Carteira)

```powershell
# Executa o bot com menus interativos (long-polling):
surge bot
```

- Envie `/start` ou `/menu` para abrir o menu com botões inline:
  - `[➕ Registrar Gasto]` ➔ Selecione a categoria (`Alimentação`, `Lazer`, etc.) e envie o valor com descrição.
  - `[📊 Resumo Gastos]` ➔ Veja o panorama financeiro com gastos, tetos, consumo % e alertas.
  - `[🎯 Definir Teto]` ➔ Defina ou ajuste o limite mensal da categoria.
  - `[💼 Minha Carteira]` ➔ Visualize sua carteira declarada com tickers, cotas, PM e valor total.
  - `[➕ Adicionar Ativo]` ➔ Declare um ativo pelo Telegram (ex: `PETR4 100 34.50` com validação de cotação).
  - `[➖ Remover Ativo]` ➔ Remova posições com botões clicáveis dinâmicos.
- Comandos rápidos de texto:
  - `/carteira` ➔ Exibe a carteira atual.
  - `/ativo PETR4 100 30` ➔ Adiciona ativo diretamente.
  - `/remover PETR4` ➔ Remove ativo diretamente.
  - `/cancelar` ➔ Cancela a operação em andamento.
- Restrição de segurança: apenas o `SURGE_TELEGRAM_CHAT_ID` autorizado consegue interagir.

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
| `SURGE_DROP_THRESHOLD` | `5.0` | Queda % vs fechamento anterior para alertar |
| `SURGE_CRON_HOUR` | `18` | Hora de execução diária do scanner |
| `SURGE_CRON_MINUTE` | `0` | Minuto de execução diária do scanner |
| `SURGE_DB_PATH` | `./surge.db` | Caminho do banco SQLite |
| `SURGE_TELEGRAM_ENABLED` | `false` | Ativa notificações via Telegram |
| `SURGE_TELEGRAM_BOT_TOKEN` | — | Token do Bot do Telegram |
| `SURGE_TELEGRAM_CHAT_ID` | — | Chat ID do destinatário no Telegram |
| `SURGE_EMAIL_ENABLED` | `false` | Ativa envio de e-mail via SMTP |
| `SURGE_SMTP_HOST` | `smtp.gmail.com` | Servidor SMTP |
| `SURGE_SMTP_PORT` | `587` | Porta SMTP (TLS) |
| `SURGE_SMTP_USER` | — | Usuário SMTP |
| `SURGE_SMTP_PASSWORD` | — | Senha / App Password do Gmail |
| `SURGE_EMAIL_FROM` | — | E-mail do remetente |
| `SURGE_EMAIL_TO` | — | E-mail do destinatário |
| `SURGE_IMAP_ENABLED` | `false` | Ativa leitura de comandos por e-mail |
| `SURGE_IMAP_HOST` | `imap.gmail.com` | Servidor IMAP |
| `SURGE_IMAP_PORT` | `993` | Porta IMAP (SSL) |
| `SURGE_IMAP_USER` | — | Usuário IMAP |
| `SURGE_IMAP_PASSWORD` | — | Senha de app para leitura IMAP |
| `SURGE_IMAP_MAILBOX` | `INBOX` | Caixa postal para monitorar |
| `SURGE_INVESTMENT_EMAIL_SUBJECT` | `SURGE: INVESTIMENTO` | Prefixo de assunto para registrar compras |
| `SURGE_EMAIL_POLL_MINUTES` | `5` | Intervalo em minutos para checagem IMAP |
| `SURGE_BRAPI_TOKEN` | — | Token da Brapi (opcional) |
| `SURGE_BRAPI_BASE_URL` | `https://brapi.dev` | URL base da API Brapi |
| `SURGE_GEMINI_API_KEY` | — | Chave de API do Google Gemini para insights |
| `SURGE_MAX_OPPORTUNITIES_PER_SCAN` | `10` | Limite máximo de oportunidades por scan |
| `SURGE_TIMEZONE` | `America/Sao_Paulo` | Fuso horário da aplicação |
| `SURGE_LOG_LEVEL` | `INFO` | Nível de log (DEBUG, INFO, WARNING) |

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
| IA / LLM | Google Gemini (`google-genai`) via `MarketAnalystPort` |
| Agendamento | APScheduler |
| Testes | `pytest` + fakes (sem mocks de framework) |
| Qualidade | `ruff` + `black` + `mypy` |
| Deploy | Docker + Docker Compose |

## Arquitetura

```
src/
  finances/      → bounded context de finanças pessoais (despesas, orçamento)
    domain/      → models.py (Transaction, CategoryBudget) e ports.py
    application/ → register_expense_use_case.py
    adapters/    → outbound (SQLite FinanceSqliteRepository)
  investments/   → bounded context de investimentos
    domain/      → models.py e ports.py de carteira, cotações e alertas
    application/ → manage, scan, radar e importação de e-mails
    adapters/    → inbound (IMAP, scheduler) e outbound (Brapi, yfinance, SQLite, Gemini, notificadores)
    assets/      → templates Jinja2 de alertas financeiros
  memory/        → bounded context de memória semântica
    domain/      → ISemanticMemoryPort
    application/ → salvar preferências e buscar contexto
    adapters/    → FakeSemanticMemoryAdapter provisório (evoluível para vector store)
  shared/        → infraestrutura transversal, incluindo config.py
  main.py        → composition root e adapter CLI (portfolio, scan, test-email, finances)
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
mypy src
```

## CI

`ci.yml` roda lint + testes unitários + `docker build` em PR para `main`.

## Roadmap

- [x] MVP `investment_scanner` (monitoramento B3/global, quedas >= 5%, alertas e-mail/Telegram)
- [x] Bounded context de Finanças Pessoais (`finances`) com registro de despesas e controle de tetos por categoria
- [x] Insights de mercado com Google Gemini via porta analítica desacoplada
- [x] ChatOps bidirecional no Telegram (bot interativo com botões para despesas, tetos e resumo mensal)
- [ ] Memória persistente (migração de memória em RAM para SQLite com embeddings e busca vetorial)
- [ ] Parser de holerite por e-mail (extração de valor líquido de salário)
- [ ] Runtime de Agente Pessoal (ReAct loop com *tool calling* sobre as ferramentas de domínio)
- [ ] Automações acadêmicas (IFMA: alertas de prazos e provas)
- [ ] Contas a pagar automatizadas


### Alertas da carteira

Os alertas gerados pelo scanner da carteira incluem, quando o preço médio foi informado, quantidade, custo da posição, valor atual e P&L não realizado. O Surge apenas notifica: nenhuma ordem de compra ou venda é executada automaticamente.

### Registrar compras por e-mail

Configure uma senha de app do Gmail no `.env` e habilite o IMAP. O scheduler lê mensagens não lidas com assunto iniciado por `SURGE: INVESTIMENTO`:

```text
Assunto: SURGE: INVESTIMENTO

Hoje comprei 10 cotas de PETR4 por R$ 30,00
```

O ativo é validado via Brapi. Compras posteriores consolidam quantidade e preço médio; mensagens válidas são marcadas como lidas. Mensagens de outros assuntos permanecem disponíveis para futuras automações.
