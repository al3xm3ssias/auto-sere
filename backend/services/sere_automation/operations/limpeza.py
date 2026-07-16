"""
limpeza.py — Operação de limpeza de documentos dos alunos no SERE
======================================================================

Migrado de sere_2026.py::modo_limpeza (e funções auxiliares
navegar_por_aluno, navegar_pasta_virtual, buscar_documentos_api,
excluir_arquivo_api, remover_slot, limpar_aluno).

Comportamento preservado do script original:
    - Remove todos os documentos anexados de um aluno, EXCETO os slots
      protegidos (parecer descritivo, requerimento de matrícula,
      declaração de matrícula).
    - Alunos com situação "TRANSFERIDO" são ignorados.
    - Cada slot pode ter várias versões empilhadas no SERE — o sistema
      tenta remover até MAX_TENTATIVAS_SLOT vezes ou até o slot ficar
      vazio.
    - Ao final, documentos-alunos.json é atualizado com o estado
      pós-limpeza, e dois relatórios são salvos (concluídos / falhas).

O que mudou na migração (decisões registradas em
docs/plano_migracao_sere_automation.md):
    - Login/sessão agora vêm de SereClient (sere_automation/client.py),
      não mais reimplementados aqui.
    - Navegação genérica (navegar_por_aluno, navegar_pasta_virtual) e
      acesso à API de documentos (buscar/excluir/remover_slot,
      parse_validado) vêm de navegacao.py e documentos_api.py — não
      duplicados aqui, já que são usados por mais de uma operação no
      script original.
    - norm() vem de backend.core.normalizacao (migração 1:1 de
      sere_normalizacao.py), não de uma cópia local simplificada.
    - Caminhos agora vêm de PATHS (backend/core/config.py), não mais
      hardcoded por sistema operacional.
    - documentos-alunos.json passa a salvar sempre em PATHS.dados
      (era um caminho relativo no script original — decisão aprovada
      no plano de migração).
    - Engine do navegador padronizado em Firefox (corrige o bug do
      script original, que chamava o inválido p.chrome nesse modo).
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
from backend.services.sere_automation.documentos_api import (
    buscar_documentos_api,
    parse_validado,
    remover_slot,
)
from backend.services.sere_automation.navegacao import (
    navegar_pasta_virtual,
    navegar_por_aluno,
)

logger = logging.getLogger(__name__)

# Slots que nunca são removidos pela limpeza.
# (Preservado de sere_2026.py::SLOTS_PROTEGIDOS_NORM)
SLOTS_PROTEGIDOS_NORM = {
    "PARECER DESCRITIVO",
    "REQUERIMENTO DE MATRICULA",
    "DECLARACAO DE MATRICULA",
}


@dataclass
class ResultadoAluno:
    """Resultado da limpeza de um único aluno."""

    cgm: str
    nome: str
    turma: str
    status: str = "Não processado"
    removidos: list[str] = field(default_factory=list)
    protegidos: list[str] = field(default_factory=list)
    falhas: list[dict] = field(default_factory=list)

    def para_dict(self) -> dict:
        """Serializa no mesmo formato usado pelos relatórios JSON originais."""
        return {
            "CGM": self.cgm,
            "Nome": self.nome,
            "Turma": self.turma,
            "Status": self.status,
            "Removidos": self.removidos,
            "Protegidos": self.protegidos,
            "Falhas": self.falhas,
        }


@dataclass
class RelatorioLimpeza:
    """Agregado de resultados de uma execução completa da limpeza."""

    turmas_selecionadas: list[str]
    concluidos: list[ResultadoAluno] = field(default_factory=list)
    com_falha: list[ResultadoAluno] = field(default_factory=list)
    todos: list[ResultadoAluno] = field(default_factory=list)


def carregar_turmas(caminho: Optional[Path] = None) -> dict[str, list[dict]]:
    """
    Lê turmas.json e retorna { nome_turma: [lista de alunos] }.

    (Comportamento preservado de sere_2026.py::carregar_turmas; o
    caminho padrão agora vem de PATHS em vez de uma constante local
    calculada por sistema operacional.)
    """
    caminho = caminho or (PATHS.dados / "turmas.json")
    logger.info("Carregando turmas de: %s", caminho)
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    total_alunos = sum(len(v) for v in dados.values())
    logger.info("Turmas: %d | Alunos: %d", len(dados), total_alunos)
    return dados


async def limpar_aluno(
    pagina, aluno: dict, nome_turma: str
) -> tuple[ResultadoAluno, list[dict]]:
    """
    Limpa todos os documentos de um aluno (exceto slots protegidos).

    Retorna (resultado, documentos_restantes_apos_limpeza).

    (Comportamento preservado de sere_2026.py::limpar_aluno.)
    """
    cgm = str(aluno["CGM"])
    nome = aluno.get("Nome", "SemNome")
    situacao = aluno.get("Situação", "")

    logger.info("Limpando: '%s' | CGM=%s | Turma='%s'", nome, cgm, nome_turma)

    resultado = ResultadoAluno(cgm=cgm, nome=nome, turma=nome_turma)

    if "TRANSFER" in norm(situacao):
        resultado.status = f"Ignorado (situação: {situacao})"
        logger.info("Ignorado: situação '%s'", situacao)
        return resultado, []

    ok = await navegar_pasta_virtual(pagina, cgm)
    if not ok:
        resultado.status = "Falha ao abrir pasta virtual"
        return resultado, []

    documentos = await buscar_documentos_api(pagina, cgm)
    if not documentos:
        resultado.status = "API não retornou documentos"
        return resultado, []

    para_remover = [
        doc
        for doc in documentos
        if doc.get("nomearquivo", "").strip()
        and norm(doc.get("tipodocumento", "")) not in SLOTS_PROTEGIDOS_NORM
    ]
    for doc in documentos:
        tipo_norm = norm(doc.get("tipodocumento", ""))
        if tipo_norm in SLOTS_PROTEGIDOS_NORM and doc.get("nomearquivo", "").strip():
            resultado.protegidos.append(doc["tipodocumento"])

    logger.info(
        "Slots: %d total | %d com arquivo | %d a remover",
        len(documentos),
        sum(1 for d in documentos if d.get("nomearquivo", "").strip()),
        len(para_remover),
    )

    if not para_remover:
        resultado.status = "Nenhum arquivo para remover"
        await pagina.keyboard.press("Escape")
        await pagina.wait_for_timeout(500)
        docs_restantes = await buscar_documentos_api(pagina, cgm)
        return resultado, docs_restantes

    todos_ok = True
    for doc in para_remover:
        slot = doc["tipodocumento"]
        logger.info("Removendo slot: %s", slot)
        sucesso, msg = await remover_slot(pagina, cgm, doc, norm)

        if sucesso:
            logger.info("%s: %s", slot, msg)
            resultado.removidos.append(slot)
        else:
            logger.error("%s: %s", slot, msg)
            resultado.falhas.append({"Slot": slot, "Motivo": msg})
            todos_ok = False

    resultado.status = "Todos removidos" if todos_ok else "Parcial — algumas remoções falharam"

    await pagina.keyboard.press("Escape")
    await pagina.wait_for_timeout(500)

    docs_restantes = await buscar_documentos_api(pagina, cgm)
    return resultado, docs_restantes


def _atualizar_documentos_alunos(
    docs_restantes_por_cgm: dict[str, list[dict]],
    caminho: Optional[Path] = None,
) -> None:
    """
    Atualiza (ou cria) documentos-alunos.json com o estado pós-limpeza.
    Sobrescreve apenas os registros dos CGMs processados nesta execução.

    (Comportamento preservado de
    sere_2026.py::atualizar_documentos_alunos_via_api. Decisão aprovada:
    o caminho padrão agora é PATHS.dados / "documentos-alunos.json" —
    no script original era um caminho relativo (Path("documentos-alunos.json")),
    que salvava em lugares diferentes dependendo de onde o comando era
    executado.)
    """
    caminho = caminho or (PATHS.dados / "documentos-alunos.json")

    existentes: list[dict] = []
    if caminho.exists():
        try:
            with open(caminho, encoding="utf-8") as f:
                existentes = json.load(f)
        except (json.JSONDecodeError, OSError):
            existentes = []

    cgms_atualizados = set(docs_restantes_por_cgm.keys())
    lista_final = [a for a in existentes if str(a.get("CGM", "")) not in cgms_atualizados]

    for cgm, docs_api in docs_restantes_por_cgm.items():
        detalhes = []
        for doc in docs_api:
            nome_arquivo = doc.get("nomearquivo", "").strip()
            if not nome_arquivo:
                continue
            detalhes.append(
                {
                    "tipo": doc.get("tipodocumento", "").strip(),
                    "arquivo": nome_arquivo,
                    "data": doc.get("datainclusao", "").strip(),
                    "validado": parse_validado(doc.get("tag")),
                }
            )
        lista_final.append({"CGM": cgm, "Detalhes": detalhes, "Total": len(detalhes)})

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, ensure_ascii=False, indent=2)

    logger.info("documentos-alunos.json atualizado — %d aluno(s) no arquivo", len(lista_final))


def _salvar_relatorios(relatorio: RelatorioLimpeza, *, ano_base: str, modo_teste: bool) -> None:
    """
    Salva os relatórios de concluídos/falhas em PATHS.cache.

    (No script original, esses JSONs eram salvos na pasta onde o
    comando era executado — mesma inconsistência do
    documentos-alunos.json, corrigida aqui pela mesma decisão.)
    """
    sufixo = "_TESTE" if modo_teste else ""
    path_ok = PATHS.cache / f"limpeza-documentos_concluidos-{ano_base}{sufixo}.json"
    path_falha = PATHS.cache / f"limpeza-documentos_falhas-{ano_base}{sufixo}.json"
    PATHS.cache.mkdir(parents=True, exist_ok=True)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    with open(path_ok, "w", encoding="utf-8") as f:
        json.dump(
            {
                "Total": len(relatorio.concluidos),
                "Turmas": relatorio.turmas_selecionadas,
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
                "Turmas": relatorio.turmas_selecionadas,
                "Data_Hora": agora,
                "Alunos": [r.para_dict() for r in relatorio.com_falha],
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    logger.info("Relatórios salvos em: %s | %s", path_ok, path_falha)


async def executar_limpeza(
    turmas_selecionadas: list[str],
    *,
    modo_teste: bool = False,
    ano_base: Optional[str] = None,
    debug: bool = False,
) -> RelatorioLimpeza:
    """
    Remove todos os documentos (exceto protegidos) dos alunos das turmas
    selecionadas.

    Equivalente a: python sere_2026.py --limpeza [--teste] [--turmas ...]

    debug=True ativa logs verbosos e screenshots por passo no SereClient
    (ver client.py::passo_debug) — útil para acompanhar o que o robô fez
    depois da execução, sem precisar de navegador visível.

    (Comportamento preservado de sere_2026.py::modo_limpeza.)
    """
    ano_base = ano_base or str(datetime.now().year)
    turmas = carregar_turmas()

    lista_alunos: list[tuple[str, dict]] = [
        (nome_turma, aluno)
        for nome_turma in turmas_selecionadas
        for aluno in turmas[nome_turma]
    ]
    if modo_teste:
        lista_alunos = lista_alunos[:1]
        logger.warning("MODO TESTE — processando apenas 1 aluno")

    logger.info(
        "Limpeza de documentos — SERE %s | Turmas: %d | Alunos: %d",
        ano_base,
        len(turmas_selecionadas),
        len(lista_alunos),
    )

    relatorio = RelatorioLimpeza(turmas_selecionadas=turmas_selecionadas)
    docs_restantes_por_cgm: dict[str, list[dict]] = {}

    async with SereClient(debug=debug) as sessao:
        await navegar_por_aluno(sessao.pagina)
        await sessao.passo_debug("apos_navegar_por_aluno")

        total = len(lista_alunos)
        for idx, (nome_turma, aluno) in enumerate(lista_alunos, 1):
            cgm_aluno = str(aluno.get("CGM", ""))
            nome_aluno = aluno.get("Nome", "SemNome")
            logger.info("[%02d/%d] Processando: %s (CGM=%s)", idx, total, nome_aluno, cgm_aluno)

            try:
                # Sessão pode cair no meio de uma lista longa — garante
                # relogin automático antes de continuar (comportamento
                # generalizado a partir de sere_2026.py::garantir_logado,
                # que no original só existia dentro do modo --validar).
                if not await sessao.garantir_logado():
                    logger.error("Não foi possível reautenticar — abortando limpeza.")
                    break

                resultado, docs_api = await limpar_aluno(sessao.pagina, aluno, nome_turma)
                relatorio.todos.append(resultado)
                docs_restantes_por_cgm[cgm_aluno] = docs_api
                await sessao.passo_debug(f"apos_processar_aluno", cgm=cgm_aluno, status=resultado.status)

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

    logger.info("Atualizando documentos-alunos.json com estado pós-limpeza…")
    _atualizar_documentos_alunos(docs_restantes_por_cgm)

    _salvar_relatorios(relatorio, ano_base=ano_base, modo_teste=modo_teste)

    logger.info(
        "Limpeza finalizada%s — Concluídos: %d | Com falha: %d | Total: %d",
        " (TESTE)" if modo_teste else "",
        len(relatorio.concluidos),
        len(relatorio.com_falha),
        len(relatorio.todos),
    )
    return relatorio
