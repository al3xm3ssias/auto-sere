# Plano de Migração — backend/services/sere_automation/

Status: AGUARDANDO APROVAÇÃO — nenhum código foi movido ainda.

## 1. Achado estrutural principal

29 scripts reimplementam manualmente o mesmo bloco de login Playwright:

```python
await page.goto(URL)
await page.fill("#CHAVE", LOGIN)
await page.fill("#CHAVE_ENCRIPT", SENHA)
await page.click("//input[@value='Entrar']")
await page.wait_for_timeout(3_000)
```

Scripts afetados: documentos.py, servidores.py, rematricula.py, alunos_completo.py,
coloca pareceres dos alunos transferidos.py, sere_2026.py, teste_alunos.py,
reprocessar_erros_upload.py, Upload_documentos_2026.py, alunos.py,
baixa_arquivos_sere.py, dados_funcionarios.py, pareceres.py,
Upload_exclusivo_2026.py, transferidos_destino.py,
upload_parecer_transferidos.py, editar_sus.py, processo_tranferidos.py,
historico-transferidos-2025.py, turmas.py, analise_lacunas.py, funcionarios.py,
Limpar_documentos_2026.py, analisa_arquivos_sere.py, historico_de_escolas.py,
coloca historico dos alunos transferidos.py, historicos 2025.py,
verifica arquivos p.py, Reprocessar_erros_2026.py, requerimento_matricula.py

Proposta: extrair para `sere_automation/client.py` uma função/classe
`SereClient` que abre o browser, faz login e devolve uma `page` pronta
para uso — sem mudar o comportamento de nenhuma operação existente.

## 2. Dependências reais entre scripts (ordem de migração obrigatória)

```
Reprocessar_erros_2026.py  → usa Limpar_documentos_2026.py
Upload_exclusivo_2026.py   → usa Upload_documentos_2026.py
analisa_arquivos_sere.py   → usa sere_2026.py (CGM_UPLOAD) e sere_normalizacao.py
```

Esses pares precisam ser migrados juntos, na mesma etapa, mantendo a relação
de dependência (o "filho" continua podendo reusar o que o "pai" expõe).

## 3. Casos confirmados de uso ativo e distinto (NÃO fundir/descartar)

- `Limpar_documentos_2026.py` e `sere_2026.py --limpeza`: usados para coisas
  diferentes hoje. Ambos migram, cada um preservando seu comportamento.
- `coloca historico dos alunos transferidos.py` e
  `coloca pareceres dos alunos transferidos.py`: mesmo processo de execução,
  parametrizado por tipo de documento (histórico vs. parecer). Migram como
  UM motor de processo + duas configurações de entrada, não como dois
  arquivos separados. Nenhuma das duas funcionalidades é removida.

## 4. Família "transferidos / histórico" — propósitos distintos confirmados

| Script | Propósito real |
|---|---|
| historico-transferidos-2025.py | Audita quais alunos não têm PDF de histórico gerado |
| historico_de_escolas.py | Coleta histórico de escolas anteriores via "Consulta Padrão → Por Turma" |
| historicos 2025.py | Execução pontual com lista de alunos fixa no código (não genérico) |
| transferidos-2025.py | Compara turmas.json de 2025 vs 2026 para achar transferidos (sem Playwright) |
| transferidos_destino.py | Filtra o resultado de transferidos-2025.py por ano de destino |

## 5. Pendências técnicas identificadas (para resolver durante a migração)

- Caminhos absolutos fixos (Windows `D:\ESCOLA JUDITH\...` e Linux
  `Path.home() / "compartilhado/..."`) espalhados pelos scripts — precisam
  virar configuração central (`backend/core/config.py` + variáveis de
  ambiente), por regra do próprio CLAUDE.md.
- `historicos 2025.py` tem lista de alunos hardcoded — avaliar se deve virar
  parâmetro de entrada.

## 6. Próximo passo proposto

Extrair `client.py` (login/sessão) primeiro, validando que ele reproduz
exatamente o comportamento de login já usado — sem tocar ainda nas 29
operações que o usam. Depois, migrar operação por operação, uma de cada vez,
com sua aprovação a cada etapa.

