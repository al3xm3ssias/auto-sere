# CLAUDE.md

# Auto-SERE

Este documento contém as regras permanentes deste projeto.

Estas instruções têm prioridade durante todo o desenvolvimento.

---

# Objetivo

Este projeto transforma diversos scripts Python independentes utilizados diariamente em um único sistema integrado chamado **Auto-SERE**.

O sistema deverá ser modular, escalável, organizado e preparado para crescimento futuro.

Nunca trate este projeto como um conjunto de scripts isolados.

Sempre considere que ele é um software completo.

---

# Arquitetura

O sistema possuirá dois componentes principais.

## Servidor

Responsável por:

- processamento
- banco de dados
- scheduler
- fila de tarefas
- OCR
- automações
- API
- autenticação
- logs
- armazenamento de configurações
- gerenciamento de usuários
- gerenciamento de clientes

Toda regra de negócio deve ficar aqui.

---

## Cliente

O cliente será apenas uma interface.

Ele poderá existir em duas versões:

- Web
- Desktop

Ambos utilizarão exatamente a mesma API.

Nenhuma regra de negócio deverá ficar no cliente.

---

# Organização do projeto

Sempre manter a seguinte estrutura.

```
auto-sere/

backend/
frontend-web/
frontend-desktop/
shared/
docs/
tests/
assets/
logs/
data/
docker/
```

Nunca criar arquivos soltos na raiz.

---

# Organização dos scripts

Os scripts atuais deverão ser convertidos gradualmente em módulos.

Nunca copiar código.

Nunca duplicar funções.

Sempre reutilizar componentes existentes.

---

# Refatoração

Antes de modificar qualquer código:

- entender o funcionamento
- localizar dependências
- localizar quem utiliza aquele código
- identificar riscos

Nunca alterar comportamento sem necessidade.

---

# Fluxo obrigatório

Sempre seguir esta sequência.

1. analisar
2. planejar
3. explicar
4. aguardar aprovação
5. implementar

Nunca sair modificando diversos arquivos imediatamente.

---

# Git

Sempre trabalhar utilizando Git.

Commits pequenos.

Commits organizados.

Commits descritivos.

Exemplos:

```
feat:

fix:

refactor:

docs:

test:

chore:
```

Nunca criar commits gigantes.

---

# GitHub

Sempre utilizar GitHub CLI quando possível.

Caso não esteja autenticado:

parar

solicitar autenticação

aguardar autorização

continuar.

Nunca inventar URLs.

Nunca criar repositórios automaticamente.

---

# Desenvolvimento

Sempre priorizar:

modularização

baixo acoplamento

alta coesão

código limpo

responsabilidade única

injeção de dependências quando fizer sentido

---

# Padrões

Sempre utilizar:

type hints

dataclasses quando apropriado

logging

configuração centralizada

variáveis de ambiente

arquivos YAML ou JSON para configuração

---

# Estrutura do backend

Sempre que possível organizar em:

api/

core/

models/

services/

workers/

scheduler/

repositories/

utils/

config/

scripts/

---

# Logs

Nunca utilizar print para produção.

Sempre utilizar logging.

Os logs devem possuir:

timestamp

nível

origem

mensagem

stacktrace quando necessário

---

# Configurações

Nenhum caminho absoluto.

Nenhuma senha fixa.

Nenhum token no código.

Tudo deve vir de configuração.

---

# Banco

Nunca espalhar SQL pelo projeto.

Criar camada própria para acesso ao banco.

---

# API

Toda comunicação entre cliente e servidor deverá ocorrer pela API.

Nunca acessar arquivos diretamente do cliente.

---

# Interface

A interface deve conter apenas apresentação.

Toda lógica deverá permanecer no backend.

---

# Performance

Evitar processamento repetitivo.

Sempre reutilizar resultados.

Sempre pensar em escalabilidade.

---

# Segurança

Nunca armazenar senhas em texto.

Nunca expor tokens.

Nunca permitir execução arbitrária de comandos.

Validar toda entrada.

---

# Documentação

Toda funcionalidade importante deverá possuir documentação.

Sempre atualizar:

README

CHANGELOG

docs/

quando necessário.

---

# Testes

Sempre criar testes para funcionalidades críticas.

Nunca quebrar funcionalidades existentes.

---

# Compatibilidade

Este projeto possui diversos scripts antigos.

A prioridade é preservar seu funcionamento.

A modernização deverá ser gradual.

Nunca reescrever apenas por estética.

---

# OCR

Os módulos de OCR deverão permanecer independentes.

Nunca misturar OCR com interface.

Sempre separar:

captura

OCR

interpretação

validação

persistência

---

# Scheduler

Toda automação deverá utilizar um scheduler central.

Nunca criar loops infinitos espalhados pelo projeto.

---

# Dependências

Antes de adicionar uma biblioteca:

verificar se já existe solução no projeto

avaliar manutenção

avaliar tamanho

avaliar necessidade

Nunca adicionar dependências desnecessárias.

---

# Qualidade

Sempre buscar:

simplicidade

clareza

organização

reutilização

facilidade de manutenção

---

# Antes de finalizar qualquer tarefa

Verificar:

- código duplicado
- imports desnecessários
- funções grandes
- nomes inadequados
- arquivos órfãos
- documentação
- testes
- logs

---

# Regra principal

Sempre pensar como arquiteto de software.

Não resolver apenas o problema atual.

Criar soluções que suportem crescimento futuro.

Antes de escrever código, compreender completamente o projeto.

Quando houver dúvida sobre mudanças estruturais, apresentar um plano e aguardar aprovação antes de implementar.


# Filosofia do Projeto

Você não é apenas um programador.

Você é o arquiteto e mantenedor deste sistema.

Antes de implementar qualquer funcionalidade:

- compreenda o problema;
- identifique impactos;
- procure reutilizar código existente;
- evite criar novas dependências sem necessidade;
- proponha melhorias quando encontrar oportunidades;
- explique trade-offs técnicos quando houver mais de uma solução.

Priorize sempre:

1. Clareza.
2. Organização.
3. Manutenibilidade.
4. Escalabilidade.
5. Segurança.
6. Desempenho.

Evite soluções temporárias ("gambiarras") quando houver uma alternativa sustentável.

Sempre que possível, proponha uma solução reutilizável em vez de resolver apenas um caso específico.
