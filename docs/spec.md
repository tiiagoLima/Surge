# Spec — Personal Automation Hub (Surge)

> Documento de referência para desenvolvimento orientado a spec (spec-driven development).
> Este arquivo é a fonte de verdade para ferramentas de IA (OpenCode, Claude Code) gerarem a
> base do repositório. Alterações de arquitetura devem ser refletidas aqui antes de virar código.

## 1. Objetivo

O objetivo não é resolver um problema único, mas ter uma **base extensível** onde novas
automações pessoais possam ser adicionadas ao longo do tempo sem reescrever o núcleo.

Agente personificado: **Surge**.

**Módulo inicial (MVP):** `investment_scanner` — monitora ativos da B3 e do mercado global,
identifica quedas relevantes e notifica por e-mail e Telegram.

**Módulos previstos (não implementados agora, mas que a arquitetura deve suportar sem refatoração
estrutural):** contas a pagar, automações relacionadas à faculdade.

**Objetivos secundários:** peça de portfólio; exercício deliberado de POO, Clean Architecture e DDD tático.

## 2. Decisões de Arquitetura

### ADR-0001 — Hexagonal (Ports & Adapters)
Domínio não depende de detalhe técnico. Toda comunicação externa passa por portas.

### ADR-0002 — DDD tático dentro da camada de domínio
Entidades como `Quote`, `Opportunity` são objetos ricos, imutáveis.

### ADR-0003 — Python 3.13 com ambiente virtual isolado
`venv` + `pyproject.toml` (PEP 621). Python 3.13 escolhido por ecossistema maduro (vs 3.14 free-threading ainda em adoção).

### ADR-0004 — Docker para deploy
Imagem Docker é artefato de deploy. `docker-compose.yml` espelha produção. Agendamento dentro do container (APScheduler).

### ADR-0005 — CI cobre lint, testes e build de imagem

### ADR-0006 — Pasta `agents/skill` como instruções para ferramentas de IA

### ADR-0007 — Bounded contexts com hexágonos independentes
O código é organizado primeiro por contexto de negócio e, dentro de cada contexto, por domínio, aplicação e adapters. `investments` contém a automação financeira; `memory` contém a fundação de memória semântica; `shared` contém apenas preocupações transversais. O composition root em `src/main.py` é o único ponto que compõe contexts.

## 3. Estrutura de Pastas (context-first — núcleo em `src/`)

```
surge/
├── docs/
│   └── spec.md
├── agents/
│   └── skill/
│       ├── README.md
│       ├── code-conventions.md
│       ├── new-automation.md
│       └── testing-guidelines.md
├── src/
│   ├── investments/                # bounded context de investimentos
│   │   ├── domain/                 # modelos e portas de investimentos
│   │   ├── application/            # carteira, scanner, radar e e-mails
│   │   ├── adapters/
│   │   │   ├── inbound/            # IMAP e scheduler
│   │   │   └── outbound/           # Brapi, yfinance, SQLite e notificadores
│   │   └── assets/templates/       # templates Jinja2 financeiros
│   ├── memory/                     # bounded context de memória semântica
│   │   ├── domain/                 # ISemanticMemoryPort
│   │   ├── application/            # salvar preferências e buscar contexto
│   │   └── adapters/outbound/      # fake em memória, substituível por vector store
│   ├── shared/
│   │   └── config.py               # configuração transversal
│   └── main.py                     # composition root e CLI
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .github/workflows/ci.yml
├── .env.example
├── pyproject.toml
└── README.md
```

Pacote importável: `src` (distribuição `surge`). Imports seguem `src.<contexto>.<camada>`, por exemplo `src.investments.domain.models` e `src.memory.domain.ports`; não crie novos módulos em camadas técnicas globais.

## 4. Convenções de Código

- Type hints obrigatórios
- Docstrings Google style
- Imutabilidade (`@dataclass(frozen=True)`)
- `PascalCase` classes, `snake_case` funções, sufixo `Port` em portas
- `ruff` + `black`
- Sem lógica de negócio em adapters

## 5. Estratégia de Testes

- `tests/unit/`: domain + application com fakes
- `tests/integration/`: adapters reais

## 6. Scanner portfolio-aware (sem hardcode)

- Nenhum ticker em env: `SURGE_WATCHLIST` foi removido. Carteira vive no SQLite
  via `PortfolioPort` (`holdings`: ticker, quantity, avg_price, currency, added_at).
- `ManagePortfolioUseCase.add/remove/list/get` — agnóstico (CLI é só inbound adapter;
  futuro `TelegramInboundAdapter` reusa o mesmo use case). `add` valida o ticker
  via `QuotePort.get_quote()` (Brapi free) antes de persistir.
- `ScanPortfolioUseCase` — monitora holdings locais, alerta se queda >= threshold e associa os dados da posição ao alerta.
- Alertas de carteira podem exibir custo, valor atual e P&L não realizado quando `avg_price` estiver cadastrado.
- O sistema é somente informativo nesta fase: não executa compras, vendas ou rebalanceamentos.
- Com IMAP habilitado, mensagens não lidas com assunto `SURGE: INVESTIMENTO` são parseadas e registram compras na carteira; outros assuntos ficam disponíveis para futuras automações.
- A primeira versão usa senha de app do Gmail; OAuth2 fica planejado para o deploy na VPS.
- `MarketRadarUseCase` — consome `QuotePort.list_market_quotes()` (Brapi
  `GET /api/quote/list`, free) e retorna quedas >= threshold excluindo a carteira.
- Threshold: queda de 5% vs fechamento anterior (configurável via `SURGE_DROP_THRESHOLD`).
- Fonte primária: yfinance; fallback/validação/radar: brapi.dev.

## 7. Docker

Multi-stage build, compose com .env, scheduler interno.

## 8. CI

Lint + testes unitários obrigatórios + build Docker.

## 9. Critérios de Aceite — Fase 1 (Bootstrap)

- [x] Estrutura com `src/`
- [x] `domain/ports.py` e `domain/models.py`
- [x] Use cases de portfólio e radar (`ScanPortfolioUseCase`, `MarketRadarUseCase`, `ManagePortfolioUseCase`) com DI
- [x] Adapters outbound funcionais (YFinance, Brapi, SQLite, Email, Telegram, Composite)
- [x] `main.py` composition root
- [x] `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `ci.yml`
- [x] `agents/skill/new-automation.md` antes dos adapters
- [x] README com setup venv e arte conceitual
