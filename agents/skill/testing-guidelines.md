# Testing Guidelines — Surge

## Estrutura
- `tests/unit/` — domain + application com fakes/mocks, sem I/O real, deve rodar em segundos
- `tests/integration/` — adapters reais (ex: yfinance com rede), pode ser lento

## Regras
- Cada `UseCase` precisa de testes unitários com ports fakeadas
- Cada `Port` precisa de pelo menos um adapter fake para teste
- Não usar rede em `tests/unit/` — sempre fake
- Testes de adapters em `tests/integration/` marcados com `pytest.mark.integration` (opcional), rodam separado no CI
- Cobertura não é meta — comportamento é meta

## Como escrever
```python
# tests/unit/test_scan_portfolio.py
from src.investments.domain.models import Quote
from src.investments.domain.ports import QuotePort, NotificationPort, StoragePort

class FakeQuotePort(QuotePort):
    def get_quote(self, ticker): ...

class FakeNotifier(NotificationPort):
    def __init__(self): self.sent = []
    def notify(self, opps): self.sent.extend(opps)
    def notify_error(self, msg): ...
```

## Comandos
- `pytest tests/unit -q` — obrigatório no CI
- `pytest tests/integration -q` — roda se secrets disponíveis
- `pytest --cov=src tests/unit`
