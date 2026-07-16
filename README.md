# Auto-SERE

Sistema integrado que unifica os scripts Python usados no dia a dia
(matrícula, SERE, OCR de documentos, dashboard, etc.) em uma aplicação
única, modular e escalável.

## Estrutura

- `backend/` — toda a regra de negócio, API, banco, scheduler, workers.
- `frontend-web/` — interface web (apenas apresentação).
- `frontend-desktop/` — interface desktop (apenas apresentação).
- `shared/` — tipos/contratos compartilhados entre backend e frontends.
- `docs/` — documentação do projeto.
- `tests/` — testes automatizados.
- `assets/` — imagens, ícones, arquivos estáticos.
- `logs/` — saída de logs da aplicação.
- `data/` — dados persistidos localmente (quando aplicável).
- `docker/` — arquivos de containerização.

## Regras do projeto

Ver `CLAUDE.md` para as diretrizes obrigatórias de arquitetura,
fluxo de trabalho e padrões de código.

## Status

Projeto em fase inicial: esqueleto de pastas criado.
Nenhum script legado foi migrado ainda.
