# Meu Projeto

## O que você precisa ter instalado

- [Python 3.11 ou mais novo](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine no Linux)

Para conferir, rode no terminal:

```bash
python --version
git --version
docker --version
```

## Como rodar

### 1. Baixe o projeto

```bash
git clone https://github.com/SEU-USUARIO/meu-projeto.git
cd meu-projeto
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv .venv
```

Ative:

```bash
# Linux ou Mac
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Quando der certo, aparece `(.venv)` no início da linha do terminal.

> Toda vez que abrir um terminal novo para trabalhar no projeto, ative o ambiente de novo.

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Crie seu arquivo de configuração

Copie o modelo:

```bash
# Linux ou Mac
cp .env.example .env

# Windows (PowerShell)
copy .env.example .env
```

Depois abra o `.env` e ajuste os valores se precisar. Para rodar com o banco do Docker deste projeto, use:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
```

### 5. Ligue o banco de dados

Abra o Docker Desktop e rode:

```bash
docker compose up -d db
```

Confira se subiu:

```bash
docker compose ps
```

O serviço `db` deve aparecer como `running` (ou `Up`).

### 6. Inicie a API

```bash
uvicorn app.main:app --reload
```

## Como saber se deu certo

Abra no navegador:

- http://localhost:8000/health deve mostrar `{"status":"ok"}`
- http://localhost:8000/health/db deve mostrar `{"database":"ok"}`
- http://localhost:8000/docs mostra a documentação interativa da API

## Comandos úteis

```bash
docker compose stop         # desliga o banco (os dados continuam salvos)
docker compose up -d db     # liga o banco de novo
docker compose down -v      # apaga o banco E todos os dados (cuidado)
```

Para parar a API, use `Ctrl + C` no terminal onde ela está rodando.

```

## Problemas comuns

**`ModuleNotFoundError` ao iniciar a API**
O ambiente virtual não está ativo, ou as dependências não foram instaladas. Ative o `.venv` e rode `pip install -r requirements.txt`.

**`Connection refused` ou erro em `/health/db`**
O banco está desligado. Abra o Docker Desktop e rode `docker compose up -d db`.

**Porta 5432 já em uso**
Você tem outro PostgreSQL rodando no computador. Desligue-o ou mude a porta no `docker-compose.yml` (por exemplo, `"5433:5432"`) e ajuste a porta no `.env`.

**Porta 8000 já em uso**
Rode em outra porta: `uvicorn app.main:app --reload --port 8001`.

**`Field required` ao iniciar**
O arquivo `.env` não existe ou está no lugar errado. Ele precisa estar na raiz do projeto, e a API deve ser iniciada a partir dessa pasta.
