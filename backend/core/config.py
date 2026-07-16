"""
config.py — Configuração central de caminhos do Auto-SERE
============================================================

Nenhum módulo do sistema deve declarar um caminho absoluto próprio
(nem "D:\\ESCOLA JUDITH", nem "/home/usuario/compartilhado/...").

Toda máquina da rede (PC servidor ou cliente) enxerga a mesma pasta
compartilhada por um caminho local diferente. Essa diferença é
resolvida em UM único lugar: a variável de ambiente AUTOSERE_DATA_DIR,
configurada uma vez por máquina (ver docs/instalacao.md).

Uso básico (em qualquer módulo do backend):

    from backend.core.config import PATHS

    caminho_turmas = PATHS.dados / "turmas.json"
    pasta_pareceres = PATHS.transf_pareceres

Se AUTOSERE_DATA_DIR não estiver definida, é levantado um erro claro
na inicialização, em vez de o sistema falhar silenciosamente mais
tarde com "arquivo não encontrado" em um caminho errado.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfiguracaoAusente(RuntimeError):
    """Levantado quando uma variável de ambiente obrigatória não está definida."""


def _raiz_dados() -> Path:
    valor = os.environ.get("AUTOSERE_DATA_DIR")
    if not valor:
        raise ConfiguracaoAusente(
            "A variável de ambiente AUTOSERE_DATA_DIR não está definida.\n"
            "Configure um arquivo .env na raiz do projeto apontando para "
            "onde esta máquina enxerga a pasta compartilhada da escola.\n"
            "Veja docs/instalacao.md para o valor correto em cada tipo de máquina."
        )
    return Path(valor)


@dataclass(frozen=True)
class Paths:
    """
    Caminhos derivados da raiz de dados compartilhada (AUTOSERE_DATA_DIR).

    A estrutura de subpastas reflete a árvore já usada pelos scripts
    legados (PYTHON/SERE/2026, 2026/DIGITALIZAÇÃO, 2026/TRANSFERENCIAS/...),
    reconstruída a partir do mapeamento de caminhos absolutos do projeto
    original. Ver docs/plano_migracao_sere_automation.md para o histórico
    desse mapeamento.
    """

    raiz: Path = field(default_factory=_raiz_dados)

    # ── Dados estruturados (JSONs de estado) ────────────────────────────
    @property
    def dados(self) -> Path:
        """turmas.json, alunos.json, documentos-alunos.json, cruzamento-documentos.json..."""
        return self.raiz / "PYTHON" / "SERE" / "2026"

    # ── Documentos físicos digitalizados ────────────────────────────────
    @property
    def digitalizacao(self) -> Path:
        return self.raiz / "2026" / "DIGITALIZAÇÃO"

    @property
    def digitalizacao_backup(self) -> Path:
        return self.raiz / "2026" / "DIGITALIZAÇÃO-BACKUP"

    # ── Transferências ───────────────────────────────────────────────────
    # Nota: "TRANSFERENCIAS/HISTÓRICOS" e a antiga referência solta a
    # "HISTÓRICOS/2025/..." foram confirmadas como a MESMA pasta física
    # (ver plano de migração) — por isso existe só uma propriedade aqui.
    @property
    def transf_pareceres(self) -> Path:
        return self.raiz / "2026" / "TRANSFERENCIAS" / "PARECERES"

    @property
    def transf_guias(self) -> Path:
        return self.raiz / "2026" / "TRANSFERENCIAS" / "GUIA DE TRANSFERENCIA"

    @property
    def transf_historicos(self) -> Path:
        return self.raiz / "2026" / "TRANSFERENCIAS" / "HISTÓRICOS"

    # ── Infraestrutura do próprio sistema (não dados da escola) ─────────
    @property
    def logs(self) -> Path:
        return self.raiz / "logs"

    @property
    def cache(self) -> Path:
        return self.raiz / "cache"

    def historicos_por_ano(self, ano: str, subpasta: str = "") -> Path:
        """
        Caminho para históricos de um ano específico, ex.:
            PATHS.historicos_por_ano("2025", "OUTRAS TURMAS")
            PATHS.historicos_por_ano("2025", "PARECERES")
        """
        base = self.raiz / "HISTÓRICOS" / ano
        return base / subpasta if subpasta else base

    def garantir_pastas_essenciais(self) -> None:
        """
        Cria (se não existirem) as pastas de infraestrutura do próprio
        sistema — logs e cache. NÃO cria pastas de dados da escola
        (digitalização, transferências etc.), pois essas já devem
        existir na estrutura compartilhada e sua ausência normalmente
        indica um problema de configuração, não algo a criar
        silenciosamente.
        """
        self.logs.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)


# Instância única, importada pelo resto do sistema.
# A leitura de AUTOSERE_DATA_DIR só acontece quando PATHS é criado —
# ou seja, na primeira vez que este módulo é importado.
PATHS = Paths()
