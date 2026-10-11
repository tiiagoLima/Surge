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
O código é organizado primeiro por contexto de negócio e, dentro de cada contexto, por domínio, aplicação e adapters. `investments` contém a automação financeira; `finances` contém despesas, fluxo de caixa e tetos orçamentários; `memory` contém a fundação de memória semântica; `shared` contém apenas preocupações transversais. O composition root em `src/main.py` é o único ponto que compõe contexts.

### ADR-0008 — Insights analíticos com LLM desacoplados (MarketAnalystPort)
O motor de regras financeiras (cálculo de quedas, P&L, limites de despesas) é e deve continuar 100% determinístico. A integração com LLM (Google Gemini via `google-genai`) atua exclusivamente como analista consultivo desacoplado através de `MarketAnalystPort`, sem interferir nos cálculos numéricos ou disparar ordens sem controle.

### ADR-0009 — Bounded context de Finanças Pessoais (`finances`)
A gestão financeira diária (registro de despesas, categorização e controle de teto mensal por `CategoryBudget`) é modelada como um bounded context separado de `investments`. Preserva seu próprio ciclo de dados no SQLite (`finance_transactions` e `finance_budgets`) com entidades imutáveis e ricas em comportamento.

### ADR-0010 — Evolução pragmática para Agent Runtime pessoal
O Surge evolui de um orquestrador determinístico orientado a scripts para um **Agente Pessoal Assistivo**, mantendo simplicidade arquitetural ("simples, mas não bobo", sem sobrecarga de frameworks genéricos).
- **Core de Negócio:** Mantém regras matemáticas e persistência estritamente determinísticas em Python puro e SQLite.
- **Agent Runtime:** Um loop de raciocínio controlado que interpreta intenções em linguagem natural, recupera contexto histórico da memória e orquestra execuções através de *tool calling* sobre os casos de uso existentes.

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
│   ├── finances/                   # bounded context de finanças pessoais
│   │   ├── domain/                 # models (Transaction, CategoryBudget) e ports.py
│   │   ├── application/            # register_expense_use_case.py
│   │   └── adapters/outbound/      # sqlite_repository.py
│   ├── investments/                # bounded context de investimentos
│   │   ├── domain/                 # modelos e portas de investimentos
│   │   ├── application/            # carteira, scanner, radar e e-mails
│   │   ├── adapters/
│   │   │   ├── inbound/            # IMAP e scheduler
│   │   │   └── outbound/           # Brapi, yfinance, SQLite, Gemini e notificadores
│   │   └── assets/templates/       # templates Jinja2 financeiros
│   ├── memory/                     # bounded context de memória semântica
│   │   ├── domain/                 # ISemanticMemoryPort
│   │   ├── application/            # salvar preferências e buscar contexto
│   │   └── adapters/outbound/      # fake em memória, evoluível para vector store
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

## 7. Bounded Context de Finanças Pessoais (`finances`)

- Rastreamento diário de despesas e receitas através de `Transaction` imutável.
- `CategoryBudget` calcula saldo disponível (`remaining`), percentual consumido (`usage_pct`), alerta preventivo aos 80% (`is_warning`) e estouro do orçamento (`is_exceeded`).
- Use case agnóstico: `RegisterExpenseUseCase` orquestra salvamento e status de teto orçamentário sem depender de CLI ou Telegram.
- Persistência dedicada em SQLite (`FinanceSqliteRepository`), isolando tabelas de finanças das tabelas de investimentos.

## 8. Arquitetura Atual vs. Visão Alvo (Diagramas UML)

### 8.1 Arquitetura Atual — Orquestrador Hexagonal Determinístico

Hoje o Surge opera como um hub de automações com pipelines pré-definidas disparadas por Scheduler ou CLI:

```mermaid
classDiagram
    direction TB

    package "Composition Root (src/main.py)" {
        class MainRoot {
            +main()
            +run_scheduler()
            +build_scan_portfolio_use_case()
            +build_register_expense_use_case()
        }
    }

    package "Context: investments" {
        class ScanPortfolioUseCase {
            +execute() list~Opportunity~
        }
        class MarketRadarUseCase {
            +execute() list~Opportunity~
        }
        class QuotePort {
            <<interface>>
            +get_quote()
        }
        class MarketAnalystPort {
            <<interface>>
            +analyze(opportunity)
        }
        class PortfolioPort {
            <<interface>>
            +save_holding()
            +list_holdings()
        }
    }

    package "Context: finances" {
        class RegisterExpenseUseCase {
            +execute(amount, category, description, month) ExpenseRegistrationResult
        }
        class TransactionPort {
            <<interface>>
            +save(transaction)
            +get_spent_by_category()
        }
        class BudgetPort {
            <<interface>>
            +save_budget()
            +get_budget_by_category()
        }
    }

    package "Context: memory (Foundation)" {
        class ISemanticMemoryPort {
            <<interface>>
            +save_preference()
            +search_similar_context()
        }
    }

    MainRoot --> ScanPortfolioUseCase
    MainRoot --> RegisterExpenseUseCase
    ScanPortfolioUseCase --> QuotePort
    ScanPortfolioUseCase --> MarketAnalystPort
    ScanPortfolioUseCase --> PortfolioPort
    RegisterExpenseUseCase --> TransactionPort
    RegisterExpenseUseCase --> BudgetPort
```

