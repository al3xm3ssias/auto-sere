# Instalação e configuração de rede — Auto-SERE

Este documento descreve como configurar o compartilhamento de arquivos
entre os computadores da escola, e como cada máquina deve apontar o
Auto-SERE para esses arquivos.

## Visão geral

Os dados do sistema (documentos de alunos, digitalizações, planilhas,
JSONs de estado etc.) moram fisicamente em **um único PC da rede**,
chamado aqui de **PC servidor**. Os demais computadores (**PCs clientes**)
acessam esses arquivos pela rede local, via compartilhamento SMB nativo
do Windows.

```
PC SERVIDOR (guarda os arquivos de verdade)
  D:\ESCOLA JUDITH\...
  └── compartilhado na rede como \\NOME-DO-SERVIDOR\ESCOLA JUDITH

PC CLIENTE Windows #1  → mapeia \\NOME-DO-SERVIDOR\ESCOLA JUDITH como (ex.) M:\
PC CLIENTE Windows #2  → mapeia \\NOME-DO-SERVIDOR\ESCOLA JUDITH como (ex.) D:\
PC/WSL Linux (Ubuntu)  → monta \\NOME-DO-SERVIDOR\ESCOLA JUDITH via CIFS
```

O Auto-SERE nunca usa um caminho fixo (nem `D:\`, nem `/mnt/...`) dentro
do código. Cada máquina informa, uma única vez, **onde ela enxerga essa
pasta compartilhada**, através da variável de ambiente
`AUTOSERE_DATA_DIR`. O restante do sistema deriva todos os caminhos a
partir dela (ver `backend/core/config.py`).

---

## 1. PC servidor — compartilhar a pasta (Windows nativo)

No computador que fisicamente guarda `D:\ESCOLA JUDITH`:

1. Abra o Explorador de Arquivos e localize a pasta `ESCOLA JUDITH`.
2. Clique com o botão direito → **Propriedades** → aba **Compartilhamento**.
3. Clique em **Compartilhamento Avançado** → marque **Compartilhar esta pasta**.
4. Em **Permissões**, garanta que os usuários da rede tenham permissão de
   **Leitura e Gravação** (conforme necessário).
5. Anote o **nome do compartilhamento** (ex.: `ESCOLA JUDITH`) e o **nome
   do computador** na rede (Configurações → Sistema → Sobre, campo "Nome
   do dispositivo").
6. Confirme que o **Firewall do Windows** permite Compartilhamento de
   Arquivos e Impressoras na rede local.

O caminho de rede final será algo como:
```
\\NOME-DO-SERVIDOR\ESCOLA JUDITH
```

> Recomendação: configure o PC servidor para nunca entrar em suspensão/
> hibernação enquanto estiver atuando como servidor, já que os demais PCs
> dependem dele estar ligado e acessível.

---

## 2. PC cliente Windows — mapear a unidade de rede

1. Abra o Explorador de Arquivos → **Este Computador** → **Mapear
   unidade de rede**.
2. Escolha uma letra livre (ex.: `M:`).
3. No campo pasta, informe `\\NOME-DO-SERVIDOR\ESCOLA JUDITH`.
4. Marque **Reconectar-se ao entrar na sessão**.
5. Informe usuário/senha da rede, se solicitado.

Depois de mapeado, configure a variável de ambiente nesse PC (ver
seção 4) apontando para essa letra, ex.: `AUTOSERE_DATA_DIR=M:\`.

---

## 3. PC/WSL Linux (Ubuntu) — montar via CIFS

No seu ambiente atual (Ubuntu/WSL), monte o compartilhamento SMB do
Windows usando `cifs-utils`:

```bash
sudo apt install cifs-utils

sudo mkdir -p /mnt/escola-judith

sudo mount -t cifs "//NOME-DO-SERVIDOR/ESCOLA JUDITH" /mnt/escola-judith \
  -o username=SEU_USUARIO,uid=$(id -u),gid=$(id -g)
```

Para montar automaticamente sempre que o sistema iniciar, adicione uma
entrada em `/etc/fstab` (ajuste usuário/senha e considere usar um
arquivo de credenciais separado, com permissão restrita, em vez de
senha em texto no fstab):

```
//NOME-DO-SERVIDOR/ESCOLA JUDITH  /mnt/escola-judith  cifs  credentials=/etc/samba/credenciais-escola,uid=1000,gid=1000  0  0
```

Depois de montado, configure `AUTOSERE_DATA_DIR=/mnt/escola-judith`.

> Nota: isso substitui o modelo anterior (Samba **rodando dentro do
> WSL**). Com o compartilhamento nativo do Windows, o WSL passa a ser
> apenas mais um **cliente** da rede, não mais precisa hospedar o
> servidor Samba — o que reduz a dependência do WSL estar ativo para o
> compartilhamento funcionar.

---

## 4. Configurar `AUTOSERE_DATA_DIR` em cada máquina

Crie um arquivo `.env` na raiz do projeto (nunca versionado no Git —
já está no `.gitignore`), com o caminho que **aquela máquina específica**
usa para enxergar a pasta compartilhada:

```env
# PC servidor ou cliente Windows (unidade M:)
AUTOSERE_DATA_DIR=M:\ESCOLA JUDITH

# PC cliente Windows (unidade D:)
AUTOSERE_DATA_DIR=D:\ESCOLA JUDITH

# Ubuntu/WSL com CIFS montado
AUTOSERE_DATA_DIR=/mnt/escola-judith
```

O restante do sistema (backend, scripts migrados) lê essa variável uma
única vez, em `backend/core/config.py`, e todos os caminhos internos
(digitalização, transferências, pareceres, dados de alunos etc.) são
derivados dela. Nenhum módulo deve declarar um caminho absoluto próprio.

---

## Status desta migração

- [x] Decisão de infraestrutura: Samba nativo do Windows no PC servidor.
- [ ] Compartilhamento configurado no PC servidor.
- [ ] `AUTOSERE_DATA_DIR` configurado em cada PC cliente.
- [ ] `backend/core/config.py` com `PATHS` implementado.
