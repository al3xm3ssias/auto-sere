"""
normalizacao.py — Biblioteca central de normalização de documentos do SERE
=============================================================================

Migrado de sere_normalizacao.py (script legado), preservando 100% da
lógica e do catálogo de dados (SERE_SLOTS, SINONIMOS) — nenhum valor foi
alterado nesta migração, apenas o local do arquivo no projeto.

Usado por qualquer módulo de backend/services/sere_automation/ e por
outros grupos (documentos/, organizacao_arquivos/) que precisem casar
nomes de arquivo com os tipos de documento oficiais do SERE.

Contém:
  • SERE_SLOTS        — catálogo completo de slots do SERE indexado por
                         idtipodocumento: grupo, nome canônico, ordem e flags.
  • IDTIPO_PARA_SLOT   — dict str→str para lookup rápido "idtipo → nome canônico"
  • NOME_PARA_ID       — dict str→int  "nome canônico → idtipo"
  • SINONIMOS          — mapeamento slot → lista de palavras-chave (maiúsculas,
                         sem acentos) para casar nomes de arquivo.
  • SINONIMOS_LOWER    — mesmo mapeamento em minúsculas/sem acentos.
  • norm()             — remove acentos e converte para MAIÚSCULAS.
  • norm_lower()       — remove acentos e converte para minúsculas.
  • resolver_slot()    — recebe qualquer texto e devolve o nome canônico do slot.
  • resolver_slot_lower() — idem, retornando em minúsculo.
  • slot_por_id()      — nome canônico a partir do idtipodocumento (int).
  • id_por_nome()      — idtipodocumento a partir do nome canônico.
  • slots_por_grupo()  — lista de slots de um grupo ordenada por 'ordem'.

Uso:
  from backend.core.normalizacao import (
      resolver_slot, resolver_slot_lower, slot_por_id, id_por_nome,
      norm, norm_lower, SINONIMOS, SINONIMOS_LOWER, SERE_SLOTS,
      IDTIPO_PARA_SLOT, NOME_PARA_ID, slots_por_grupo,
  )
"""

from __future__ import annotations

import unicodedata
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES DE NORMALIZAÇÃO (definidas antes dos dicts para uso inline)
# ─────────────────────────────────────────────────────────────────────────────

def norm(texto: str) -> str:
    """Remove acentos e converte para MAIÚSCULAS.

    >>> norm("Certidão de Nascimento")
    'CERTIDAO DE NASCIMENTO'
    """
    if not texto:
        return ""
    nfd = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return sem_acento.upper().strip()


