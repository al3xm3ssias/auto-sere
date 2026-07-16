"""
selecao_turmas.py — Seleção de turmas (menu interativo ou CLI)
====================================================================

Utilitário compartilhado por qualquer operação que precise escolher
quais turmas processar. Extraído de sere_2026.py — no script original
essa lógica ficava duplicada dentro do bloco de argparse do main(),
mesmo sendo usada por múltiplos modos (--limpeza, --validar, --espec
etc.). Isolada aqui para reaproveitar em cada novo cli.py de operação.
"""

from __future__ import annotations


def menu_selecionar_turma(turmas: dict) -> str | None:
    """
    Exibe menu numerado de turmas e retorna o nome da turma escolhida.
    Retorna None se o usuário cancelar (opção 0).

    (Comportamento preservado de sere_2026.py::menu_selecionar_turma.)
    """
    lista = sorted(turmas.keys())
    print("\n" + "═" * 55)
    print("  SELECIONE A TURMA")
    print("═" * 55)
    for i, nome in enumerate(lista, 1):
        print(f"  {i:>3}. {nome}  ({len(turmas[nome])} alunos)")
    print("─" * 55)
    print("    0. Cancelar")
    print("═" * 55)
    while True:
        try:
            entrada = input("\nDigite o número da turma: ").strip()
            if entrada == "0":
                print("Operação cancelada.")
                return None
            n = int(entrada)
            if 1 <= n <= len(lista):
                escolhida = lista[n - 1]
                print(f"\n✅ Turma selecionada: {escolhida}")
                return escolhida
            print(f"❌ Número inválido. Digite entre 1 e {len(lista)} (ou 0 para cancelar).")
        except ValueError:
            print("❌ Entrada inválida. Digite apenas o número.")


def menu_selecionar_multiplas_turmas(turmas: dict) -> list[str]:
    """
    Exibe menu de seleção múltipla de turmas.
    Suporta: '1', '1 2 3', '2-5', 'todas'.

    (Comportamento preservado de sere_2026.py::menu_selecionar_multiplas_turmas.)
    """
    nomes = sorted(turmas.keys())
    print(f"\n{'─'*55}")
    print("  SELEÇÃO DE TURMAS  (0 = todas)")
    print(f"{'─'*55}")
    for i, nome in enumerate(nomes, 1):
        print(f"  {i:>3}. {nome:<30} ({len(turmas[nome])} alunos)")
    print(f"{'─'*55}")
    print("  Use: '1', '1 2 3', '2-5', ou 'todas'")
    print(f"{'─'*55}")

    while True:
        entrada = input("  Turmas: ").strip()
        if not entrada:
            print("  ⚠️  Nenhuma entrada.")
            continue
        if entrada.lower() in ("todas", "all", "0"):
            return nomes

        indices: list[int] = []
        valido = True
        for parte in entrada.split():
            if "-" in parte:
                try:
                    ini, fim = map(int, parte.split("-", 1))
                    if not (1 <= ini <= len(nomes) and 1 <= fim <= len(nomes)):
                        raise ValueError
                    indices.extend(range(ini, fim + 1))
                except ValueError:
                    print(f"  ⚠️  Intervalo inválido: '{parte}'")
                    valido = False
                    break
            else:
                try:
                    n = int(parte)
                    if not (1 <= n <= len(nomes)):
                        raise ValueError
                    indices.append(n)
                except ValueError:
                    print(f"  ⚠️  Número inválido: '{parte}'")
                    valido = False
                    break
        if not valido:
            continue

        vistos: set[int] = set()
        unicos = [i for i in indices if not (i in vistos or vistos.add(i))]
        selecionadas = [nomes[i - 1] for i in unicos]

        total = sum(len(turmas[t]) for t in selecionadas)
        print(f"\n  ✅ {len(selecionadas)} turma(s) | {total} aluno(s)")
        for t in selecionadas:
            print(f"     • {t} ({len(turmas[t])} alunos)")
        print()
        return selecionadas


def resolver_turmas_selecionadas(
    turmas: dict,
    *,
    nomes_informados: list[str] | None,
    interativo_unico: bool,
    norm,
) -> list[str] | None:
    """
    Resolve a lista final de turmas a partir dos argumentos de linha de
    comando, seguindo exatamente a precedência do script original:

        1. --turmas SEM valores  → menu de seleção múltipla interativo
        2. --turmas COM valores  → usa os nomes informados (normalizados,
                                    tolerante a acento/caixa), avisa e
                                    ignora os que não existem
        3. --turma (sem 's')     → menu de seleção única interativo
        4. nenhum dos anteriores → todas as turmas, em ordem alfabética

    Retorna None se o usuário cancelou um menu interativo (--turma).
    Retorna lista vazia levantará ValueError se --turmas foi usado mas
    nenhum nome informado é válido (mesmo comportamento do script
    original, que fazia sys.exit(1) nesse caso — aqui delega a decisão
    de encerrar o processo para quem chama, em vez de sair sozinho).

    O parâmetro `norm` recebe a função de normalização de texto
    (backend.core.normalizacao.norm), injetada explicitamente para
    manter este módulo desacoplado de qual estratégia de normalização
    é usada por quem o chama.

    Nota sobre norm(): remove acentos (categoria Unicode "Mn"), mas o
    símbolo "º" (ordinal masculino) NÃO é removido — não é um acento
    combinante, é um caractere próprio. Ou seja, "5º Ano A" e "5 Ano A"
    são tratados como nomes DIFERENTES por --turmas. Isso é um
    comportamento pré-existente da função original (sere_normalizacao.py),
    preservado aqui sem alteração — documentado por ter sido descoberto
    durante os testes desta migração.
    """
    if nomes_informados is not None:
        if len(nomes_informados) == 0:
            return menu_selecionar_multiplas_turmas(turmas)

        nomes_norm = {norm(k): k for k in turmas.keys()}
        selecionadas: list[str] = []
        for entrada in nomes_informados:
            chave = norm(entrada)
            if chave in nomes_norm:
                selecionadas.append(nomes_norm[chave])
            else:
                print(f"⚠️  Turma não encontrada: '{entrada}'")
        if not selecionadas:
            raise ValueError("Nenhuma turma válida informada em --turmas.")
        return selecionadas

    if interativo_unico:
        escolhida = menu_selecionar_turma(turmas)
        if not escolhida:
            return None
        return [escolhida]

    return sorted(turmas.keys())
