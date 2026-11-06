# Meu Projeto

API de restaurante (FastAPI + PostgreSQL) consumida por aplicações web. Usuários podem ser **gerente**, **garçom** ou **cozinha**.

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

Gere uma chave secreta (obrigatória; a API não sobe com a chave de exemplo):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Abra o `.env`, cole o resultado em `SECRET_KEY=` e confira o banco:

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

### 6. Crie as tabelas

```bash
alembic upgrade head
```

### 7. Crie o primeiro gerente

Não existe cadastro público. O primeiro gerente é criado por script, e ele cadastra os demais pela API:

```bash
python -m scripts.create_manager "Seu Nome" voce@restaurante.com
```

### 8. Inicie a API

```bash
uvicorn app.main:app --reload
```

## Como saber se deu certo

Abra no navegador:

- http://localhost:8000/health deve mostrar `{"status":"ok"}`
- http://localhost:8000/health/db deve mostrar `{"database":"ok"}`
- http://localhost:8000/docs mostra a documentação interativa da API (somente com `ENVIRONMENT=dev`)

## Comandos úteis

```bash
docker compose stop         # desliga o banco (os dados continuam salvos)
docker compose up -d db     # liga o banco de novo
docker compose down -v      # apaga o banco E todos os dados (cuidado)
pytest                      # roda os testes
alembic revision --autogenerate -m "descrição"   # gera nova migration após mudar models
```

Para parar a API, use `Ctrl + C` no terminal onde ela está rodando.