def norm_lower(texto: str) -> str:
    """Remove acentos e converte para minúsculas.
    Usada por cruzar_documentos.py que trabalha internamente em lower-case.

    >>> norm_lower("Certidão de Nascimento")
    'certidao de nascimento'
    """
    if not texto:
        return ""
    nfd = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return sem_acento.lower().strip()


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO COMPLETO — todos os slots conhecidos do SERE
# Fonte: array retornado pela API listarArquivos (pasta virtual)
# ⚠  Sem campo "hash": o assinaturaArquivo é por arquivo/aluno, não por slot.
# ─────────────────────────────────────────────────────────────────────────────
SERE_SLOTS: dict[int, dict] = {

    # ── Grupo 1 — Identificação e Dados Pessoais ─────────────────────────────
    1: {
        "nome"       : "CPF Responsável",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "CPF/RNM/RME do Responsável",
        "ordem"      : 3,
        "cumulativo" : False,
        "por_periodo": False,
    },
    2: {
        "nome"       : "Certidão de nascimento do aluno",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "Certidão de Nascimento/Casamento/Óbito",
        "ordem"      : 1,
        "cumulativo" : True,
        "por_periodo": False,
    },
    8: {
        "nome"       : "RG",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "RG/RNM/RME/Passaporte do Estudante",
        "ordem"      : 4,
        "cumulativo" : False,
        "por_periodo": False,
    },
    12: {
        "nome"       : "CPF do Aluno",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "CPF do Estudante",
        "ordem"      : 2,
        "cumulativo" : False,
        "por_periodo": False,
    },
    17: {
        "nome"       : "Registro Nacional de Migrante (RNM)",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "Registro Nacional de Migrante (RNM)",
        "ordem"      : None,
        "cumulativo" : False,
        "por_periodo": False,
    },
    18: {
        "nome"       : "Comprovante de Emancipação",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "Documento Comprobatório de Emancipação",
        "ordem"      : 5,
        "cumulativo" : False,
        "por_periodo": False,
    },
    20: {
        "nome"       : "Requerimento de Nome Social",
        "grupo_cod"  : 1,
        "grupo_nome" : "Identificação e Dados Pessoais",
        "item_sere"  : "Requerimento de Nome Social",
        "ordem"      : 6,
        "cumulativo" : False,
        "por_periodo": False,
    },

    # ── Grupo 2 — Comprovantes e Autorizações ─────────────────────────────────
    3: {
        "nome"       : "Comprovante de residência",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Comprovante de Residência",
        "ordem"      : 1,
        "cumulativo" : False,
        "por_periodo": False,
    },
    4: {
        "nome"       : "Comprovante de Vacinação",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Comprovante de Vacinação",
        "ordem"      : 3,
        "cumulativo" : False,
        "por_periodo": False,
    },
    11: {
        "nome"       : "Declaração de vacina",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Declaração de vacina",
        "ordem"      : 4,
        "cumulativo" : False,
        "por_periodo": False,
    },
    14: {
        "nome"       : "Ficha de Saúde",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Ficha de Saúde",
        "ordem"      : 5,
        "cumulativo" : False,
        "por_periodo": False,
    },
    15: {
        "nome"       : "Autorizacão de uso de imagem",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Termo de Uso de Imagem",
        "ordem"      : 6,
        "cumulativo" : False,
        "por_periodo": False,
    },
    16: {
        "nome"       : "Comprovante de trabalho",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Comprovante de Trabalho",
        "ordem"      : 2,
        "cumulativo" : False,
        "por_periodo": False,
    },
    32: {
        "nome"       : "reservado, sem uso (Termo de Cessão de Uso de Imagem)",
        "grupo_cod"  : 2,
        "grupo_nome" : "Comprovantes e Autorizações",
        "item_sere"  : "Termo de Anuência do Noturno",
        "ordem"      : 7,
        "cumulativo" : False,
        "por_periodo": False,
    },

    # ── Grupo 3 — Histórico e Vida Escolar ───────────────────────────────────
    5: {
        "nome"       : "Transferência escolar",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Documentos de Transferência Escolar",
        "ordem"      : 1,
        "cumulativo" : True,
        "por_periodo": False,
    },
    6: {
        "nome"       : "Declaração de Matricula",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Declaração de Matricula",
        "ordem"      : 8,
        "cumulativo" : False,
        "por_periodo": False,
    },
    7: {
        "nome"       : "Requerimento de Matricula",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Requerimento de Matrícula",
        "ordem"      : 7,
        "cumulativo" : False,
        "por_periodo": True,
    },
    9: {
        "nome"       : "Histórico do Ensino Fundamental",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Histórico Escolar do Ensino Fundamental",
        "ordem"      : 3,
        "cumulativo" : True,
        "por_periodo": False,
    },
    10: {
        "nome"       : "Guia de Transferência",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Guia de Transferência",
        "ordem"      : 9,
        "cumulativo" : False,
        "por_periodo": False,
    },
    13: {
        "nome"       : "Declaração - Aluno Monitor",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Declaração Aluno Monitor",
        "ordem"      : 10,
        "cumulativo" : False,
        "por_periodo": False,
    },
    19: {
        "nome"       : "Declaração de Matrícula",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Declaração de Matrícula",
        "ordem"      : None,
        "cumulativo" : False,
        "por_periodo": False,
    },
    21: {
        "nome"       : "reservado, sem uso (HEFund)",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Ficha Individual",
        "ordem"      : 2,
        "cumulativo" : False,
        "por_periodo": True,
    },
    22: {
        "nome"       : "Histórico do Ensino Fundamental de estudos realizados no exterior",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Histórico do Ensino Fundamental de estudos realizados no exterior",
        "ordem"      : 11,
        "cumulativo" : False,
        "por_periodo": False,
    },
    23: {
        "nome"       : "Histórico do Ensino Médio",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Histórico Escolar do Ensino Médio",
        "ordem"      : 4,
        "cumulativo" : True,
        "por_periodo": False,
    },
    24: {
        "nome"       : "Histórico do Ensino Médio de estudos realizados no exterior",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Histórico do Ensino Médio de estudos realizados no exterior",
        "ordem"      : 12,
        "cumulativo" : False,
        "por_periodo": False,
    },
    25: {
        "nome"       : "reservado, sem uso (Ficha de Saúde)",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Histórico Escolar de Migrantes",
        "ordem"      : 5,
        "cumulativo" : False,
        "por_periodo": False,
    },
    30: {
        "nome"       : "Ficha de acompanhamento de estágio",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Ficha de Acompanhamento de Estágio",
        "ordem"      : 6,
        "cumulativo" : True,
        "por_periodo": False,
    },
    33: {
        "nome"       : "Declaração de Equivalência de estudos no exterior",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Declaração de Equivalência de estudos no exterior",
        "ordem"      : 13,
        "cumulativo" : False,
        "por_periodo": False,
    },
    34: {
        "nome"       : "Certificado do CELEM",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "Certificado do CELEM",
        "ordem"      : 14,
        "cumulativo" : False,
        "por_periodo": False,
    },
    36: {
        "nome"       : "2ª Via Diploma Técnico",
        "grupo_cod"  : 3,
        "grupo_nome" : "Histórico e Vida Escolar",
        "item_sere"  : "2ª Via Diploma Técnico",
        "ordem"      : 15,
        "cumulativo" : False,
        "por_periodo": False,
    },

    # ── Grupo 4 — Atas e Pareceres Regulatórios ───────────────────────────────
    26: {
        "nome"       : "ATA de Adaptação/Classificação/Reclassificação",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Ata de Adaptação/ (Re)Classificação",
        "ordem"      : 1,
        "cumulativo" : True,
        "por_periodo": False,
    },
    27: {
        "nome"       : "ATA de Regularização de Vida Escolar/Parecer/ATO",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Ata e Parecer de Regularização de Vida Escolar",
        "ordem"      : 2,
        "cumulativo" : False,
        "por_periodo": False,
    },
    28: {
        "nome"       : "ATA de Erro em Relatório Final",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Ata de Erro em Relatório Final",
        "ordem"      : 3,
        "cumulativo" : True,
        "por_periodo": False,
    },
    29: {
        "nome"       : "ATA de Revalidação de estudos realizados no exterior",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Ata de Revalidação de Estudos",
        "ordem"      : 5,
        "cumulativo" : False,
        "por_periodo": False,
    },
    31: {
        "nome"       : "Parecer Descritivo",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Parecer Descritivo",
        "ordem"      : 6,
        "cumulativo" : True,
        "por_periodo": False,
    },
    35: {
        "nome"       : "Certificado exames On-Line",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Ata do Ganhando o Mundo",
        "ordem"      : 4,
        "cumulativo" : False,
        "por_periodo": False,
    },
    37: {
        "nome"       : "Parecer Descritivo 2025-1",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Parecer Descritivo 2025-1",
        "ordem"      : 6,
        "cumulativo" : False,
        "por_periodo": False,
    },
    38: {
        "nome"       : "Parecer Descritivo 2026-1",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Parecer Descritivo 2026-1",
        "ordem"      : 7,
        "cumulativo" : False,
        "por_periodo": False,
    },
    39: {
        "nome"       : "Avaliação de Ingresso",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Avaliação de Ingresso",
        "ordem"      : 8,
        "cumulativo" : False,
        "por_periodo": False,
    },
    40: {
        "nome"       : "Plano Educacional (EE)",
        "grupo_cod"  : 4,
        "grupo_nome" : "Atas e Pareceres Regulatórios",
        "item_sere"  : "Plano Educacional (EE)",
        "ordem"      : 7,
        "cumulativo" : False,
        "por_periodo": False,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICES DERIVADOS
# ─────────────────────────────────────────────────────────────────────────────

# str(idtipo) → nome canônico  (compatível com Upload_documentos_2026 que usa str)
IDTIPO_PARA_SLOT: dict[str, str] = {str(k): v["nome"] for k, v in SERE_SLOTS.items()}

# nome canônico → idtipo (int)
NOME_PARA_ID: dict[str, int] = {v["nome"]: k for k, v in SERE_SLOTS.items()}


# ─────────────────────────────────────────────────────────────────────────────
# SINÔNIMOS — para casar nomes de arquivo com slots
# Chave  : nome canônico do slot (deve existir em SERE_SLOTS)
# Valores: palavras/frases normalizadas em MAIÚSCULAS sem acento.
#
# Regra de precedência na construção do índice invertido:
#   palavra-chave mais longa vence (evita que "VACINA" cubra "COMPROVANTE DE VACINACAO").
# ─────────────────────────────────────────────────────────────────────────────
SINONIMOS: dict[str, list[str]] = {

    # ── Grupo 1 — Identificação e Dados Pessoais ─────────────────────────────
    "CPF Responsável": [
        "CPF DO RESPONSAVEL",
        "CPF DO RESPONSÁVEL",
        "CPF RESPONSAVEL",
        "CPF RESPONSÁVEL",
        "DOCUMENTO DO RESPONSAVEL",
        "RG E CPF DO RESPONSAVEL",
        "DOCUMENTOS DOS RESPONSAVEIS",
        "CPF PAI",
        "CPF MAE",
        "CPF MÃE",
        "DOCUMENTO RESPONSAVEL",
        "RESPONSAVEL",
        "DOCUMENTOS",
        "DOCUMENTO",
    ],
    # Alias — variante de capitalização retornada pela API (idtipo 1)
    "CPF do Responsável": [
        "CPF DO RESPONSAVEL",
        "CPF DO RESPONSÁVEL",
        "CPF RESPONSAVEL",
        "CPF RESPONSÁVEL",
        "DOCUMENTO DO RESPONSAVEL",
        "RG E CPF DO RESPONSAVEL",
        "DOCUMENTOS DOS RESPONSAVEIS",
        "CPF PAI",
        "CPF MAE",
        "CPF MÃE",
        "DOCUMENTO RESPONSAVEL",
        "RESPONSAVEL",
        "DOCUMENTOS",
        "DOCUMENTO",
    ],
    "Certidão de nascimento do aluno": [
        "CERTIDAO DE NASCIMENTO DO ALUNO",
        "CERTIDAO DE NASCIMENTO",
        "CERTIDÃO DE NASCIMENTO",
        "CERTIDAO DO ALUNO",
        "CERTIDAO",
        "CERTIDÃO",
        "NASCIMENTO",
    ],
    "RG": [
        "RG DO ALUNO",
        "RG ALUNO",
        "IDENTIDADE DO ALUNO",
        "RG",
        "IDENTIDADE",
        "DOCUMENTO DE IDENTIDADE",
    ],
    # Alias — usado internamente nos scripts como "RG do aluno"
    "RG do aluno": [
        "RG DO ALUNO",
        "RG ALUNO",
        "IDENTIDADE DO ALUNO",
        "RG",
    ],
    "CPF do Aluno": [
        "CPF DO ALUNO",
        "CPF ALUNO",
        "RG E CPF DO ALUNO",
    ],
    # Alias minúsculo usado por Upload_documentos_2026 em SLOTS_ATIVOS
    "CPF do aluno": [
        "CPF DO ALUNO",
        "CPF ALUNO",
        "RG E CPF DO ALUNO",
    ],
    "Registro Nacional de Migrante (RNM)": [
        "RNM",
        "REGISTRO NACIONAL DE MIGRANTE",
        "MIGRANTE",
        "RME",
    ],
    "Comprovante de Emancipação": [
        "COMPROVANTE DE EMANCIPACAO",
        "COMPROVANTE DE EMANCIPAÇÃO",
        "EMANCIPACAO",
        "EMANCIPAÇÃO",
    ],
    "Requerimento de Nome Social": [
        "REQUERIMENTO DE NOME SOCIAL",
        "REQUERIMENTO NOME SOCIAL",
        "NOME SOCIAL",
    ],

    # ── Grupo 2 — Comprovantes e Autorizações ─────────────────────────────────
    "Comprovante de residência": [
        "COMPROVANTE DE RESIDENCIA",
        "COMPROVANTE DE RESIDÊNCIA",
        "RESIDENCIA",
        "RESIDÊNCIA",
        "ENDERECO",
        "ENDEREÇO",
        "COPEL",
        "SANEPAR",
        "TALAO",
        "CONTA DE LUZ",
        "CONTA DE AGUA",
        "CONTA DE ÁGUA",
    ],
    "Comprovante de Vacinação": [
        "COMPROVANTE DE VACINACAO",
        "COMPROVANTE DE VACINAÇÃO",
        "CARTEIRA DE VACINACAO",
        "CARTEIRA DE VACINAÇÃO",
        "CARTEIRINHA DE VACINACAO",
        "CARTEIRINHA DE VACINAÇÃO",
        "CARTAO DE VACINACAO",
        "CARTÃO DE VACINAÇÃO",
        "CARTEIRINHA",
        "CARTEIRA",
    ],
    # Alias — nome usado internamente nos scripts
    "Carteira de vacinação": [
        "CARTEIRA DE VACINACAO",
        "CARTEIRA DE VACINAÇÃO",
        "CARTEIRINHA DE VACINACAO",
        "CARTEIRINHA DE VACINAÇÃO",
        "CARTAO DE VACINACAO",
        "CARTÃO DE VACINAÇÃO",
        "CARTEIRINHA",
        "CARTEIRA",
    ],
    "Declaração de vacina": [
        "DECLARACAO DE VACINA",
        "DECLARAÇÃO DE VACINA",
        "VACINACAO",
        "VACINAÇÃO",
        "VACINA",
    ],
    "Ficha de Saúde": [
        "FICHA DE SAUDE",
        "FICHA DE SAÚDE",
        "FICHA SAUDE",
    ],
    "Autorizacão de uso de imagem": [
        "AUTORIZACAO DE USO DE IMAGEM",
        "AUTORIZAÇÃO DE USO DE IMAGEM",
        "TERMO DE USO DE IMAGEM",
        "TERMO DE IMAGEM",
        "USO DE IMAGEM",
        "CESSAO DE IMAGEM",
        "IMAGEM",
    ],
    # Alias normalizado (grafia correta com acento)
    "Autorização de uso de imagem": [
        "AUTORIZACAO DE USO DE IMAGEM",
        "AUTORIZAÇÃO DE USO DE IMAGEM",
        "TERMO DE USO DE IMAGEM",
        "TERMO DE IMAGEM",
        "USO DE IMAGEM",
        "CESSAO DE IMAGEM",
        "IMAGEM",
    ],
    "Comprovante de trabalho": [
        "COMPROVANTE DE TRABALHO",
        "CARTEIRA DE TRABALHO",
        "CTPS",
        "HOLERITE",
        "CONTRACHEQUE",
        "TRABALHO",
        "EMPREGO",
    ],

    # ── Grupo 3 — Histórico e Vida Escolar ───────────────────────────────────
    "Requerimento de Matricula": [
        "REQUERIMENTO DE MATRICULA",
        "REQUERIMENTO DE MATRÍCULA",
        "REQUERIMENTO",
        "MATRICULA",
        "MATRÍCULA",
    ],
    "Declaração de Matricula": [
        "DECLARACAO DE MATRICULA",
        "DECLARAÇÃO DE MATRICULA",
        "DECLARACAO DE MATRÍCULA",
        "DECLARAÇÃO DE MATRÍCULA",
    ],
    "Declaração de Matrícula": [
        "DECLARACAO DE MATRICULA",
        "DECLARAÇÃO DE MATRICULA",
        "DECLARACAO DE MATRÍCULA",
        "DECLARAÇÃO DE MATRÍCULA",
    ],
    "Transferência escolar": [
        "TRANSFERENCIA ESCOLAR",
        "TRANSFERÊNCIA ESCOLAR",
        "DECLARACAO DE TRANSFERENCIA",
        "DECLARAÇÃO DE TRANSFERÊNCIA",
        "TRANSFERENCIA",
    ],
    "Guia de Transferência": [
        "GUIA DE TRANSFERENCIA",
        "GUIA DE TRANSFERÊNCIA",
        "GUIA TRANSFERENCIA",
        "GUIA TRANSFERÊNCIA",
    ],
    "Histórico do Ensino Fundamental": [
        "HISTORICO ESCOLAR DO ENSINO FUNDAMENTAL",
        "HISTORICO DO ENSINO FUNDAMENTAL",
        "HISTORICO FUNDAMENTAL",
        "HIST FUNDAMENTAL",
        "HIST ESC FUNDAMENTAL",
    ],
    "Histórico do Ensino Médio": [
        "HISTORICO ESCOLAR DO ENSINO MEDIO",
        "HISTORICO DO ENSINO MEDIO",
        "HISTORICO MEDIO",
        "HIST MEDIO",
        "HIST ESC MEDIO",
    ],
    "Histórico do Ensino Fundamental de estudos realizados no exterior": [
        "HISTORICO FUNDAMENTAL EXTERIOR",
        "HISTORICO FUNDAMENTAL NO EXTERIOR",
        "HIST FUNDAMENTAL EXTERIOR",
    ],
    "Histórico do Ensino Médio de estudos realizados no exterior": [
        "HISTORICO MEDIO EXTERIOR",
        "HISTORICO MEDIO NO EXTERIOR",
        "HIST MEDIO EXTERIOR",
    ],
    "Declaração - Aluno Monitor": [
        "DECLARACAO ALUNO MONITOR",
        "DECLARAÇÃO ALUNO MONITOR",
        "ALUNO MONITOR",
    ],
    "Ficha de acompanhamento de estágio": [
        "FICHA DE ESTAGIO",
        "FICHA DE ESTÁGIO",
        "FICHA ESTAGIO",
        "ACOMPANHAMENTO DE ESTAGIO",
        "FICHA ACOMPANHAMENTO ESTAGIO",
    ],
    "Declaração de Equivalência de estudos no exterior": [
        "DECLARACAO DE EQUIVALENCIA",
        "DECLARAÇÃO DE EQUIVALÊNCIA",
        "EQUIVALENCIA",
        "EQUIVALÊNCIA",
        "ESTUDOS NO EXTERIOR",
    ],
    "Certificado do CELEM": [
        "CERTIFICADO CELEM",
        "CELEM",
    ],
    "2ª Via Diploma Técnico": [
        "2 VIA DIPLOMA TECNICO",
        "SEGUNDA VIA DIPLOMA TECNICO",
        "2A VIA DIPLOMA",
        "2 VIA DIPLOMA",
        "SEGUNDA VIA DIPLOMA",
        "DIPLOMA TECNICO",
        "DIPLOMA TÉCNICO",
        "DIPLOMA",
    ],

    # ── Grupo 4 — Atas e Pareceres Regulatórios ───────────────────────────────
    # Específicos ANTES do genérico para que o índice invertido os prefira
    "Parecer Descritivo 2025-1": [
        "PARECER DESCRITIVO 2025-1",
        "PARECER DESCRITIVO 2025",
        "PARECER 2025",
    ],
    "Parecer Descritivo 2026-1": [
        "PARECER DESCRITIVO 2026-1",
        "PARECER DESCRITIVO 2026",
        "PARECER 2026",
    ],
    # Genérico — deve ficar DEPOIS dos específicos no dict
    "Parecer Descritivo": [
        "PARECER DESCRITIVO",
        "PARECER",
    ],
    "ATA de Adaptação/Classificação/Reclassificação": [
        "ATA ADAPTACAO",
        "ATA ADAPTAÇÃO",
        "ATA CLASSIFICACAO",
        "ATA CLASSIFICAÇÃO",
        "ATA RECLASSIFICACAO",
        "ATA RECLASSIFICAÇÃO",
        "ADAPTACAO",
        "ADAPTAÇÃO",
        "RECLASSIFICACAO",
        "RECLASSIFICAÇÃO",
    ],
    "ATA de Regularização de Vida Escolar/Parecer/ATO": [
        "ATA REGULARIZACAO",
        "ATA REGULARIZAÇÃO",
        "REGULARIZACAO VIDA ESCOLAR",
        "REGULARIZAÇÃO VIDA ESCOLAR",
        "ATO",
    ],
    "ATA de Erro em Relatório Final": [
        "ATA DE ERRO EM RELATORIO FINAL",
        "ATA ERRO",
        "ATA DE ERRO",
        "ERRO RELATORIO FINAL",
        "ERRO RELATÓRIO FINAL",
    ],
    "ATA de Revalidação de estudos realizados no exterior": [
        "ATA REVALIDACAO",
        "ATA REVALIDAÇÃO",
        "REVALIDACAO EXTERIOR",
        "REVALIDAÇÃO EXTERIOR",
        "REVALIDACAO",
        "REVALIDAÇÃO",
    ],
    "Certificado exames On-Line": [
        "CERTIFICADO EXAME ON-LINE",
        "CERTIFICADO EXAME ONLINE",
        "EXAME ON-LINE",
        "EXAME ONLINE",
        "CERTIFICADO ONLINE",
        "CERTIFICADO EXAME",
        "GANHANDO O MUNDO",
    ],
    "Avaliação de Ingresso": [
        "AVALIACAO DE INGRESSO",
        "AVALIAÇÃO DE INGRESSO",
        "AVALIACAO INGRESSO",
        "AVALIAÇÃO INGRESSO",
        "INGRESSO",
    ],
    "Plano Educacional (EE)": [
        "PLANO EDUCACIONAL EE",
        "PLANO EDUCACIONAL",
        "PLANO EE",
        "PEI",
    ],
}

# SINONIMOS_LOWER — mesmos dados em minúsculo para cruzar_documentos.py
# Gerado automaticamente; não edite diretamente.
SINONIMOS_LOWER: dict[str, list[str]] = {
    slot: [kw.lower() for kw in keywords]
    for slot, keywords in SINONIMOS.items()
}


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE INVERTIDO — construído automaticamente
# Chave: palavra-chave normalizada (MAIÚSCULA) → nome canônico do slot
# Palavra-chave mais longa prevalece em caso de conflito.
# ─────────────────────────────────────────────────────────────────────────────
def _build_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for slot_name, keywords in SINONIMOS.items():
        for kw in keywords:
            kw_norm = norm(kw)
            # Mantém a palavra-chave mais longa em caso de colisão
            if kw_norm not in idx or len(kw_norm) > len(idx[kw_norm]):
                idx[kw_norm] = slot_name
    return idx

_INDICE_INVERTIDO: dict[str, str] = {}


def _ensure_index() -> None:
    global _INDICE_INVERTIDO
    if not _INDICE_INVERTIDO:
        _INDICE_INVERTIDO = _build_index()


def _build_index_lower() -> dict[str, str]:
    idx: dict[str, str] = {}
    for slot_name, keywords in SINONIMOS_LOWER.items():
        for kw in keywords:
            kw_n = norm_lower(kw)
            if kw_n not in idx or len(kw_n) > len(idx[kw_n]):
                idx[kw_n] = slot_name
    return idx

_INDICE_LOWER: dict[str, str] = {}


def _ensure_index_lower() -> None:
    global _INDICE_LOWER
    if not _INDICE_LOWER:
        _INDICE_LOWER = _build_index_lower()


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES PÚBLICAS
# ─────────────────────────────────────────────────────────────────────────────

def resolver_slot(texto: str) -> Optional[str]:
    """Recebe qualquer texto (nome de arquivo, tipo do SERE, etc.) e devolve
    o nome canônico do slot SERE correspondente, ou None se não encontrado.

    Estratégia (ordem de prioridade):
      1. Correspondência exata após norm().
      2. Verifica se alguma palavra-chave do índice está contida no texto
         (prefere a mais longa — mais específica).

    Exemplos:
      resolver_slot("1028828167_Certidao_de_Nascimento.pdf")
          → "Certidão de nascimento do aluno"
      resolver_slot("COPEL")
          → "Comprovante de residência"
      resolver_slot("xyz_desconhecido.pdf")
          → None
    """
    _ensure_index()
    texto_norm = norm(texto)

    if texto_norm in _INDICE_INVERTIDO:
        return _INDICE_INVERTIDO[texto_norm]

    melhor: Optional[str] = None
    melhor_len = 0
    for kw, slot in _INDICE_INVERTIDO.items():
        if kw in texto_norm and len(kw) > melhor_len:
            melhor = slot
            melhor_len = len(kw)

    return melhor


def resolver_slot_lower(texto: str) -> Optional[str]:
    """Igual a resolver_slot(), mas trabalha em minúsculas.
    Usada por cruzar_documentos.py cujas chaves internas estão em lower-case.

    Exemplos:
      resolver_slot_lower("certidao de nascimento") → "Certidão de nascimento do aluno"
      resolver_slot_lower("comprovante de residencia") → "Comprovante de residência"
    """
    _ensure_index_lower()
    texto_norm = norm_lower(texto)

    if texto_norm in _INDICE_LOWER:
        return _INDICE_LOWER[texto_norm]

    melhor: Optional[str] = None
    melhor_len = 0
    for kw, slot in _INDICE_LOWER.items():
        if kw in texto_norm and len(kw) > melhor_len:
            melhor = slot
            melhor_len = len(kw)

    return melhor


def slot_por_id(idtipo: int) -> Optional[str]:
    """Devolve o nome canônico do slot a partir do idtipodocumento (int).

    >>> slot_por_id(4)
    'Comprovante de Vacinação'
    >>> slot_por_id(999)
    None
    """
    entry = SERE_SLOTS.get(idtipo)
    return entry["nome"] if entry else None


def id_por_nome(nome: str) -> Optional[int]:
    """Devolve o idtipodocumento (int) a partir do nome canônico do slot."""
    return NOME_PARA_ID.get(nome)


def slots_por_grupo(grupo_cod: int) -> list[dict]:
    """Devolve a lista de slots de um grupo, ordenada pelo campo 'ordem'."""
    resultado = [
        {"id": k, **v}
        for k, v in SERE_SLOTS.items()
        if v["grupo_cod"] == grupo_cod
    ]
    return sorted(resultado, key=lambda x: (x["ordem"] is None, x["ordem"]))


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-TEST rápido — execute: python sere_normalizacao.py
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    casos = [
        # (texto_entrada, esperado_resolver_slot)
        ("1028828167_Certidao_de_Nascimento.pdf", "Certidão de nascimento do aluno"),
        ("COPEL",                                  "Comprovante de residência"),
        ("SANEPAR_conta",                          "Comprovante de residência"),
        ("vacina_crianca",                         "Declaração de vacina"),
        ("RG_ALUNO",                               "RG"),
        ("CPF DO RESPONSAVEL",                     "CPF Responsável"),
        ("PARECER_2026",                           "Parecer Descritivo 2026-1"),
        ("PARECER_2025",                           "Parecer Descritivo 2025-1"),
        ("xyz_desconhecido.pdf",                   None),
    ]
    casos_lower = [
        # (texto_lower, esperado_resolver_slot_lower)
        ("certidao de nascimento",      "Certidão de nascimento do aluno"),
        ("comprovante de residencia",   "Comprovante de residência"),
        ("comprovante de vacinacao",    "Comprovante de Vacinação"),
        ("cpf do aluno",                "CPF do Aluno"),
        ("cpf responsavel",             "CPF Responsável"),
        ("rg do aluno",                 "RG"),
    ]
    print("=" * 65)
    print("SMOKE-TEST — sere_normalizacao.py")
    print("=" * 65)
    ok = err = 0
    for texto, esperado in casos:
        resultado = resolver_slot(texto)
        status = "✅" if resultado == esperado else "❌"
        if resultado == esperado:
            ok += 1
        else:
            err += 1
        print(f"  {status}  '{texto}'")
        if resultado != esperado:
            print(f"       esperado : {esperado!r}")
            print(f"       obtido   : {resultado!r}")
    print()
    print("── resolver_slot_lower (para cruzar_documentos) ──")
    for texto, esperado in casos_lower:
        resultado = resolver_slot_lower(texto)
        status = "✅" if resultado == esperado else "❌"
        if resultado == esperado:
            ok += 1
        else:
            err += 1
        print(f"  {status}  '{texto}'")
        if resultado != esperado:
            print(f"       esperado : {esperado!r}")
            print(f"       obtido   : {resultado!r}")
    print("=" * 65)
    print(f"  {ok} OK  |  {err} FALHA(S)")
    print()
    print("slot_por_id(4)  →", slot_por_id(4))
    print("slot_por_id(31) →", slot_por_id(31))
    print("id_por_nome('Comprovante de residência') →", id_por_nome("Comprovante de residência"))
    print("slots_por_grupo(1) →", [s["nome"] for s in slots_por_grupo(1)])
    print("=" * 65)
