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

### ADR-0011 — Persistência de Memória em SQLite e Desacoplamento Textual vs. Semântico
A memória do Surge é estruturada com separação formal de responsabilidades:
- **Modelo de Domínio Rico:** Introduzida a entidade `MemoryEntry` (id, content, category, user_id, timestamps).
- **Contratos Específicos:** A porta `MemoryStoragePort` gerencia a persistência estruturada de fatos, decisões e preferências e provê busca textual parametrizada. O contrato `ISemanticMemoryPort` permanece reservado para recuperação por similaridade vetorial (embeddings) em fases posteriores.
- **Armazenamento Unificado:** Implementado o adaptador `SqliteMemoryRepository` na tabela `memory_entries` em `surge.db`, garantindo persistência atômica, sobrevivência entre reinícios e ciclo de vida compartilhado no composition root (`src/main.py`).

### ADR-0012 — Runtime Mínimo do Agente com Tool Calling Estrito e Determinístico
O Surge implementa o bounded context `src/agent/` para orquestrar conversação assistiva por chamadas de função (Function Calling):
- **Contrato Neutro de Modelo:** A interface `AgentModelPort` abstrai a comunicação com LLMs, permitindo execução 100% determinística nos testes via `FakeAgentModel` e conexão real via `GeminiAgentModel` (`SURGE_GEMINI_MODEL`, padrão `gemini-2.5-flash`). A configuração `SURGE_GEMINI_MODEL` é compartilhada com o `GeminiAnalystAdapter` (previamente com modelo fixo), preservando seu comportamento de fallback e sem alterar sua lógica de negócio.
- **Tool Registry com Validação Rigorosa:** O modelo nunca executa funções diretamente. As ferramentas residem em uma allowlist explícita no `ToolRegistry`, com validação estrita de tipos, campos obrigatórios e rejeição de campos extras.
- **Salvaguardas de Execução:** Limite rígido de turnos de modelo (`max_model_turns = 3`) previne loops infinitos. Em caso de exceções, os detalhes técnicos ficam restritos aos logs (`logger.exception`) e mensagens controladas são retornadas ao modelo.
- **Preservação de IDs de Função:** O adapter Gemini preserva com precisão o identificador de chamada de função (`FunctionCall.id` e `FunctionResponse.id`) entre as rodadas conversacionais. IDs locais de fallback não são enviados ao provedor como IDs de correlação.
- **Restrição Contra Tarefas de Programação:** O Surge é estritamente um assistente pessoal para finanças e investimentos. Pedidos de escrita, revisão, debug ou execução de código, bem como solicitações de acesso ao sistema de arquivos local ou comandos de terminal, são categoricamente recusados pelo runtime sem acionamento de ferramentas.
- **Cálculos Determinísticos em Python:** O modelo de IA nunca é encarregado de realizar operações aritméticas ou cálculos financeiros. O domínio (`Holding.total_cost`) e o caso de uso de aplicação (`ManagePortfolioUseCase.get_summary()`) calculam de forma determinística em Python o custo total por posição (`quantity * avg_price`), o total de posições e o total investido (inclusive agrupado por moeda) antes de disponibilizar os dados via `get_portfolio_holdings`.
  - `total_invested` é `null` quando há múltiplas moedas ou qualquer posição sem `avg_price`; não há conversão cambial nem estimativa de custos ausentes. Carteira vazia mantém total zero. `total_invested_by_currency` contém a soma dos custos conhecidos por moeda, podendo ser parcial quando faltam preços médios. Posições sem preço médio continuam listadas, sem `avg_price` e sem `total_cost` no payload.
- **Somente Leitura e Privacidade:** Nesta primeira etapa, apenas a ferramenta `get_portfolio_holdings` é disponibilizada (estritamente leitura). Não há acesso a shell, arquivos, código ou escrita. Os dados estritamente necessários da carteira são transmitidos ao provedor do modelo para compor a resposta, e o payload financeiro nunca é exposto em logs.
- **Estratégia de Testes Sem Mocks de Framework:** Testes de domínio, aplicação e ferramentas utilizam fakes explícitos em memória (como `FakePortfolioUseCase` e `FakeAgentModel`), reservando doubles do SDK externo exclusivamente para os testes de adapters.

### ADR-0013 — Independência Operacional do LLM e Requisitos de Capacidades
O LLM é uma capacidade opcional de inteligência e enriquecimento, não uma dependência universal do núcleo determinístico. O domínio `src/agent/domain/capabilities.py` usa somente a biblioteca padrão e separa **Demanda** (`CapabilityRequirements`) de **Oferta** (`RuntimeAvailability`), ambas imutáveis e com dimensões `llm`, `network` e `storage`. A demanda aceita exclusivamente membros de `RequirementLevel` (`StrEnum`): `REQUIRED` (`required`) impede execução quando ausente; `OPTIONAL` (`optional`) permite execução degradada quando ausente; `NOT_REQUIRED` (`not_required`, padrão) não exige o recurso. A oferta aceita apenas booleanos, falsos por padrão. Definições exigem IDs não vazios e requisitos tipados; o registro puro rejeita duplicatas e não faz I/O.

