# Backend — Auto-SERE

Contém toda a regra de negócio do sistema. Nenhuma lógica de negócio
deve existir nos frontends — eles apenas consomem esta API.

## Módulos

- `api/` — rotas e endpoints expostos ao frontend.
- `core/` — configuração central, exceptions, inicialização da aplicação.
- `models/` — entidades e schemas de dados.
- `services/` — regras de negócio (orquestram repositories e workers).
- `repositories/` — camada de acesso a dados/banco (nenhum SQL fora daqui).
- `workers/` — tarefas assíncronas e processamento em background (ex: OCR).
- `scheduler/` — automações agendadas (substitui loops soltos pelo projeto).
- `utils/` — funções auxiliares genéricas, sem regra de negócio.
- `config/` — arquivos de configuração (YAML/JSON), sem segredos versionados.
- `scripts/` — scripts legados em processo de migração para os módulos acima.

## Padrões obrigatórios

- Type hints em todo código novo.
- Logging (nunca `print`) com timestamp, nível, origem e stacktrace quando necessário.
- Sem caminhos absolutos, senhas fixas ou tokens no código — tudo via configuração/env.