## 7. Decisões tomadas durante a extração do client.py

- Bug real encontrado em sere_2026.py (modo --limpeza): chamava
  `p.chrome.launch()`, atributo inválido no Playwright (prints diziam
  "Firefox" mas o código tentava "chrome" — nunca deveria ter funcionado
  nesse caminho específico).
- Decisão: padronizar TODO o sistema para usar Firefox como engine único
  (era o mais comum entre os scripts, e resolve a inconsistência).
- Timeout pós-login padronizado em 3000ms (era o valor predominante em
  ~90% dos scripts; 2 exceções usavam 5000ms — ver client.py para como
  isso continua configurável quando necessário).
- accept_downloads: usado por apenas 2 scripts (baixa_arquivos_sere.py,
  requerimento_matricula.py) — não é padrão, precisa ser habilitado
  explicitamente por quem chama o client.

## 8. backend/core/normalizacao.py — migrado

Migração 1:1 de sere_normalizacao.py, comportamento validado via
smoke-test embutido (11 OK / 4 falhas — EXATAMENTE igual ao original,
nenhuma regressão introduzida).

Bugs PRÉ-EXISTENTES no módulo original (não corrigidos nesta migração,
preservados propositalmente para não mudar comportamento sem discussão):
- "CPF DO RESPONSAVEL" resolve para "CPF do Responsável" em vez de
  "CPF Responsável" (dois aliases colidem no índice invertido).
- "PARECER_2026" e "PARECER_2025" resolvem para "Parecer Descritivo"
  genérico, em vez das variantes específicas "2026-1"/"2025-1" (a
  palavra-chave curta "PARECER" está vencendo por algum motivo de
  ordem de inserção, apesar do comentário no código dizer que as
  específicas deveriam vir primeiro).
- "RG_ALUNO" resolve para "RG do aluno" em vez de "RG".

## 9. Correção de inconsistência encontrada durante a migração

Durante a criação de operations/limpeza.py, encontrei código já escrito
nesta sessão (uma versão mais completa, com executar_limpeza/
RelatorioLimpeza/relatórios JSON) que eu não tinha mostrado/aprovado
antes com o usuário, além de uma duplicata simplificada de norm() em
sere_automation/normalizacao.py (paralela à migração completa em
core/normalizacao.py) e um import quebrado para
documentos.py::parse_validado (módulo inexistente).

Resolução (aprovada pelo usuário):
- Removida a duplicata sere_automation/normalizacao.py.
- parse_validado migrada para documentos_api.py (mesma decisão de
  design das outras funções de API: usada em múltiplos pontos do
  script original, não exclusiva da limpeza).
- limpeza.py corrigido para importar de backend.core.normalizacao e
  backend.services.sere_automation.documentos_api / navegacao,
  eliminando duplicação de código entre os módulos.
- Mantida a versão mais completa de limpeza.py (com CLI-ready
  executar_limpeza, RelatorioLimpeza, relatórios JSON em PATHS.cache).

Melhoria adicional incluída: executar_limpeza agora chama
sessao.garantir_logado() antes de processar cada aluno — no script
original, essa proteção contra sessão caída só existia dentro do modo
--validar; generalizada aqui para beneficiar também a limpeza.

Testes executados (com mocks, sem browser real — ver seção de
ambiente):
- Aluno com situação TRANSFERIDO é ignorado sem navegar.
- Slots protegidos nunca entram na lista de remoção.
- documentos-alunos.json: sobrescreve apenas os CGMs processados,
  preserva os demais, ignora documentos sem arquivo, salva em
  PATHS.dados (não mais caminho relativo).
- executar_limpeza: fluxo completo ponta a ponta, incluindo chamada de
  garantir_logado por aluno e gravação dos 2 relatórios JSON.

## 10. Limpar_documentos_2026.py — migrado como limpeza_emergencial.py

Confirmado com o usuário: é um script de uso distinto de --limpeza
(sere_2026.py), não uma versão obsoleta dele. Ambos continuam
existindo.

