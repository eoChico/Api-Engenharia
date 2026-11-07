# Projeto Restaurante

API de restaurante (FastAPI + PostgreSQL) consumida por aplicações web. Os usuários têm um destes papéis: **gerente**, **garçom**, **cozinha** ou **caixa**.

## Sumário

- [O que você precisa ter instalado](#o-que-você-precisa-ter-instalado)
- [Como rodar](#como-rodar)
- [Como saber se deu certo](#como-saber-se-deu-certo)
- [Comandos úteis](#comandos-úteis)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Configuração (`.env`)](#configuração-env)
- [Autenticação](#autenticação)
- [Endpoints](#endpoints)
- [Cliente de demonstração](#cliente-de-demonstração)
- [Como criar um novo endpoint](#como-criar-um-novo-endpoint)
- [Problemas comuns](#problemas-comuns)
- [Produção: checklist](#produção-checklist)

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
.\.venv\Scripts\Activate.ps1
```

Quando der certo, aparece `(.venv)` no início da linha do terminal.

> Toda vez que abrir um terminal novo para trabalhar no projeto, ative o ambiente de novo, a partir da pasta do projeto.

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

Não existe cadastro público. O primeiro gerente é criado por script, e ele cadastra os demais usuários pela API:

```bash
python -m scripts.create_manager "Seu Nome" voce@restaurante.com
```

O script pede a senha duas vezes (mínimo de 10 caracteres).

### 8. Inicie a API

```bash
uvicorn app.main:app --reload
```

## Como saber se deu certo

Abra no navegador:

- http://localhost:8000/health deve mostrar `{"status":"ok"}`
- http://localhost:8000/health/db deve mostrar `{"database":"ok"}`
- http://localhost:8000/docs mostra a documentação interativa da API (somente com `ENVIRONMENT=dev`)

Para testar o fluxo completo pelo `/docs`:

1. Clique em **Authorize**, preencha `username` com o **e-mail** do gerente e `password` com a senha. Deixe `client_id` e `client_secret` vazios.
2. `GET /api/v1/auth/me` deve devolver `200` com `"role": "manager"`.
3. `POST /api/v1/users` para criar um garçom. Deve devolver `201`.
4. Faça logout no Authorize, entre como o garçom e chame `GET /api/v1/users`. Deve devolver `403`.

## Comandos úteis

```bash
docker compose stop         # desliga o banco (os dados continuam salvos)
docker compose up -d db     # liga o banco de novo
docker compose down -v      # apaga o banco E todos os dados (cuidado)
pytest                      # roda os testes
alembic upgrade head        # aplica as migrations pendentes
alembic current             # mostra a migration aplicada
alembic heads               # mais de uma linha = conflito de migrations
alembic revision --autogenerate -m "descrição"   # gera nova migration após mudar models
```

Para ver as tabelas pelo terminal:

```bash
docker compose exec db psql -U postgres -d app
```

Dentro do `psql`: `\dt` lista as tabelas, `\d users` mostra a estrutura de uma tabela e `\q` sai.

Para parar a API, use `Ctrl + C` no terminal onde ela está rodando.

## Estrutura do projeto

```
app/
├── api/
│   ├── deps.py              # autenticação, papéis e sessão do banco
│   └── routes/              # endpoints: health, auth, users, tables
├── core/                    # config, segurança (JWT, hash), middleware, rate limit
├── db/                      # base declarativa e sessão do banco
├── models/                  # tabelas (SQLAlchemy)
├── schemas/                 # entrada e saída da API (Pydantic)
├── services/                # regra de negócio e acesso ao banco
└── main.py                  # criação do app, middlewares e registro das rotas
alembic/versions/            # migrations
scripts/create_manager.py    # cria o primeiro gerente
tests/                       # testes automáticos
```

Cada requisição passa por: **rota** (valida quem pode chamar) → **service** (regra de negócio e banco) → **model** (tabela).

## Configuração (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `ENVIRONMENT` | `dev` | `prod` desliga `/docs`, `/redoc` e `/openapi.json` |
| `DATABASE_URL` | — | Conexão com o PostgreSQL (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | — | **Obrigatória**, mínimo 32 caracteres. Assina os JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Vida do access token |
| `REFRESH_TOKEN_EXPIRE_HOURS` | `12` | Janela deslizante da sessão (cobre um turno) |
| `REFRESH_ABSOLUTE_LIFETIME_DAYS` | `7` | Depois disso, login obrigatório |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | `5` / `15` | Bloqueio da conta após senhas erradas |
| `LOGIN_RATE_LIMIT` | `10/minute` | Limite de logins por IP |
| `REFRESH_RATE_LIMIT` | `30/minute` | Limite de refresh por IP |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Em produção com vários workers, use Redis (`redis://...`) |
| `CORS_ORIGINS` | `[]` | Lista JSON de origens permitidas (nunca `*`) |
| `ALLOWED_HOSTS` | `["localhost","127.0.0.1"]` | Lista JSON de hosts aceitos |

Depois de mudar o `.env`, reinicie a API.

## Autenticação

### Papéis

| Papel | Valor | O que pode |
|---|---|---|
| Gerente | `manager` | Tudo: gerencia usuários e mesas |
| Garçom | `waiter` | Consulta mesas ativas |
| Caixa | `cashier` | Consulta mesas ativas (pedidos e pagamentos a definir) |
| Cozinha | `kitchen` | Sem acesso a mesas (rotas de cozinha a definir) |

Só o gerente cria usuários e define papéis. Cada rota usa o **menor acesso possível**: se um papel não está listado numa rota, ele recebe `403`.

### Como funciona a sessão

1. `POST /auth/login` devolve um **access token** (JWT, 15 min) e um **refresh token** (opaco, 12 h).
2. O access token vai em toda requisição: `Authorization: Bearer <access_token>`.
3. Quando o access token expira, o front chama `POST /auth/refresh` com o refresh token e recebe **um novo par**. O refresh token antigo deixa de valer (rotação).
4. Enquanto o usuário trabalha, a sessão se renova sozinha por até 7 dias. Parado por mais de 12 h, precisa logar de novo.

### Regras para quem consome a API (front-ends)

- **Renove com uma única chamada por vez** (single-flight). Se várias requisições recebem 401 ao mesmo tempo, só uma chama `/auth/refresh`; as outras esperam e reaproveitam o resultado.
- **Sempre troque o refresh token guardado** pelo novo que vier na resposta. Reapresentar um token antigo é tratado como roubo e **encerra a sessão inteira**.
- Se `/auth/refresh` responder 401, a sessão acabou: mande o usuário para a tela de login.
- Não registre tokens em logs. Em apps web, prefira guardar o refresh token fora do alcance de scripts de terceiros (por exemplo, num backend-for-frontend com cookie `HttpOnly`).
- Erros 429 trazem o header `Retry-After`.
- O domínio do front precisa estar em `CORS_ORIGINS` (e em `ALLOWED_HOSTS` quando a API estiver publicada).

### Proteções ativas

- Senhas com Argon2. Login com mensagem genérica (não revela se o e-mail existe).
- Bloqueio da conta por 15 min após 5 senhas erradas, mais limite de requisições por IP.
- O **papel e o status vêm sempre do banco**, nunca do token: desativar ou rebaixar alguém vale na hora.
- Trocar senha, papel ou desativar um usuário derruba todas as sessões dele.
- Refresh tokens com rotação e detecção de reuso (reuso revoga a sessão inteira).
- Ações sensíveis ficam registradas na tabela `audit_logs`.
- Schemas de entrada rejeitam campos desconhecidos (`422`), evitando *mass assignment*.
- Headers de segurança, CORS restrito por origem e TrustedHost.

## Endpoints

Prefixo de tudo abaixo: `/api/v1` (exceto `/health`). 🔓 = pública, 🔑 = exige access token, 👔 = exige gerente.

### Saúde

| Método | Caminho | Acesso | Resposta |
|---|---|---|---|
| `GET` | `/health` | 🔓 | `{"status":"ok"}` |
| `GET` | `/health/db` | 🔓 | `{"database":"ok"}` |

### Auth

#### 🔓 `POST /auth/login`

Corpo em **form-data** (`application/x-www-form-urlencoded`). O campo `username` recebe o **e-mail**.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=voce@restaurante.com&password=SUA_SENHA"
```

No PowerShell, use `curl.exe` em vez de `curl`.

Resposta `200`:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "k3J...",
  "token_type": "bearer",
  "expires_in": 900
}
```

Erros: `401` e-mail ou senha incorretos (também para conta bloqueada ou inativa), `422` corpo inválido, `429` muitas tentativas.

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

Resposta `204`. Todas as sessões são encerradas; faça login de novo.
Erros: `400` senha atual incorreta, `422` nova senha fraca (mínimo 10 caracteres) ou igual à atual.

#### 🔑 `GET /auth/me`

Resposta `200`:

```json
{
  "id": "0b5f...",
  "name": "Maria",
  "email": "maria@restaurante.com",
  "role": "waiter",
  "is_active": true,
  "created_at": "2026-11-06T12:00:00Z"
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

`role`: `waiter`, `manager`, `kitchen` ou `cashier`. A senha tem no mínimo 10 caracteres.
Resposta `201` (objeto de usuário, sem a senha).
Erros: `409` e-mail já cadastrado, `403` não é gerente, `422` corpo inválido.

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

### Mesas

Gerente cria e edita. Gerente, garçom e caixa consultam. A cozinha não tem acesso. Mesas nunca são apagadas: são **desativadas** (`is_active: false`), para não quebrar o histórico quando existirem pedidos.

#### 👔 `POST /tables`

```json
{ "number": 1, "seats": 4 }
```

`number` de 1 a 9999 (único) e `seats` de 1 a 50. Resposta `201`:

```json
{ "id": "7c1e...", "number": 1, "seats": 4, "is_active": true }
```

Erros: `409` número já existe, `403` não é gerente, `422` corpo inválido.

#### 🔑 `GET /tables?limit=50&offset=0`

Lista paginada (`limit` de 1 a 100), ordenada por número. Garçom e caixa veem só mesas ativas. O gerente pode usar `include_inactive=true` para ver todas; os demais papéis recebem `403` se tentarem. Resposta `200`: lista de mesas.
Erros: `403` papel sem acesso (cozinha) ou uso de `include_inactive` sem ser gerente.

#### 🔑 `GET /tables/{table_id}`

Resposta `200` ou `404`. Para garçom e caixa, uma mesa inativa responde `404`, como se não existisse.

#### 👔 `PATCH /tables/{table_id}`

Envie só o que quer mudar: `number`, `seats`, `is_active`. Qualquer outro campo é rejeitado com `422`.

```json
{ "seats": 6, "is_active": false }
```

Erros: `404` mesa não encontrada, `409` número já existe, `403` não é gerente.

### Códigos de erro comuns

| Código | Significado |
|---|---|
| `400` | Regra de negócio violada (ex.: alterar o próprio papel) |
| `401` | Token ausente, inválido ou expirado. Tente `/auth/refresh` |
| `403` | Autenticado, mas sem permissão para a ação |
| `404` | Recurso não encontrado |
| `409` | Conflito (e-mail duplicado, número de mesa duplicado, último gerente) |
| `422` | Corpo da requisição inválido |
| `429` | Muitas requisições (veja o header `Retry-After`) |

## Cliente de demonstração

Existe um cliente web de exemplo (`api-eng-demo`) que consome a API como qualquer aplicação externa faria: login, refresh automático, criação de usuários (gerente) e lista de mesas (garçom, caixa e gerente). Ele fica em uma pasta **separada**, ao lado da `api-eng`, e roda em Docker na porta 3000.

```
projetos/
├── api-eng/          # a API (porta 8000)
└── api-eng-demo/     # o cliente (porta 3000)
```

Para rodar os dois ao mesmo tempo:

```bash
# Terminal 1: API
cd api-eng
docker compose up -d db
uvicorn app.main:app --reload

# Terminal 2: cliente
cd api-eng-demo
docker compose up --build
```

Abra http://localhost:3000 (use `localhost`, não `127.0.0.1`, porque o CORS compara a origem exata). O endereço da API fica em `api-eng-demo/public/config.js`.

Para o cliente funcionar:

- `http://localhost:3000` precisa estar em `CORS_ORIGINS` no `.env` da API, e a API deve ser reiniciada depois de mudar.
- Se alterar a porta do cliente, adicione a nova origem ao `CORS_ORIGINS`.

O botão **Simular access token expirado** mostra o refresh automático funcionando, que é o que evita deslogar o garçom no meio do turno. O cliente guarda os tokens em `sessionStorage` só por simplicidade; em um front real, prefira um backend-for-frontend com cookie `HttpOnly`.

## Como criar um novo endpoint

Todo recurso novo segue a mesma estrutura:

| O que | Onde |
|---|---|
| Tabela do banco | `app/models/<recurso>.py` (e registrar em `app/models/__init__.py`) |
| Migration | `alembic/versions/` (gerada com `alembic revision --autogenerate`) |
| Entrada e saída da API | `app/schemas/<recurso>.py` |
| Regra de negócio e banco | `app/services/<recurso>_service.py` |
| Rotas | `app/api/routes/<recurso>.py` |
| Registro da rota | `app/main.py` (`include_router(..., prefix="/api/v1")`) |
| Testes | `tests/test_<recurso>.py` |
| Documentação | esta seção **Endpoints** |

Regras que não mudam:

- Toda rota exige autenticação e o **menor papel possível** (`CurrentUser`, `ManagerUser` ou `require_roles(...)`).
- Schemas de entrada usam `extra="forbid"`, e schemas de criação, atualização e leitura são separados.
- Regra de negócio e acesso ao banco ficam no service; a rota só traduz erros em HTTP.
- Listagens têm paginação (`limit` máximo de 100).
- Onde houver dado por usuário, confira o dono do objeto e responda `404` (não `403`) se não for dele.
- Ações importantes registram `audit_service.record(...)`.
- Leia a migration gerada antes de aplicar, e nunca edite uma migration que já foi para a branch principal.
- Se mudar a lista de papéis (`UserRole`), a migration precisa ser **escrita à mão**: o autogenerate não detecta mudança na constraint `ck_users_user_role`.

O teste `tests/test_route_protection.py` falha se alguma rota ficar sem autenticação. Rotas públicas de propósito entram em `PUBLIC_PATHS`, com justificativa no PR.

Antes de abrir o PR: rode `pytest`, confirme que a API sobe e que o endpoint aparece no `/docs`, e atualize este README.

## Problemas comuns

**`ModuleNotFoundError` ao iniciar a API**
O ambiente virtual não está ativo, ou as dependências não foram instaladas. Ative o `.venv` e rode `pip install -r requirements.txt`.

**O PowerShell não ativa o `.venv`**
Rode a partir da pasta do projeto e use o caminho explícito: `.\.venv\Scripts\Activate.ps1`. Se aparecer "execução de scripts desabilitada", rode uma vez `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

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

**`Unauthorized` no botão Authorize do `/docs`**
O campo `username` precisa ser o **e-mail** completo do usuário. Se estiver certo, confira se a conta não está bloqueada:

```bash
docker compose exec db psql -U postgres -d app -c "SELECT email, role, is_active, locked_until FROM users;"
```

Para liberar uma conta bloqueada durante o desenvolvimento:

```bash
docker compose exec db psql -U postgres -d app -c "UPDATE users SET locked_until = NULL, failed_login_attempts = 0;"
```

**Erro de CORS no cliente (`blocked by CORS policy`)**
Confira que o `.env` da API tem a origem do cliente em `CORS_ORIGINS` (por exemplo, `["http://localhost:3000"]`) e reinicie a API.

**Migration gerada vazia**
O model não foi importado em `app/models/__init__.py`.

**`violates check constraint "ck_users_user_role"`**
Um papel novo foi usado sem migration que atualize a constraint. Veja a regra na seção "Como criar um novo endpoint".

**`alembic heads` mostra mais de uma linha**
Duas pessoas geraram migration ao mesmo tempo. Quem entrar por último roda `alembic merge heads -m "merge"`.

## Produção: checklist

- `ENVIRONMENT=prod`, `SECRET_KEY` forte vinda do gerenciador de segredos, `CORS_ORIGINS` e `ALLOWED_HOSTS` com os domínios reais.
- API atrás de proxy reverso com HTTPS e HSTS. Rode o uvicorn com `--proxy-headers --forwarded-allow-ips=<ip do proxy>` para o rate limit enxergar o IP real.
- Mais de um worker: configure `RATE_LIMIT_STORAGE_URI` com Redis.
- Não exponha a porta 5432 do Postgres. Use um usuário de banco sem superuser para a aplicação.
- Limite o tamanho do corpo das requisições no proxy reverso.
- Agende a limpeza periódica de `refresh_tokens` expirados e revogados.
- Rode `pip-audit` no CI para vigiar vulnerabilidades nas dependências.
