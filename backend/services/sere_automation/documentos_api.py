"""
documentos_api.py — Acesso à API do SERE para documentos da pasta virtual
=============================================================================

Encapsula as chamadas à API interna do SERE (listarArquivos, mudarStatus)
usadas para consultar e excluir documentos da pasta virtual de um aluno.

Extraído de sere_2026.py. Migração 1:1 do comportamento original.
"""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)

URL_SERE = "https://www.sere.pr.gov.br/sere"
URL_API_LISTAR = f"{URL_SERE}/gerenciarPastaVirtual.do?action=listarArquivos&cgmAluno="
URL_MUDAR_STATUS = f"{URL_SERE}/gerenciarPastaVirtual.do?action=mudarStatus"

# Máximo de tentativas de exclusão por slot (para versões empilhadas no SERE).
MAX_TENTATIVAS_SLOT = 15


async def buscar_documentos_api(pagina: Page, cgm: str) -> list[dict]:
    """
    Consulta listarArquivos e retorna a lista completa de documentos
    da pasta virtual do aluno.

    (Comportamento preservado de sere_2026.py::buscar_documentos_api.)
    """
    url = f"{URL_API_LISTAR}{cgm}"
    resultado = await pagina.evaluate(
        f"""
        async () => {{
            const resp = await fetch('{url}', {{credentials: 'include'}});
            if (!resp.ok) return null;
            return await resp.json();
        }}
        """
    )
    if resultado is None:
        logger.error("API listarArquivos retornou null para CGM=%s", cgm)
        return []
    logger.info("API: %d documentos para CGM=%s", len(resultado), cgm)
    return resultado


async def excluir_arquivo_api(pagina: Page, cgm: str, assinatura: str) -> bool:
    """
    Exclui um arquivo via POST mudarStatus. Retorna True se HTTP 2xx.

    (Comportamento preservado de sere_2026.py::excluir_arquivo_api.)
    """
    url_listar = f"{URL_API_LISTAR}{cgm}"
    resultado = await pagina.evaluate(
        f"""
        async () => {{
            await fetch('{url_listar}', {{credentials: 'include'}});
            const resp = await fetch('{URL_MUDAR_STATUS}', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'assinaturaArquivo={assinatura}&acao=EXCLUIR'
            }});
            return resp.ok;
        }}
        """
    )
    return bool(resultado)


def parse_validado(tag_raw) -> bool:
    """
    Verifica se o campo 'tag' retornado pela API listarArquivos indica
    que o documento foi validado (validado=SIM).

    Usada tanto pela atualização de documentos-alunos.json quanto por
    outras operações (validação, análise) que precisam saber se um
    documento já foi conferido pela secretaria.

    (Comportamento preservado de sere_2026.py::_parse_validado, usada
    em 4 pontos diferentes do script original — não é exclusiva da
    operação de limpeza, por isso mora aqui em vez de dentro dela.)
    """
    if not tag_raw:
        return False
    try:
        import json as _json

        tag_list = _json.loads(tag_raw) if isinstance(tag_raw, str) else tag_raw
        return any(
            str(t.get("validado", "")).upper() == "SIM"
            for t in tag_list
            if isinstance(t, dict)
        )
    except (ValueError, TypeError):
        return False


async def remover_slot(pagina: Page, cgm: str, doc: dict, norm) -> tuple[bool, str]:
    """
    Remove TODAS as versões empilhadas de um slot de documento.
    Itera até MAX_TENTATIVAS_SLOT ou até o slot ficar vazio.

    O parâmetro `norm` recebe a função de normalização de texto
    (backend.core.normalizacao.norm), injetada explicitamente em vez de
    importada aqui, para manter este módulo independente de qual
    estratégia de normalização é usada por quem o chama.

    (Comportamento preservado de sere_2026.py::remover_slot.)
    """
    slot = doc["tipodocumento"]
    slot_norm = norm(slot)
    versoes_removidas = 0

    for tentativa in range(1, MAX_TENTATIVAS_SLOT + 1):
        docs_atuais = await buscar_documentos_api(pagina, cgm)
        pendentes = [
            d
            for d in docs_atuais
            if norm(d.get("tipodocumento", "")) == slot_norm
            and d.get("nomearquivo", "").strip()
        ]

        if not pendentes:
            return True, f"Removido ({versoes_removidas} versão(ões))"

        versao_atual = pendentes[0]
        assinatura = versao_atual["assinaturaArquivo"]
        nome_arquivo = versao_atual.get("nomearquivo", "")

        logger.info(
            "Removendo versão %d de '%s': %s", versoes_removidas + 1, slot, nome_arquivo
        )

        try:
            ok = await excluir_arquivo_api(pagina, cgm, assinatura)
            if ok:
                versoes_removidas += 1
            else:
                logger.warning("mudarStatus não-OK — tentando excluirDocumento via JS")
                pagina.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
                await pagina.evaluate(f"excluirDocumento('{assinatura}')")
                versoes_removidas += 1
        except Exception as exc:
            logger.warning("Tentativa %d com erro: %s", tentativa, exc)

        await pagina.wait_for_timeout(1_200)

    docs_finais = await buscar_documentos_api(pagina, cgm)
    ainda_presente = any(
        norm(d.get("tipodocumento", "")) == slot_norm and d.get("nomearquivo", "").strip()
        for d in docs_finais
    )
    if not ainda_presente:
        return True, f"Removido ({versoes_removidas} versão(ões))"

    return False, (
        f"Falhou após {MAX_TENTATIVAS_SLOT} tentativas "
        f"({versoes_removidas} versão(ões) removida(s), slot ainda tem arquivo)"
    )
