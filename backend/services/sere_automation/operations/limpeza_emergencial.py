"""
limpeza_emergencial.py — Limpeza pontual com confirmação e modo --erros
============================================================================

Migrado de Limpar_documentos_2026.py.

Diferença de propósito em relação a operations/limpeza.py (confirmado
com o usuário: são usados para coisas diferentes no dia a dia, ambos
continuam existindo):

    - operations/limpeza.py        → limpeza padrão do dia a dia,
                                      SEMPRE atualiza documentos-alunos.json.
    - limpeza_emergencial.py (este) → limpeza pontual/emergencial:
          • exige confirmação explícita antes de rodar (equivalente ao
            antigo --limpar obrigatório);
          • pode reprocessar SÓ os alunos que falharam numa execução
            anterior, a partir do JSON de falhas (--erros);
          • nomeia os relatórios de saída com sufixo das turmas
            filtradas, quando aplicável;
          • NÃO atualiza documentos-alunos.json (o script original
            também não fazia isso).

A lógica de remoção em si (limpar_aluno, remover_slot,
navegar_pasta_virtual, buscar_documentos_api) é EXATAMENTE a mesma do
modo de limpeza padrão — por isso é reaproveitada diretamente de
operations/limpeza.py e sere_automation/{navegacao,documentos_api}.py,
em vez de duplicada aqui (regra do CLAUDE.md: nunca duplicar código).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import PATHS
from backend.core.normalizacao import norm
from backend.services.sere_automation.client import SereClient
from backend.services.sere_automation.navegacao import navegar_por_aluno
from backend.services.sere_automation.operations.limpeza import (
    ResultadoAluno,
    carregar_turmas,
    limpar_aluno,
)

logger = logging.getLogger(__name__)


@dataclass
class RelatorioLimpezaEmergencial:
    """Agregado de resultados de uma execução de limpeza emergencial."""

    turmas_envolvidas: list[str]
    concluidos: list[ResultadoAluno] = field(default_factory=list)
    com_falha: list[ResultadoAluno] = field(default_factory=list)
    todos: list[ResultadoAluno] = field(default_factory=list)
    caminho_relatorio_ok: Optional[Path] = None
    caminho_relatorio_falha: Optional[Path] = None


def carregar_alunos_com_falha(caminho_json: Path) -> tuple[list[str], list[tuple[str, dict]]]:
    """
    Lê um JSON de falhas gerado por uma execução anterior e retorna
    (turmas_envolvidas, lista de (turma, aluno)) para reprocessamento.

    (Comportamento preservado de
    Limpar_documentos_2026.py::carregar_alunos_com_falha.)
    """
    with open(caminho_json, encoding="utf-8") as f:
        dados = json.load(f)

    lista: list[tuple[str, dict]] = []
    for aluno in dados.get("Alunos", []):
        turma = aluno.get("Turma", "Desconhecida")
        lista.append((turma, aluno))

    turmas = list(dict.fromkeys(t for t, _ in lista))  # ordem de inserção, sem duplicatas

    logger.info("JSON de falhas: %s | Alunos a reprocessar: %d", caminho_json, len(lista))
    for t in turmas:
        qtd = sum(1 for turma, _ in lista if turma == t)
        logger.info("  • %s (%d aluno(s))", t, qtd)

    return turmas, lista


def _sufixo_turmas(turmas_selecionadas: list[str], total_turmas_existentes: int) -> str:
    """
    Gera o sufixo de nome de arquivo quando a execução está filtrada
    para turmas específicas (em vez de rodar todas).

    (Comportamento preservado de Limpar_documentos_2026.py::main —
    bloco de cálculo de sufixo_turma.)
    """
    filtrando = len(turmas_selecionadas) < total_turmas_existentes
    if not filtrando:
        return ""
    return "_" + "_".join(norm(t).replace(" ", "") for t in turmas_selecionadas)


def _salvar_relatorios(
    relatorio: RelatorioLimpezaEmergencial,
    *,
    sufixo_turma: str,
    modo_teste: bool,
    ano_base: str,
) -> None:
    """
    Salva os relatórios de concluídos/falhas em PATHS.cache, com o
    sufixo de turma quando aplicável — preservando o nome de arquivo
    que Reprocessar_erros_2026.py espera encontrar por padrão.
    """
    sufixo_teste = "_TESTE" if modo_teste else ""
    sufixo_final = f"{sufixo_turma}{sufixo_teste}"

    PATHS.cache.mkdir(parents=True, exist_ok=True)
    path_ok = PATHS.cache / f"limpeza-documentos_concluidos-{ano_base}{sufixo_final}.json"
    path_falha = PATHS.cache / f"limpeza-documentos_falhas-{ano_base}{sufixo_final}.json"

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    with open(path_ok, "w", encoding="utf-8") as f:
        json.dump(
            {
                "Total": len(relatorio.concluidos),
                "Turmas": relatorio.turmas_envolvidas,
                "Data_Hora": agora,
                "Alunos": [r.para_dict() for r in relatorio.concluidos],
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    with open(path_falha, "w", encoding="utf-8") as f:
        json.dump(
            {
                "Total": len(relatorio.com_falha),
                "Turmas": relatorio.turmas_envolvidas,
                "Data_Hora": agora,
                "Alunos": [r.para_dict() for r in relatorio.com_falha],
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    relatorio.caminho_relatorio_ok = path_ok
    relatorio.caminho_relatorio_falha = path_falha
    logger.info("Relatórios salvos em: %s | %s", path_ok, path_falha)


async def executar_limpeza_emergencial(
    *,
    turmas_selecionadas: Optional[list[str]] = None,
    lista_alunos_override: Optional[list[tuple[str, dict]]] = None,
    modo_teste: bool = False,
    ano_base: Optional[str] = None,
    debug: bool = False,
) -> RelatorioLimpezaEmergencial:
    """
    Remove documentos (exceto protegidos) dos alunos selecionados.

    Dois modos de uso:
      1. turmas_selecionadas informado  → processa alunos dessas turmas
         (lidas de turmas.json).
      2. lista_alunos_override informado → reprocessa exatamente essa
         lista de (turma, aluno), tipicamente vinda de
         carregar_alunos_com_falha() (equivalente a --erros).

    Diferente de operations.limpeza.executar_limpeza, esta função NÃO
    atualiza documentos-alunos.json (preservando o comportamento do
    script original) e nomeia os relatórios com sufixo de turma quando
    a execução está filtrada.

    (Comportamento preservado de Limpar_documentos_2026.py::main.)
    """
    ano_base = ano_base or str(datetime.now().year)

    if lista_alunos_override is not None:
        lista_alunos = lista_alunos_override
        turmas_envolvidas = list(dict.fromkeys(t for t, _ in lista_alunos))
        sufixo_turma = ""  # script original também não aplicava sufixo no modo --erros
    else:
        assert turmas_selecionadas is not None, (
            "Informe turmas_selecionadas ou lista_alunos_override."
        )
        todas_turmas = carregar_turmas()
        lista_alunos = [
            (nome_turma, aluno)
            for nome_turma in turmas_selecionadas
            for aluno in todas_turmas[nome_turma]
        ]
        turmas_envolvidas = turmas_selecionadas
        sufixo_turma = _sufixo_turmas(turmas_selecionadas, len(todas_turmas))

    if modo_teste:
        lista_alunos = lista_alunos[:1]
        logger.warning("MODO TESTE — processando apenas 1 aluno")

    logger.info(
        "Limpeza emergencial — SERE %s | Turmas envolvidas: %d | Alunos: %d",
        ano_base,
        len(turmas_envolvidas),
        len(lista_alunos),
    )

    relatorio = RelatorioLimpezaEmergencial(turmas_envolvidas=turmas_envolvidas)

    async with SereClient(debug=debug) as sessao:
        await navegar_por_aluno(sessao.pagina)
        await sessao.passo_debug("apos_navegar_por_aluno")

        total = len(lista_alunos)
        for idx, (nome_turma, aluno) in enumerate(lista_alunos, 1):
            nome_aluno = aluno.get("Nome", "SemNome")
            cgm_aluno = str(aluno.get("CGM", ""))
            logger.info("[%02d/%d] Processando: %s (CGM=%s)", idx, total, nome_aluno, cgm_aluno)

            try:
                if not await sessao.garantir_logado():
                    logger.error("Não foi possível reautenticar — abortando.")
                    break

                # Reaproveita a mesma função de negócio do modo de
                # limpeza padrão — nenhuma lógica de remoção duplicada.
                resultado, _docs_restantes = await limpar_aluno(sessao.pagina, aluno, nome_turma)
                relatorio.todos.append(resultado)
                await sessao.passo_debug("apos_processar_aluno", cgm=cgm_aluno, status=resultado.status)

                if resultado.status in ("Todos removidos", "Nenhum arquivo para remover"):
                    relatorio.concluidos.append(resultado)
                elif "Ignorado" not in resultado.status:
                    relatorio.com_falha.append(resultado)

            except Exception as exc:
                logger.exception("[%d/%d] Erro inesperado: '%s'", idx, total, nome_aluno)
                resultado = ResultadoAluno(
                    cgm=cgm_aluno,
                    nome=nome_aluno,
                    turma=nome_turma,
                    status=f"Erro: {exc}",
                    falhas=[{"Slot": "desconhecido", "Motivo": "Erro inesperado"}],
                )
                relatorio.todos.append(resultado)
                relatorio.com_falha.append(resultado)

            try:
                voltar = await sessao.pagina.query_selector("a[href*='AoClicarVoltar']")
                if voltar:
                    await voltar.click()
                else:
                    await sessao.pagina.go_back()
                await sessao.pagina.wait_for_timeout(1_500)
            except Exception:
                logger.warning("Erro ao voltar para a tela anterior", exc_info=True)

    _salvar_relatorios(relatorio, sufixo_turma=sufixo_turma, modo_teste=modo_teste, ano_base=ano_base)

    logger.info(
        "Limpeza emergencial finalizada%s — Concluídos: %d | Com falha: %d | Total: %d",
        " (TESTE)" if modo_teste else "",
        len(relatorio.concluidos),
        len(relatorio.com_falha),
        len(relatorio.todos),
    )
    return relatorio