## Configuração (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `ENVIRONMENT` | `dev` | `prod` desliga `/docs`, `/redoc` e `/openapi.json` |
| `DATABASE_URL` | , | Conexão com o PostgreSQL (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | , | **Obrigatória**, mínimo 32 caracteres. Assina os JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Vida do access token |
| `REFRESH_TOKEN_EXPIRE_HOURS` | `12` | Janela deslizante da sessão (cobre um turno) |
| `REFRESH_ABSOLUTE_LIFETIME_DAYS` | `7` | Depois disso, login obrigatório |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | `5` / `15` | Bloqueio da conta após senhas erradas |
| `LOGIN_RATE_LIMIT` | `10/minute` | Limite por IP no login |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Em produção com vários workers, use Redis (`redis://...`) |
| `CORS_ORIGINS` | `[]` | Lista JSON de origens permitidas (nunca `*`) |
| `ALLOWED_HOSTS` | `["localhost","127.0.0.1"]` | Lista JSON de hosts aceitos |

## Autenticação

### Papéis

| Papel | Valor | Pode |
|---|---|---|
| Gerente | `manager` | Tudo, inclusive gerenciar usuários |
| Garçom | `waiter` | Rotas liberadas para garçom (a definir nas rotas de domínio) |
| Cozinha | `kitchen` | Rotas liberadas para cozinha (a definir nas rotas de domínio) |

### Como funciona a sessão

1. `POST /auth/login` devolve um **access token** (JWT, 15 min) e um **refresh token** (opaco, 12 h).
2. O access token vai em toda requisição: `Authorization: Bearer <access_token>`.
3. Quando o access token expira (ou está perto), o front chama `POST /auth/refresh` com o refresh token e recebe **um novo par**. O refresh token antigo deixa de valer (rotação).
4. Enquanto o usuário trabalha, a sessão se renova sozinha por até 7 dias. Parado por mais de 12 h, precisa logar de novo.

### Regras para quem consome a API (front-ends)

- **Renove com uma única chamada por vez** (single-flight). Se várias requisições recebem 401 ao mesmo tempo, só uma chama `/auth/refresh`; as outras esperam e reaproveitam o resultado.
- **Sempre troque o refresh token guardado** pelo novo que vier na resposta. Reapresentar um token antigo é tratado como roubo e **encerra a sessão inteira**.
- Se `/auth/refresh` responder 401, a sessão acabou: mande o usuário para a tela de login.
- Não registre tokens em logs. Em apps web, prefira guardar o refresh token fora do alcance de scripts de terceiros (por exemplo, num backend-for-frontend com cookie `HttpOnly`).
- Erros 429 trazem o header `Retry-After`.

### Proteções ativas

- Senhas com Argon2. Login com mensagem genérica (não revela se o e-mail existe).
- Bloqueio da conta por 15 min após 5 senhas erradas, mais limite de requisições por IP.
- O **papel e o status vêm sempre do banco**, nunca do token: desativar ou rebaixar alguém vale na hora.
- Trocar senha, papel ou desativar um usuário derruba todas as sessões dele.
- Ações sensíveis ficam registradas na tabela `audit_logs`.

## Endpoints

Prefixo de tudo abaixo: `/api/v1`. 🔓 = pública, 🔑 = exige access token, 👔 = exige gerente.

### Auth

#### 🔓 `POST /auth/login`
Corpo em **form-data** (`application/x-www-form-urlencoded`). O campo `username` recebe o **e-mail**.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=voce@restaurante.com&password=SUA_SENHA"
```

Resposta `200`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "k3J...",
  "token_type": "bearer",
  "expires_in": 900
}
```
Erros: `401` e-mail/senha incorretos (também para conta bloqueada ou inativa), `422` corpo inválido, `429` muitas tentativas.

#### 🔓 `POST /auth/refresh`
```json
{ "refresh_token": "k3J..." }
```
Resposta `200`: mesmo formato do login, com **novo par** de tokens.
Erros: `401` sessão expirada, revogada ou token já usado; `429` limite excedido.

#### 🔓 `POST /auth/logout`
Encerra a sessão do dispositivo. Sempre responde `204` (mesmo se o token já era inválido).
```json
{ "refresh_token": "k3J..." }
```

#### 🔑 `POST /auth/logout-all`
Encerra **todas** as sessões do usuário, em todos os dispositivos. Resposta `204`.

#### 🔑 `POST /auth/change-password`
```json
{ "current_password": "senha-atual", "new_password": "nova-senha-longa" }
```
Resposta `204`. Todas as sessões são encerradas; faça login de novo. Erros: `400` senha atual incorreta, `422` nova senha fraca ou igual à atual.

#### 🔑 `GET /auth/me`
Resposta `200`:
```json
{
  "id": "0b5f...",
  "name": "Maria",
  "email": "maria@restaurante.com",
  "role": "waiter",
  "is_active": true,
  "created_at": "2026-10-29T12:00:00Z"
}
```

### Usuários (somente gerente)

#### 👔 `POST /users`
```json
{
  "name": "João",
  "email": "joao@restaurante.com",
  "password": "senha-longa-123",
  "role": "kitchen"
}
```
`role`: `waiter`, `manager` ou `kitchen`. Resposta `201` (objeto de usuário). Erros: `409` e-mail já cadastrado, `403` não é gerente.

#### 👔 `GET /users?limit=50&offset=0`
Lista paginada (`limit` de 1 a 100). Resposta `200`: lista de usuários.

#### 👔 `GET /users/{user_id}`
Resposta `200` ou `404`.

#### 👔 `PATCH /users/{user_id}`
Envie só o que quer mudar. Campos aceitos: `name`, `role`, `is_active`. Qualquer outro campo é rejeitado com `422`.
```json
{ "role": "waiter", "is_active": false }
```
Regras:
- Não é possível alterar o próprio papel ou status (`400`).
- Não é possível deixar o sistema sem gerente ativo (`409`).
- Mudar papel ou status encerra todas as sessões do usuário afetado.

### Códigos de erro comuns

| Código | Significado |
|---|---|
| `401` | Token ausente, inválido ou expirado. Tente `/auth/refresh` |
| `403` | Autenticado, mas sem permissão para a ação |
| `404` | Recurso não encontrado |
| `409` | Conflito (e-mail duplicado, último gerente) |
| `422` | Corpo da requisição inválido |
| `429` | Muitas requisições |

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

**`SECRET_KEY fraca` ao iniciar**
Gere uma chave com o comando do passo 4 e cole no `.env`.

**`relation "users" does not exist`**
Faltou rodar `alembic upgrade head`.

## Produção: checklist

- `ENVIRONMENT=prod`, `SECRET_KEY` forte vinda do gerenciador de segredos, `CORS_ORIGINS` e `ALLOWED_HOSTS` com os domínios reais.
- API atrás de proxy reverso com HTTPS e HSTS. Rode o uvicorn com `--proxy-headers --forwarded-allow-ips=<ip do proxy>` para o rate limit enxergar o IP real.
- Mais de um worker: configure `RATE_LIMIT_STORAGE_URI` com Redis.
- Não exponha a porta 5432 do Postgres. Use um usuário de banco sem superuser para a aplicação.
- Agende a limpeza periódica de `refresh_tokens` expirados e revogados.