`is_eligible` verifica apenas os recursos `REQUIRED`; `is_fully_supported` verifica os `REQUIRED` e `OPTIONAL`. Ambos lançam `KeyError` para IDs desconhecidos. O futuro Execution Coordinator (Issue #18) usará essas consultas para direcionar modo pleno versus modo degradado; não é implementado nesta etapa, que não adiciona gates nem altera fluxos existentes.

O composition root declara armazenamento `REQUIRED` para `portfolio.get_holdings` e `memory.manage`; rede e armazenamento `REQUIRED` para `portfolio.manage`, pois a inclusão valida o ticker por cotação; e todos os recursos `REQUIRED` para `agent.ask`. `investment.scan_portfolio` exige rede e armazenamento, com LLM `OPTIONAL`: o `ScanPortfolioUseCase` é o paradigma de degradação graciosa, mantendo regras determinísticas sem enriquecimento por LLM. Sem LLM é elegível mas não plenamente suportado; com todos os recursos é plenamente suportado; sem rede é inelegível.

Construir o registro não lê configuração nem constrói o runtime do agente. `get_runtime_capabilities()` retorna `RuntimeAvailability` usando `bool(settings.gemini_api_key)` para LLM e assumindo rede e armazenamento disponíveis; não verifica conectividade, validade da credencial ou saúde de serviços. As declarações não substituem validações próprias dos casos de uso.

### ADR-0014 — Falhas Normalizadas e Saúde Observável dos Provedores LLM
O domínio puro `src/agent/domain/provider_health.py` declara falhas e snapshots imutáveis de saúde, sem dependência de SDK. As categorias são `AUTHENTICATION`, `CONFIGURATION`, `RATE_LIMIT`, `TEMPORARY_UNAVAILABLE`, `TIMEOUT`, `INVALID_REQUEST`, `PERMANENT` (reservada para falhas permanentes explícitas) e `UNKNOWN`. O classificador da borda traduz códigos HTTP/status simbólicos e timeouts; falhas desconhecidas não são consideradas retentáveis. A indicação `retryable` é informativa: não há retry automático nesta etapa.

Os adapters Gemini começam `UNAVAILABLE` sem chave e `DEGRADED` com chave ainda não verificada. Sucesso de geração ou probe leva a `AVAILABLE`, limpando a falha anterior; falha retentável leva a `DEGRADED`, e não retentável a `UNAVAILABLE`. `get_health()` apenas retorna o snapshot em memória; `check_health()` é um probe explícito via `client.models.get(model=...)`, sem geração de conteúdo. Saúde observada não garante sucesso futuro, não altera configuração e não adiciona probes ao scanner ou à inicialização.

`GeminiAgentModel` encapsula falhas em `ProviderError`, preservando a exceção original apenas para diagnóstico explícito. Logs e mensagens normalizadas usam textos fixos seguros, nunca payloads do SDK, credenciais, prompts ou traceback. O sanitizador na borda mascara formatos comuns de chaves/tokens; ele não autoriza registrar payloads completos. O runtime mantém captura genérica de `Exception` (incluindo `ProviderError`) para não importar adapters na aplicação, retornando mensagem amigável sem detalhes técnicos. A sanitização da mensagem é responsabilidade da borda, não do domínio.

`GeminiAnalystAdapter` observa a mesma saúde, mas mantém exatamente o fallback `Insight indisponível devido a erro na API de análise.` e não propaga falhas de análise ao `ScanPortfolioUseCase`. O scanner continua calculando, persistindo e notificando oportunidades deterministicamente, sem depender da saúde do LLM. Nenhuma dependência, modelo configurado, schema de banco ou estratégia de deploy é alterada.

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
│   ├── agent/                      # bounded context do assistente pessoal e runtime
│   │   ├── domain/                 # models (AgentMessage, ToolCall, ToolResult) e ports
│   │   ├── application/            # agent_runtime.py, tool_registry.py
│   │   └── adapters/               # outbound (gemini_agent_model, fake_agent_model) e tools
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
│   ├── memory/                     # bounded context de memória e preferências
│   │   ├── domain/                 # models (MemoryEntry) e ports (MemoryStoragePort)
│   │   ├── application/            # use cases (manage_memory, save_preference, search_memory)
│   │   └── adapters/outbound/      # sqlite_memory_repository.py, fake_memory_adapter.py
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

### Fase 3 — Memória Persistente e Semântica
- [x] Persistência de preferências e fatos em SQLite (`memory_entries`)
- [x] Entidade de domínio rica `MemoryEntry` e contrato `MemoryStoragePort` desacoplado de vetores
- [x] Ciclo de vida unificado da memória no composition root (`src/main.py`) e CLI (`surge memory`)
- [x] Testes de persistência com validação de sobrevivência a reinício de processo
- [ ] Integração com geração de embeddings e busca híbrida (similaridade vetorial / ChromaDB / sqlite-vec)

### Fase 4 — Agent Runtime & ChatOps
- [x] Runtime de agente com loop conversacional e Tool Calling seguro (`src/agent/`)
- [x] Contrato neutro `AgentModelPort`, simulador `FakeAgentModel` e adaptador Gemini (`SURGE_GEMINI_MODEL`)
- [x] Allowlist e validação estrita de argumentos no `ToolRegistry` (rejeição de campos extras)
- [x] Ferramenta de leitura de carteira `get_portfolio_holdings` sem cálculos ad-hoc no adapter
- [x] Subcomando CLI `surge ask` para experimentação de ponta a ponta
- [ ] Integração do Runtime com o bot interativo do Telegram
- [ ] Persistência de sessões de conversa e consolidação de memória
- [ ] Parser de e-mails de folha de pagamento (extração de valor líquido)
- [ ] Resumos semanais consolidados com insights contextuais da IA