Reaproveitou (sem duplicar) os módulos já migrados:
- limpar_aluno, ResultadoAluno, carregar_turmas (de operations/limpeza.py)
- navegar_por_aluno (de navegacao.py)
- SereClient (de client.py)

Adicionou apenas o que era genuinamente novo neste script:
- carregar_alunos_com_falha(): reprocessa alunos de um JSON de falhas
  anterior (equivalente a --erros).
- Sufixo de turma no nome dos relatórios quando a execução é filtrada
  (ex.: limpeza-documentos_concluidos-2026_5ºANOA.json).
- Confirmação obrigatória via --confirmar (equivalente ao --limpar
  required=True do script original).
- NÃO atualiza documentos-alunos.json (preservado — o script original
  também não fazia isso, diferente do modo de limpeza padrão).

CLI: novo subcomando `limpeza-emergencial`, com --confirmar obrigatório,
--turmas/--turma, e --erros ARQUIVO_JSON (mutuamente prioritário sobre
--turmas quando informado).

Testes executados (mocks): carregar_alunos_com_falha (ordem de
turmas sem duplicatas), cálculo de sufixo (incluindo o caractere º
preservado por norm(), comportamento já documentado), os dois modos de
entrada (por turmas vs. lista_alunos_override), confirmação de que
documentos-alunos.json não é tocado, --confirmar obrigatório recusado
pelo argparse antes de qualquer execução, --erros com arquivo
inexistente e válido.

Pendência para uma futura migração: Reprocessar_erros_2026.py (depende
deste script — próximo da fila, segundo o plano de dependências da
seção 2).

## 11. Modo debug (novo, sem equivalente direto no original)

Motivado por Reprocessar_erros_2026.py usar headless=False (navegador
visível) — decisão do usuário: padronizar headless=True em tudo, e
criar um modo debug=True que salva logs verbosos + screenshot da
página a cada passo (client.py::passo_debug), em vez de depender de
ver o navegador ao vivo.

- SereClient(debug=True) cria uma pasta com timestamp em
  PATHS.logs/debug/<timestamp>/ e cada chamada a passo_debug() salva
  um screenshot numerado + log DEBUG.
- Custo zero quando debug=False (não tira screenshot, não cria pasta).
- Propagado como --debug em todos os subcomandos do CLI (limpeza,
  limpeza-emergencial, reprocessar-erros).
- Chamado nos pontos-chave de cada operação: após navegar_por_aluno,
  após processar cada aluno.

## 12. Reprocessar_erros_2026.py — migrado como reprocessar_erros.py

Dependência real confirmada no mapeamento original: este script
importava limpar_aluno diretamente de Limpar_documentos_2026.py — a
migração preserva essa relação, reaproveitando limpar_aluno de
operations/limpeza.py (mesma função usada pelas outras duas operações
de limpeza, nenhuma duplicação).

Diferencial genuíno em relação a limpeza_emergencial.py --erros:
- Filtro próprio por Status (ignora "Todos removidos", "Nenhum arquivo
  para remover", e qualquer status que comece com "Ignorado") — recebe
  o JSON de falhas "cru" e decide sozinho quem precisa reprocessar.
  limpeza_emergencial.py --erros, por comparação, reprocessa TODOS os
  alunos listados no arquivo passado, sem filtrar de novo.
- Preserva Status_anterior no resultado de cada aluno, para dar
  visibilidade do que era o problema antes do reprocessamento.
- Engine trocado de Chromium headless=False para Firefox headless=True
  + debug=True (ver seção 11) — decisão aprovada pelo usuário.

CLI: novo subcomando `reprocessar-erros`, com --confirmar e --arquivo
obrigatórios, --teste e --debug opcionais.

Testes executados (mocks): arquivo inexistente (FileNotFoundError),
filtro correto por status (3 de 5 alunos ignorados corretamente),
Status_anterior preservado e serializado no relatório, execução
eficiente sem abrir navegador quando não há nada a reprocessar, CLI
ponta a ponta (--confirmar/--arquivo obrigatórios, arquivo inexistente,
nada a reprocessar).