### 8.2 Visão Alvo — Runtime de Agente Pessoal com Tool Calling

A visão futura transforma o Surge em um assistente pessoal com loop de decisão, mantendo as regras de negócio duras sob controle:

```mermaid
classDiagram
    direction TB

    package "Inbound Gateways" {
        class TelegramChatOps {
            +handle_message(text)
            +render_keyboards()
        }
        class PayrollEmailParser {
            +poll_unread_payroll()
            +extract_salary()
        }
        class SchedulerTrigger {
            +daily_scan()
            +weekly_summary()
        }
    }

    package "Agent Core Runtime" {
        class AgentLoop {
            +process_intent(user_input, user_id)
            +plan_actions()
            +call_tool()
        }
        class ToolRegistry {
            +register(tool_spec)
            +invoke(tool_name, arguments)
        }
    }

    package "Persistent Semantic Memory" {
        class PersistentMemoryPort {
            <<interface>>
            +store_memory(content, tags)
            +search_vector(query, limit)
        }
        class SqliteVectorStore {
            +fts_search()
            +vector_similarity()
        }
    }

    package "Deterministic Tools (Domain Hexagons)" {
        class FinanceTools {
            +register_expense()
            +set_monthly_budget()
            +get_budget_balance()
        }
        class InvestmentTools {
            +scan_portfolio()
            +get_radar_opportunities()
        }
    }

    TelegramChatOps --> AgentLoop : Mensagem / Botões
    PayrollEmailParser --> AgentLoop : Salário identificado
    SchedulerTrigger --> AgentLoop : Resumo programado

    AgentLoop --> ToolRegistry : Tool Calling
    AgentLoop --> PersistentMemoryPort : Recuperação contextual
    PersistentMemoryPort <|.. SqliteVectorStore

    ToolRegistry --> FinanceTools : Execução matemática estrita
    ToolRegistry --> InvestmentTools : Consulta de cotações
```

### 8.3 Filosofia de Evolução do Agente

- **Simples, mas não bobo:** Evitar frameworks pesados ou caixa-preta; construir um loop de agente transparente sobre a base de Python + SQLite.
- **Divisão de Responsabilidades:** O LLM **nunca** calcula saldos, percentuais ou quedas financeiras por conta própria. Ele interpreta linguagem natural, seleciona as ferramentas e sintetiza a comunicação com o usuário.
- **Roteiro em 4 Fases:**
  1. *Fase 1 (Atual - Bootstrap & Hexágonos):* Domínios ricos, Use Cases e SQLite para investimentos e despesas.
  2. *Fase 2 (Memória Persistente):* Migração do adapter de memória de RAM para SQLite persistente, corrigindo ciclo de vida no composition root.
  3. *Fase 3 (Memória Semântica com Embeddings):* Geração local/remota de embeddings com busca vetorial (`sqlite-vec` / FTS5).
  4. *Fase 4 (Agent Runtime & ChatOps):* Loop de tool calling e interface bidirecional via Telegram e parser de holerites.

## 9. Docker

Multi-stage build, compose com .env, scheduler interno.

## 10. CI

Lint + testes unitários obrigatórios + build Docker.

## 11. Critérios de Aceite e Fases do Projeto

### Fase 1 — Bootstrap & Scanner de Investimentos
- [x] Estrutura com `src/` e bounded contexts independentes
- [x] `domain/ports.py` e `domain/models.py` (Quote, Holding, Opportunity)
- [x] Use cases de portfólio e radar (`ScanPortfolioUseCase`, `MarketRadarUseCase`, `ManagePortfolioUseCase`)
- [x] Adapters outbound funcionais (YFinance, Brapi, SQLite, Email, Telegram, Composite)
- [x] Templates Jinja2 para relatórios de oportunidades em Dark Mode
- [x] `main.py` composition root e CLI

### Fase 2 — Finanças Pessoais & LLM Insights
- [x] Contexto `finances` modelado (`Transaction`, `CategoryBudget`)
- [x] Regras de orçamento: limites, cálculo de consumo, alerta de 80% e estouro
- [x] Portas `TransactionPort` e `BudgetPort` com adapter `FinanceSqliteRepository`
- [x] `RegisterExpenseUseCase` implementado e coberto por testes unitários
- [x] Inbound adapter do Telegram com menus inline (`surge bot`) para gastos, tetos e panorama mensal
- [x] Integração consultiva do Gemini via `MarketAnalystPort` para síntese analítica
- [x] Testes unitários com fakes rodando sem I/O real

### Fase 3 — Memória Semântica Persistente
- [ ] Persistência de preferências em SQLite (`memory_store`)
- [ ] Ciclo de vida unificado da memória no composition root (`src/main.py`)
- [ ] Integração com geração de embeddings e busca híbrida (FTS5 + similaridade vetorial)

### Fase 4 — Agent Runtime & ChatOps
- [ ] Runtime de agente com loop ReAct / Tool Calling
- [ ] Bot interativo no Telegram com menus para registro de gastos e divisão de salário
- [ ] Parser de e-mails de folha de pagamento (extração de valor líquido)
- [ ] Resumos semanais consolidados com insights contextuais da IA

