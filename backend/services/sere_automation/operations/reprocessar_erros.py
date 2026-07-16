"""
reprocessar_erros.py — Reprocessa alunos que falharam numa limpeza anterior
================================================================================

Migrado de Reprocessar_erros_2026.py.

Diferença em relação a limpeza_emergencial.py (--erros): este script
tem seu próprio filtro de "quem precisa ser reprocessado", baseado em
Status (ignora "Todos removidos", "Nenhum arquivo para remover" e
qualquer status que comece com "Ignorado"), e preserva o
Status_anterior de cada aluno no resultado — para dar visibilidade de
qual era o problema antes do reprocessamento. limpeza_emergencial.py
--erros, por outro lado, reprocessa TODOS os alunos listados no JSON
de falhas, sem filtrar por status novamente (o filtro já foi feito
por quem gerou aquele JSON).

Mudanças na migração (decisões registradas em
docs/plano_migracao_sere_automation.md):
    - Engine padronizado em Firefox headless=True (o script original
      usava Chromium com headless=False — decisão aprovada: usar o
      novo modo debug=True do SereClient para acompanhar a execução
      em vez de manter o navegador visível).
    - Reaproveita limpar_aluno de operations/limpeza.py, exatamente
      como o script original importava de Limpar_documentos_2026.py —
      nenhuma lógica de remoção duplicada.
    - Relatórios salvos em PATHS.cache, não mais em caminho relativo.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import PATHS
from backend.services.sere_automation.client import SereClient
from backend.services.sere_automation.navegacao import navegar_por_aluno
from backend.services.sere_automation.operations.limpeza import ResultadoAluno, limpar_aluno

logger = logging.getLogger(__name__)

# Status que indicam que o aluno NÃO precisa ser reprocessado.
STATUS_OK = {"Todos removidos", "Nenhum arquivo para remover"}


@dataclass
class ResultadoReprocessamento:
    """Resultado do reprocessamento de um aluno, com histórico do status anterior."""

    resultado: ResultadoAluno
    status_anterior: str

    def para_dict(self) -> dict:
        dado = self.resultado.para_dict()
        dado["Status_anterior"] = self.status_anterior
        return dado


@dataclass
class RelatorioReprocessamento:
    """Agregado de resultados de uma execução de reprocessamento de erros."""

    fonte: Path
    resolvidos: list[ResultadoReprocessamento] = field(default_factory=list)
    ainda_com_falha: list[ResultadoReprocessamento] = field(default_factory=list)
    todos: list[ResultadoReprocessamento] = field(default_factory=list)
    caminho_relatorio_resolvidos: Optional[Path] = None
    caminho_relatorio_falhas: Optional[Path] = None


def carregar_alunos_com_erro(caminho_json: Path) -> list[dict]:
    """
    Lê o JSON de falhas e retorna a lista de alunos que precisam ser
    reprocessados. Ignora alunos com status "Todos removidos",
    "Nenhum arquivo para remover", ou que começam com "Ignorado".

    (Comportamento preservado de
    Reprocessar_erros_2026.py::carregar_alunos_com_erro.)
    """
    if not caminho_json.exists():
        raise FileNotFoundError(
            f"Arquivo de falhas não encontrado: {caminho_json}\n"
            "Execute primeiro a limpeza (padrão ou emergencial)."
        )

    with open(caminho_json, encoding="utf-8") as f:
        dados = json.load(f)

    alunos = dados.get("Alunos", [])

    para_reprocessar = [
        a
        for a in alunos
        if a.get("Status", "") not in STATUS_OK and not a.get("Status", "").startswith("Ignorado")
    ]

    logger.info("JSON de falhas: %s", caminho_json)
    logger.info("  Total no arquivo : %d", len(alunos))
    logger.info("  A reprocessar    : %d", len(para_reprocessar))

    return para_reprocessar


def _salvar_relatorios(relatorio: RelatorioReprocessamento, *, modo_teste: bool, ano_base: str) -> None:
    """
    Salva os relatórios de resolvidos/ainda-com-falha em PATHS.cache.

    (No script original, esses JSONs eram salvos na pasta onde o
    comando era executado — corrigido pela mesma decisão já aplicada
    às demais operações de limpeza.)
    """
    sufixo = "_TESTE" if modo_teste else ""
    PATHS.cache.mkdir(parents=True, exist_ok=True)
    path_ok = PATHS.cache / f"limpeza-documentos_retry-resolvidos-{ano_base}{sufixo}.json"
    path_falha = PATHS.cache / f"limpeza-documentos_retry-falhas-{ano_base}{sufixo}.json"

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    with open(path_ok, "w", encoding="utf-8") as f:
        json.dump(
            {
                "Total": len(relatorio.resolvidos),
                "Data_Hora": agora,
                "Alunos": [r.para_dict() for r in relatorio.resolvidos],
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    with open(path_falha, "w", encoding="utf-8") as f:
        json.dump(
            {
                "Total": len(relatorio.ainda_com_falha),
                "Data_Hora": agora,
                "Alunos": [r.para_dict() for r in relatorio.ainda_com_falha],
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    relatorio.caminho_relatorio_resolvidos = path_ok
    relatorio.caminho_relatorio_falhas = path_falha
    logger.info("Relatórios salvos em: %s | %s", path_ok, path_falha)


async def executar_reprocessamento(
    caminho_falhas: Path,
    *,
    modo_teste: bool = False,
    ano_base: Optional[str] = None,
    debug: bool = False,
) -> RelatorioReprocessamento:
    """
    Reprocessa os alunos que falharam numa execução de limpeza
    anterior, a partir do relatório JSON de falhas.

    Equivalente a: python Reprocessar_erros_2026.py --erro [--teste] [--arquivo ...]

    debug=True substitui o antigo headless=False do script original —
    acompanhe a execução depois via logs/debug/ em vez de precisar do
    navegador visível.

    (Comportamento preservado de Reprocessar_erros_2026.py::main.)
    """
    ano_base = ano_base or str(datetime.now().year)

    alunos_com_erro = carregar_alunos_com_erro(caminho_falhas)
    relatorio = RelatorioReprocessamento(fonte=caminho_falhas)

    if not alunos_com_erro:
        logger.info("Nenhum aluno para reprocessar — encerrando.")
        return relatorio

    if modo_teste:
        alunos_com_erro = alunos_com_erro[:1]
        logger.warning("MODO TESTE — processando apenas 1 aluno")

    logger.info(
        "Reprocessamento de erros — SERE %s | Fonte: %s | Alunos: %d",
        ano_base,
        caminho_falhas,
        len(alunos_com_erro),
    )

    async with SereClient(debug=debug) as sessao:
        await navegar_por_aluno(sessao.pagina)
        await sessao.passo_debug("apos_navegar_por_aluno")

        total = len(alunos_com_erro)
        for idx, aluno in enumerate(alunos_com_erro, 1):
            nome_aluno = aluno.get("Nome", "SemNome")
            nome_turma = aluno.get("Turma", "")
            status_anterior = aluno.get("Status", "")

            logger.info(
                "[%02d/%d] Reprocessando: %s (era: %s)", idx, total, nome_aluno, status_anterior
            )

            try:
                if not await sessao.garantir_logado():
                    logger.error("Não foi possível reautenticar — abortando reprocessamento.")
                    break

                # Reaproveita a mesma função de negócio das demais
                # operações de limpeza — nenhuma lógica duplicada.
                resultado, _docs = await limpar_aluno(sessao.pagina, aluno, nome_turma)
                item = ResultadoReprocessamento(resultado=resultado, status_anterior=status_anterior)
                relatorio.todos.append(item)
                await sessao.passo_debug(
                    "apos_reprocessar_aluno", cgm=resultado.cgm, status=resultado.status
                )

                if resultado.status in STATUS_OK:
                    relatorio.resolvidos.append(item)
                    logger.info("RESOLVIDO: %s", resultado.status)
                elif not resultado.status.startswith("Ignorado"):
                    relatorio.ainda_com_falha.append(item)
                    logger.warning("AINDA COM FALHA: %s", resultado.status)

            except Exception as exc:
                logger.exception("[%d/%d] Erro inesperado: '%s'", idx, total, nome_aluno)
                resultado = ResultadoAluno(
                    cgm=str(aluno.get("CGM", "")),
                    nome=nome_aluno,
                    turma=nome_turma,
                    status=f"Erro: {exc}",
                    falhas=[{"Slot": "desconhecido", "Motivo": "Erro inesperado"}],
                )
                item = ResultadoReprocessamento(resultado=resultado, status_anterior=status_anterior)
                relatorio.todos.append(item)
                relatorio.ainda_com_falha.append(item)

            try:
                voltar = await sessao.pagina.query_selector("a[href*='AoClicarVoltar']")
                if voltar:
                    await voltar.click()
                else:
                    await sessao.pagina.go_back()
                await sessao.pagina.wait_for_timeout(1_500)
            except Exception:
                logger.warning("Erro ao voltar para a tela anterior", exc_info=True)

    _salvar_relatorios(relatorio, modo_teste=modo_teste, ano_base=ano_base)

    logger.info(
        "Reprocessamento finalizado%s — Resolvidos: %d | Ainda com falha: %d | Total: %d",
        " (TESTE)" if modo_teste else "",
        len(relatorio.resolvidos),
        len(relatorio.ainda_com_falha),
        len(relatorio.todos),
    )
    return relatorio
