"""
cli.py — Ponto de entrada de linha de comando das operações SERE
=====================================================================

Equivalente ao antigo `python sere_2026.py --limpeza [opções]` e
`python Limpar_documentos_2026.py --limpar [opções]`.

Migrados por enquanto: limpeza (padrão) e limpeza-emergencial (ver
docs/plano_migracao_sere_automation.md). Os demais modos do script
original ainda não foram migrados e não estão disponíveis aqui.

Uso — limpeza padrão (atualiza documentos-alunos.json):
    python -m backend.services.sere_automation.cli limpeza
    python -m backend.services.sere_automation.cli limpeza --teste
    python -m backend.services.sere_automation.cli limpeza --turma
    python -m backend.services.sere_automation.cli limpeza --turmas "5º Ano A" "6º Ano B"
    python -m backend.services.sere_automation.cli limpeza --turmas
        (sem valores após --turmas = menu de seleção múltipla interativo)

Uso — limpeza emergencial (NÃO atualiza documentos-alunos.json,
exige confirmação explícita, suporta reprocessar falhas):
    python -m backend.services.sere_automation.cli limpeza-emergencial --confirmar
    python -m backend.services.sere_automation.cli limpeza-emergencial --confirmar --turmas "5º Ano A"
    python -m backend.services.sere_automation.cli limpeza-emergencial --confirmar --erros /caminho/limpeza-documentos_falhas-2026.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from backend.core.normalizacao import norm
from backend.services.sere_automation.client import ErroDeLogin
from backend.services.sere_automation.operations.limpeza import (
    carregar_turmas,
    executar_limpeza,
)
from backend.services.sere_automation.operations.limpeza_emergencial import (
    carregar_alunos_com_falha,
    executar_limpeza_emergencial,
)
from backend.services.sere_automation.operations.reprocessar_erros import (
    executar_reprocessamento,
)
from backend.services.sere_automation.selecao_turmas import resolver_turmas_selecionadas

logger = logging.getLogger(__name__)


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sere-automation",
        description="Auto-SERE — operações automatizadas no portal SERE.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="operacao", required=True)

    p_limpeza = subparsers.add_parser(
        "limpeza",
        help="Limpeza padrão: remove documentos e atualiza documentos-alunos.json.",
    )
    p_limpeza.add_argument(
        "--teste", action="store_true", help="Processa apenas 1 aluno, para validar antes de rodar tudo."
    )
    p_limpeza.add_argument(
        "--turma", action="store_true", help="Seleção interativa de uma única turma."
    )
    p_limpeza.add_argument(
        "--turmas",
        nargs="*",
        metavar="TURMA",
        default=None,
        help="Uma ou mais turmas por nome (sem valor = menu de seleção múltipla interativo). "
        "Se omitido, processa todas as turmas.",
    )
    p_limpeza.add_argument(
        "--debug",
        action="store_true",
        help="Salva log verboso e screenshots de cada passo em logs/debug/ "
        "(útil para acompanhar a execução sem abrir o navegador visível).",
    )

    p_emerg = subparsers.add_parser(
        "limpeza-emergencial",
        help="Limpeza pontual: exige --confirmar, suporta reprocessar falhas via --erros, "
        "NÃO atualiza documentos-alunos.json.",
    )
    p_emerg.add_argument(
        "--confirmar",
        action="store_true",
        required=True,
        help="Obrigatório — confirma a execução da limpeza emergencial.",
    )
    p_emerg.add_argument(
        "--teste", action="store_true", help="Processa apenas 1 aluno, para validar antes de rodar tudo."
    )
    p_emerg.add_argument(
        "--turma", action="store_true", help="Seleção interativa de uma única turma."
    )
    p_emerg.add_argument(
        "--turmas",
        nargs="*",
        metavar="TURMA",
        default=None,
        help="Uma ou mais turmas por nome (sem valor = menu de seleção múltipla interativo). "
        "Ignorado se --erros for usado.",
    )
    p_emerg.add_argument(
        "--erros",
        metavar="ARQUIVO_JSON",
        default=None,
        help="Reprocessa apenas os alunos com falha de um relatório JSON anterior "
        "(ex.: limpeza-documentos_falhas-2026.json). Quando usado, ignora --turmas/--turma.",
    )
    p_emerg.add_argument(
        "--debug",
        action="store_true",
        help="Salva log verboso e screenshots de cada passo em logs/debug/ "
        "(útil para acompanhar a execução sem abrir o navegador visível).",
    )

    p_reproc = subparsers.add_parser(
        "reprocessar-erros",
        help="Reprocessa apenas os alunos com falha de um relatório JSON anterior, "
        "preservando o status anterior de cada um no resultado.",
    )
    p_reproc.add_argument(
        "--confirmar",
        action="store_true",
        required=True,
        help="Obrigatório — confirma que quer reprocessar os erros.",
    )
    p_reproc.add_argument(
        "--arquivo",
        type=Path,
        required=True,
        metavar="ARQUIVO_JSON",
        help="Caminho do relatório JSON de falhas a reprocessar.",
    )
    p_reproc.add_argument(
        "--teste", action="store_true", help="Processa apenas 1 aluno, para validar antes de rodar tudo."
    )
    p_reproc.add_argument(
        "--debug",
        action="store_true",
        help="Salva log verboso e screenshots de cada passo em logs/debug/.",
    )

    return parser


def _imprimir_resumo(titulo: str, relatorio, modo_teste: bool) -> None:
    print()
    print("=" * 65)
    print(f"  ✅ {titulo}{' (TESTE)' if modo_teste else ''}")
    print(f"     Concluídos : {len(relatorio.concluidos)}")
    print(f"     Com falha  : {len(relatorio.com_falha)}")
    print(f"     Total      : {len(relatorio.todos)}")
    print("=" * 65)


async def _rodar_limpeza(args: argparse.Namespace) -> int:
    turmas = carregar_turmas()

    try:
        turmas_selecionadas = resolver_turmas_selecionadas(
            turmas,
            nomes_informados=args.turmas,
            interativo_unico=args.turma,
            norm=norm,
        )
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1

    if turmas_selecionadas is None:
        # Usuário cancelou o menu interativo (--turma, opção 0).
        return 0

    try:
        relatorio = await executar_limpeza(turmas_selecionadas, modo_teste=args.teste, debug=args.debug)
    except ErroDeLogin as exc:
        print(f"❌ Falha de login: {exc}")
        return 1

    _imprimir_resumo("LIMPEZA FINALIZADA", relatorio, args.teste)
    return 0 if not relatorio.com_falha else 2


async def _rodar_limpeza_emergencial(args: argparse.Namespace) -> int:
    if args.erros:
        caminho_json = Path(args.erros)
        if not caminho_json.exists():
            print(f"❌ Arquivo não encontrado: {caminho_json}")
            return 1
        _turmas_envolvidas, lista_alunos = carregar_alunos_com_falha(caminho_json)
        kwargs = {"lista_alunos_override": lista_alunos}
    else:
        turmas = carregar_turmas()
        try:
            turmas_selecionadas = resolver_turmas_selecionadas(
                turmas,
                nomes_informados=args.turmas,
                interativo_unico=args.turma,
                norm=norm,
            )
        except ValueError as exc:
            print(f"❌ {exc}")
            return 1

        if turmas_selecionadas is None:
            return 0

        kwargs = {"turmas_selecionadas": turmas_selecionadas}

    try:
        relatorio = await executar_limpeza_emergencial(modo_teste=args.teste, debug=args.debug, **kwargs)
    except ErroDeLogin as exc:
        print(f"❌ Falha de login: {exc}")
        return 1

    _imprimir_resumo("LIMPEZA EMERGENCIAL FINALIZADA", relatorio, args.teste)
    if relatorio.caminho_relatorio_ok:
        print(f"  📄 OK     : {relatorio.caminho_relatorio_ok}")
        print(f"  ⚠️  Falhas : {relatorio.caminho_relatorio_falha}")
    return 0 if not relatorio.com_falha else 2


async def _rodar_reprocessar_erros(args: argparse.Namespace) -> int:
    if not args.arquivo.exists():
        print(f"❌ Arquivo não encontrado: {args.arquivo}")
        return 1

    try:
        relatorio = await executar_reprocessamento(
            args.arquivo, modo_teste=args.teste, debug=args.debug
        )
    except ErroDeLogin as exc:
        print(f"❌ Falha de login: {exc}")
        return 1
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return 1

    if not relatorio.todos:
        print("\n✅ Nenhum aluno com erro encontrado no arquivo. Nada a reprocessar.")
        return 0

    print()
    print("=" * 65)
    print(f"  ✅ REPROCESSAMENTO FINALIZADO{' (TESTE)' if args.teste else ''}")
    print(f"     Resolvidos      : {len(relatorio.resolvidos)}")
    print(f"     Ainda com falha : {len(relatorio.ainda_com_falha)}")
    print(f"     Total           : {len(relatorio.todos)}")
    print("=" * 65)
    if relatorio.caminho_relatorio_resolvidos:
        print(f"  📄 Resolvidos : {relatorio.caminho_relatorio_resolvidos}")
        print(f"  ⚠️  Falhas     : {relatorio.caminho_relatorio_falhas}")

    return 0 if not relatorio.ainda_com_falha else 2


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    parser = _construir_parser()
    args = parser.parse_args(argv)

    if args.operacao == "limpeza":
        return asyncio.run(_rodar_limpeza(args))
    if args.operacao == "limpeza-emergencial":
        return asyncio.run(_rodar_limpeza_emergencial(args))
    if args.operacao == "reprocessar-erros":
        return asyncio.run(_rodar_reprocessar_erros(args))

    parser.error(f"Operação desconhecida: {args.operacao}")
    return 1  # pragma: no cover — argparse.error já encerra o processo


if __name__ == "__main__":
    sys.exit(main())
