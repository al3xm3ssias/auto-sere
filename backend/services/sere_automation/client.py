"""
client.py — Cliente central de sessão do SERE
=================================================

Extrai a lógica de login/sessão que hoje está duplicada, quase
idêntica, em ~29 scripts diferentes (ver docs/plano_migracao_sere_automation.md
para o mapeamento completo).

Decisões tomadas nessa extração (aprovadas antes da implementação):

- Engine padronizado em Firefox para todo o sistema. O código original
  tinha um bug em um dos modos de sere_2026.py, que chamava o atributo
  inválido `p.chrome` (Playwright só tem chromium/firefox/webkit) — os
  prints diziam "Firefox" mas o código tentava "chrome". Resolvido
  padronizando tudo em Firefox, que já era o mais usado no projeto.
- headless=True é o padrão para TODAS as operações — inclusive as que
  no script original abriam o navegador visível (ex.: Reprocessar_erros_2026.py
  usava headless=False). Para acompanhar o que o robô está fazendo sem
  precisar de interface gráfica, use debug=True (ver abaixo) em vez de
  headless=False.
- Timeout pós-login padronizado em 3000ms, que era o valor usado em
  ~90% dos scripts (2 exceções usavam 5000ms — continuam configuráveis
  via parâmetro quando necessário).
- accept_downloads é opt-in (era usado por só 2 dos ~29 scripts), não
  vira padrão para todos.
- A lógica de detecção de sessão caída + relogin automático
  (esta_na_tela_login / garantir_logado), que só existia dentro de
  sere_2026.py, foi generalizada aqui para beneficiar TODAS as
  operações que passarem a usar este client — não só as que já tinham.
- Modo debug (novo, sem equivalente no código original): quando
  debug=True, cada chamada a passo_debug() registra um log detalhado
  E salva um screenshot da página em PATHS.logs/debug/. Permite
  acompanhar exatamente o que o robô via em cada etapa, mesmo rodando
  headless=True — sem travar a máquina esperando alguém olhar a tela
  em tempo real, e funcionando igual em qualquer servidor sem
  interface gráfica.

Uso básico:

    from backend.services.sere_automation.client import SereClient

    async with SereClient() as sessao:
        await sessao.pagina.goto(...)
        # ... operação específica aqui ...

Uso com downloads habilitados:

    async with SereClient(accept_downloads=True) as sessao:
        ...

Uso com modo debug (logs verbosos + screenshot a cada passo):

    async with SereClient(debug=True) as sessao:
        await sessao.pagina.goto(...)
        await sessao.passo_debug("apos_abrir_pasta_virtual", cgm=cgm)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from backend.core.config import PATHS

logger = logging.getLogger(__name__)

URL_SERE = "https://www.sere.pr.gov.br/sere"

# Seletores do formulário de login do SERE — centralizados aqui para que
# uma eventual mudança no site precise ser corrigida em um único lugar.
SELETOR_CAMPO_LOGIN = "#CHAVE"
SELETOR_CAMPO_SENHA = "#CHAVE_ENCRIPT"
SELETOR_BOTAO_ENTRAR = "//input[@value='Entrar']"

TIMEOUT_PADRAO_POS_LOGIN_MS = 3_000


class ErroDeLogin(RuntimeError):
    """Levantado quando o login no SERE falha e não é possível recuperar a sessão."""


@dataclass
class Credenciais:
    """
    Wrapper simples em torno de LOGIN/SENHA.

    Mantém compatibilidade com o módulo `credenciais.py` local que os
    scripts legados já usam (from credenciais import LOGIN, SENHA),
    mas isola essa dependência aqui em vez de espalhá-la por 29 arquivos.
    """

    login: str
    senha: str

    @classmethod
    def do_modulo_local(cls) -> "Credenciais":
        """
        Carrega LOGIN e SENHA do módulo `credenciais.py` (não versionado,
        deve existir localmente em cada máquina — ver credenciais_modelo.py
        como template).
        """
        try:
            from credenciais import LOGIN, SENHA  # type: ignore
        except ImportError as exc:
            raise ErroDeLogin(
                "Não foi possível importar credenciais.py. Copie "
                "credenciais_modelo.py para credenciais.py e preencha "
                "LOGIN e SENHA localmente (esse arquivo nunca deve ser "
                "versionado no Git)."
            ) from exc

        if not LOGIN or not SENHA:
            raise ErroDeLogin("LOGIN e SENHA em credenciais.py não podem estar vazios.")

        return cls(login=LOGIN, senha=SENHA)


class SereClient:
    """
    Gerencia uma sessão autenticada no SERE: abre o navegador, faz login,
    garante o fechamento correto no final, e sabe se re-autenticar caso a
    sessão caia no meio de uma operação longa.

    Pensado para ser usado como um async context manager:

        async with SereClient() as sessao:
            await sessao.pagina.goto(alguma_url)
    """

    def __init__(
        self,
        credenciais: Optional[Credenciais] = None,
        *,
        headless: bool = True,
        accept_downloads: bool = False,
        timeout_pos_login_ms: int = TIMEOUT_PADRAO_POS_LOGIN_MS,
        url: str = URL_SERE,
        debug: bool = False,
    ) -> None:
        self._credenciais = credenciais or Credenciais.do_modulo_local()
        self._headless = headless
        self._accept_downloads = accept_downloads
        self._timeout_pos_login_ms = timeout_pos_login_ms
        self._url = url
        self.debug = debug
        self._contador_passos = 0
        self._pasta_debug: Optional[Path] = None

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.pagina: Optional[Page] = None

    # ── Ciclo de vida (context manager) ─────────────────────────────────

    async def __aenter__(self) -> "SereClient":
        await self._abrir()
        try:
            await self._fazer_login()
        except Exception:
            # Se o login falhar, __aexit__ nunca é chamado pelo Python
            # (a entrada no "with" não chegou a completar) — então o
            # fechamento precisa ser feito aqui mesmo, para não deixar
            # o navegador aberto em caso de falha de autenticação.
            await self.fechar()
            raise
        return self

    async def __aexit__(
        self,
        tipo_excecao: Optional[Type[BaseException]],
        excecao: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.fechar()

    async def _abrir(self) -> None:
        logger.debug("Iniciando Playwright (Firefox, headless=%s)", self._headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(headless=self._headless)

        if self._accept_downloads:
            self._context = await self._browser.new_context(accept_downloads=True)
            self.pagina = await self._context.new_page()
        else:
            self.pagina = await self._browser.new_page()

        if self.debug:
            marca_tempo = datetime.now().strftime("%Y%m%d-%H%M%S")
            self._pasta_debug = PATHS.logs / "debug" / marca_tempo
            self._pasta_debug.mkdir(parents=True, exist_ok=True)
            logger.info("Modo debug ativo — screenshots em: %s", self._pasta_debug)

    async def fechar(self) -> None:
        """Fecha o navegador e encerra o Playwright, mesmo se algo falhar antes."""
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        logger.debug("Sessão SERE encerrada.")

    # ── Login e recuperação de sessão ───────────────────────────────────

    async def _fazer_login(self) -> None:
        assert self.pagina is not None
        logger.info("Acessando SERE em %s", self._url)
        await self.pagina.goto(self._url)

        logger.info("Fazendo login…")
        await self.pagina.fill(SELETOR_CAMPO_LOGIN, self._credenciais.login)
        await self.pagina.fill(SELETOR_CAMPO_SENHA, self._credenciais.senha)
        await self.pagina.click(SELETOR_BOTAO_ENTRAR)
        await self.pagina.wait_for_timeout(self._timeout_pos_login_ms)

        if await self.esta_na_tela_login():
            raise ErroDeLogin(
                "Formulário de login ainda presente após tentativa de "
                "autenticação — verifique LOGIN/SENHA em credenciais.py."
            )
        logger.info("Login efetuado com sucesso.")

    async def esta_na_tela_login(self) -> bool:
        """
        Verifica se a página atual é a tela de login do SERE (existência
        do campo de usuário). Usado após navegação para detectar sessão
        caída — nesse caso o SERE volta a exibir o formulário de login
        em vez do menu esperado.

        (Comportamento preservado de sere_2026.py::esta_na_tela_login,
        generalizado aqui para beneficiar qualquer operação.)
        """
        assert self.pagina is not None
        try:
            elemento = await self.pagina.query_selector(SELETOR_CAMPO_LOGIN)
            return elemento is not None
        except Exception:
            return False

    async def garantir_logado(self) -> bool:
        """
        Garante que a página está autenticada no SERE. Se a sessão caiu
        (formulário de login reapareceu), refaz a autenticação.

        Retorna True se terminou autenticado (já estava ou logou de
        novo), False se a tentativa de relogin falhou.

        Chame isso antes de qualquer navegação em operações longas
        (ex.: processar uma lista grande de alunos), já que o SERE pode
        derrubar a sessão no meio do processo.

        (Comportamento preservado de sere_2026.py::garantir_logado.)
        """
        assert self.pagina is not None

        if not await self.esta_na_tela_login():
            return True

        logger.warning("Sessão caiu — refazendo login…")
        try:
            await self.pagina.fill(SELETOR_CAMPO_LOGIN, self._credenciais.login)
            await self.pagina.fill(SELETOR_CAMPO_SENHA, self._credenciais.senha)
            await self.pagina.click(SELETOR_BOTAO_ENTRAR)
            await self.pagina.wait_for_timeout(self._timeout_pos_login_ms)

            if await self.esta_na_tela_login():
                logger.error("Ainda na tela de login após tentativa de relogin.")
                return False
            return True
        except Exception:
            logger.exception("Erro ao tentar refazer o login.")
            return False

    # ── Modo debug (logs verbosos + screenshot por passo) ──────────────

    async def passo_debug(self, descricao: str, **contexto: object) -> None:
        """
        Registra um passo de depuração: log detalhado + screenshot da
        página atual. Não faz nada se debug=False (custo zero na
        execução normal).

        Pensado para ser espalhado nos pontos-chave de qualquer
        operação (após login, após abrir pasta virtual, antes/depois
        de cada exclusão de slot, etc.), permitindo revisar depois
        exatamente o que o robô via em cada etapa — mesmo rodando
        headless, sem precisar acompanhar ao vivo.

        Exemplo:
            await sessao.passo_debug("apos_abrir_pasta_virtual", cgm=cgm)
            await sessao.passo_debug("antes_excluir_slot", slot=slot, cgm=cgm)
        """
        if not self.debug or self.pagina is None:
            return

        self._contador_passos += 1
        detalhes = " | ".join(f"{k}={v}" for k, v in contexto.items())
        logger.debug("[DEBUG passo %03d] %s%s", self._contador_passos, descricao, f" | {detalhes}" if detalhes else "")

        if self._pasta_debug is not None:
            nome_arquivo = f"{self._contador_passos:03d}-{descricao}.png"
            caminho = self._pasta_debug / nome_arquivo
            try:
                await self.pagina.screenshot(path=str(caminho))
                logger.debug("[DEBUG passo %03d] screenshot salvo: %s", self._contador_passos, caminho)
            except Exception:
                logger.warning("Falha ao salvar screenshot de debug: %s", nome_arquivo, exc_info=True)
