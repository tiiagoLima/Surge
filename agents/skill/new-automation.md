# Como Criar uma Nova Automação — Surge

> Siga este passo a passo para adicionar um caso de uso sem quebrar Hexagonal/DDD. Leia `docs/spec.md` antes.

## 1. Escolher o bounded context e modelar o domínio

Antes de criar arquivos, defina o contexto delimitado. Reutilize `src/investments/` para carteira, cotações e alertas; use `src/memory/` para memória semântica. Para um conceito novo e independente, crie `src/<contexto>/` com seu próprio hexágono.

Crie/edite `src/<contexto>/domain/models.py`:
- Entidades como `@dataclass(frozen=True)`
- Value objects imutáveis
- Métodos ricos (ex: `is_significant_drop()` em `Quote`) — não apenas dados

Se o novo módulo tem conceito conflitante (ex: um `Ticker` com significado diferente), crie ou use outro bounded context; não compartilhe modelos de domínio entre contexts.

## 2. Definir portas (ISP estrito)

Edite `src/<contexto>/domain/ports.py`:
```python
class MyPort(ABC):
    @abstractmethod
    def do_something(self, ...) -> ...: ...
```
Portas são interfaces abstratas. Nunca importe adapter aqui.
Não engorde portas existentes — crie uma porta nova e segregada
(ex: `PortfolioPort` separada de `StoragePort`, mesmo que o mesmo
adapter SQLite implemente ambas). Regras de negócio dependem só dos
métodos estritos da sua porta.

## 3. Criar o UseCase (agnóstico à entrada — ChatOps-ready)

Crie `src/<contexto>/application/<meu_modulo>_use_case.py`:
```python
from src.<contexto>.domain.ports import MyPort

class MyUseCase:
    def __init__(self, port: MyPort) -> None:
        self._port = port

    def execute(self) -> ...:
        # só lógica de negócio, sem I/O concreto
        ...
```
- Injeção via `__init__` — nunca instanciar adapter dentro do UseCase
- Assinaturas agnósticas: o use case não sabe se é chamado pela CLI
  (`src/main.py`) ou por um futuro `TelegramInboundAdapter`
  (ex: `ManagePortfolioUseCase.add/remove/list/get` sem `argparse` dentro).
- Type hints obrigatórios, docstring Google style
- Padrões de referência: `ScanPortfolioUseCase` (monitora o que é meu),
  `MarketRadarUseCase` (descobre o mercado via `list_market_quotes()` e
  exclui o que já tenho).

## 4. Implementar adapters

Crie em `src/<contexto>/adapters/outbound/` (ou `inbound/` para gatilhos):
```python
from src.<contexto>.domain.ports import MyPort

class MyAdapter(MyPort):
    def do_something(self, ...) -> ...:
        # traduz formato externo <-> modelo de domínio
        ...
```
- Um adapter só traduz. Se começar a decidir regra de negócio, mova para `application/`

## 5. Registrar no composition root

Edite `src/main.py`:
- Instancie adapters concretos
- Injete nos UseCases
- Adicione trigger (scheduler, webhook, email) em `src/<contexto>/adapters/inbound/`

## 6. Testes

- `tests/unit/test_<meu_modulo>.py` — UseCase com fakes das portas
- `tests/integration/test_<meu_adapter>.py` — adapter real (se precisar de I/O)

## 7. Config

Se precisar de env vars, adicione em `src/shared/config.py` (`Settings`) e documente em `.env.example`.

## Checklist

- [ ] Models imutáveis?
- [ ] Porta com sufixo `Port`?
- [ ] UseCase sem importar adapter?
- [ ] Adapter sem regra de negócio?
- [ ] Injetado em `main.py`?
- [ ] Testes unit com fakes?
- [ ] `.env.example` atualizado?
