"""
navegacao.py — Navegação genérica dentro do portal SERE
============================================================

Funções de navegação reutilizáveis por qualquer operação (limpeza,
upload, validação etc.), extraídas de sere_2026.py.

Migração 1:1 do comportamento original — nenhuma lógica foi alterada,
apenas o local do código e a substituição de `page` solto por
`client.pagina` do SereClient.
"""

from __future__ import annotations

import logging

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


async def navegar_por_aluno(pagina: Page) -> None:
    """
    Navega pelo menu do SERE até a seção "Consulta Padrão → Por Aluno".

    (Comportamento preservado de sere_2026.py::navegar_por_aluno.)
    """
    logger.info("Navegando para: Consulta Padrão → Por Aluno")
    menu = await pagina.wait_for_selector("#divoCMenu0_0", timeout=15_000)
    await menu.evaluate(
        "el => el.dispatchEvent(new MouseEvent('mouseover', "
        "{view: window, bubbles: true, cancelable: true}))"
    )
    await pagina.wait_for_timeout(800)
    await pagina.click("//div[contains(text(),'Consulta Padr')]")
    await pagina.wait_for_timeout(500)
    await pagina.click("//div[contains(text(),'Por Aluno')]")
    await pagina.wait_for_timeout(1_500)
    logger.info("Navegação concluída.")


async def navegar_pasta_virtual(pagina: Page, cgm: str) -> bool:
    """
    Abre a pasta virtual de um aluno pelo CGM.

    Retorna True se conseguiu abrir, False em caso de timeout.

    (Comportamento preservado de sere_2026.py::navegar_pasta_virtual,
    incluindo a tentativa de renavegação em caso de #cgm não aparecer
    a tempo — evita abortar uma operação longa por uma simples demora
    de renderização.)
    """
    try:
        await pagina.wait_for_selector("#cgm", timeout=10_000)
    except PlaywrightTimeoutError:
        logger.warning("#cgm não apareceu em 10s, tentando renavegar | CGM=%s", cgm)
        try:
            await navegar_por_aluno(pagina)
            await pagina.wait_for_selector("#cgm", timeout=10_000)
        except PlaywrightTimeoutError:
            logger.error("Timeout em #cgm mesmo após renavegar | CGM=%s", cgm)
            return False

    try:
        await pagina.fill("#cgm", cgm)
        await pagina.keyboard.press("Enter")
        await pagina.wait_for_timeout(2_000)
    except Exception:
        logger.exception("Erro ao preencher/enviar #cgm | CGM=%s", cgm)
        return False

    try:
        turmas_links = await pagina.query_selector_all("a.texto_normal")
        linhas_turma = await pagina.query_selector_all(
            "table[bgcolor='#1E3B6D'] tr[bgcolor='#D6EBDF']"
        )
        if turmas_links and len(turmas_links) >= 4 and len(linhas_turma) > 1:
            txt = await turmas_links[0].inner_text()
            logger.info("Múltiplas turmas — selecionando: '%s'", txt)
            await turmas_links[0].click()
            await pagina.wait_for_timeout(2_000)
    except Exception:
        logger.warning("Erro ao verificar/selecionar turma", exc_info=True)

    try:
        botao = await pagina.wait_for_selector("input[value='Listar Arquivos']", timeout=8_000)
        await botao.click()
        await pagina.wait_for_timeout(2_000)
        await pagina.wait_for_selector("#div_pasta_virtual", timeout=15_000)
        return True
    except PlaywrightTimeoutError:
        logger.error("Timeout em 'Listar Arquivos' | CGM=%s", cgm)
        return False
