# Seniors – Empregabilidade Backend

Backend FastAPI do projeto Seniors – Empregabilidade, desenvolvido pela equipe da AGES. O código-fonte, os contratos da API, os identificadores do banco de dados e os arquivos de configuração permanecem em inglês.

Este repositório contém somente a base técnica inicial. Entidades, módulos de negócio, autenticação, autorização, auditoria e armazenamento de arquivos serão adicionados apenas depois que seus requisitos forem confirmados.

## Tecnologias

- CPython 3.14
- FastAPI e Uvicorn
- PostgreSQL 18.4 em Docker Compose
- SQLAlchemy 2 com o driver síncrono Psycopg 3
- Migrações com Alembic
- Pydantic Settings
- uv para gerenciar Python e dependências
- pytest, Ruff, mypy e pre-commit

## Pré-requisitos

- uv 0.11.33
- Docker com o plugin Compose
- Portas `5432` e `8000` disponíveis localmente

Python não possui uma classificação oficial de LTS. O repositório fixa a linha atual do Python 3.14 em `.python-version` e restringe o projeto ao Python 3.14.x.

## Execução local

```bash
uv sync --frozen
cp .env.example .env
docker compose up -d postgres
uv run alembic upgrade head
uv run pre-commit install --install-hooks
uv run uvicorn app.main:app --reload --no-access-log
```

No PowerShell, copie o arquivo de ambiente com:

```powershell
Copy-Item .env.example .env
```

A API estará disponível em `http://localhost:8000`. Endpoints técnicos úteis:

- `GET /health`: verifica se o processo está vivo sem consultar o PostgreSQL;
- `GET /ready`: executa `SELECT 1` no PostgreSQL para verificar prontidão;
- `GET /docs`: documentação OpenAPI interativa;
- `GET /openapi.json`: documento OpenAPI.

A futura API do produto está reservada em `/api/v1`. Ainda não existem rotas de produto.

## Comandos

| Comando                                                  | Finalidade                                      |
| -------------------------------------------------------- | ----------------------------------------------- |
| `docker compose up -d postgres`                          | Inicia o PostgreSQL local                       |
| `docker compose stop postgres`                           | Para o PostgreSQL sem apagar os dados           |
| `uv run uvicorn app.main:app --reload --no-access-log`   | Inicia a API localmente                         |
| `uv run ruff format .`                                   | Formata os arquivos Python                      |
| `uv run ruff format --check .`                           | Verifica a formatação                           |
| `uv run ruff check .`                                    | Executa as regras de lint                       |
| `uv run mypy`                                            | Executa a verificação estrita de tipos          |
| `uv run pytest`                                          | Executa os testes e exige 80% de cobertura      |
| `uv run python scripts/validate.py`                      | Executa todos os controles de qualidade         |
| `uv run alembic upgrade head`                            | Aplica todas as migrações do banco              |

Para remover o banco local e todos os seus dados, execute `docker compose down --volumes`. Esse comando é destrutivo e deve ser usado somente quando os dados locais não forem mais necessários.

## Configuração

O Pydantic valida as variáveis de ambiente e, opcionalmente, um arquivo `.env` local não versionado.

| Variável       | Padrão                    | Finalidade                                                   |
| -------------- | ------------------------- | ------------------------------------------------------------ |
| `APP_ENV`      | `local`                   | Ambiente: `local`, `test`, `staging` ou `production`         |
| `DATABASE_URL` | Banco do Compose local    | URL SQLAlchemy com `postgresql+psycopg`                      |
| `LOG_LEVEL`    | `INFO`                    | Nível de log do Python                                       |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Lista JSON de origens permitidas para o frontend          |

Nunca versione credenciais ou configurações de produção. Os valores de `.env.example` servem apenas para o desenvolvimento local.

## Banco de dados e migrações

O Compose gerencia o PostgreSQL local e persiste os dados da versão 18 em `/var/lib/postgresql`, caminho oficial da imagem para a versão 18 ou superior.

`alembic/versions` está intencionalmente vazio. Não crie migrações vazias ou fictícias. Depois que os modelos forem confirmados, importe os metadados compartilhados do SQLAlchemy em `alembic/env.py`, gere a revisão, inspecione todas as operações e teste tanto o upgrade quanto o downgrade.

## Estrutura técnica

O repositório segue um monólito modular, mas atualmente define somente fronteiras técnicas:

```text
.
├── .github/              # CI, Dependabot, CODEOWNERS e orientação para PRs
├── alembic/              # Ambiente de migrações; ainda sem revisões
├── app/                  # Somente código entregue na aplicação
│   ├── api/              # Composição das rotas em /api/v1
│   ├── core/             # Configuração, erros, logging e middleware
│   ├── db/               # Engine e sessões do SQLAlchemy
│   ├── health/           # Endpoints de liveness e readiness do PostgreSQL
│   └── main.py           # Composição da aplicação FastAPI
├── docs/                 # Arquitetura, ADRs e políticas de engenharia
├── scripts/              # Pontos de entrada para validação do repositório
├── tests/                # Testes técnicos unitários e de integração PostgreSQL
├── alembic.ini           # Configuração do Alembic
├── compose.yaml          # Serviço PostgreSQL para desenvolvimento local
├── pyproject.toml        # Projeto, dependências e configuração das ferramentas
└── uv.lock               # Lockfile reproduzível das dependências
```

Nenhum módulo de domínio está implícito nessa estrutura. Depois que entidades e fluxos forem confirmados, adicione módulos coesos em `app/` com base em capacidades reais do produto. Um módulo poderá ser responsável por suas próprias rotas, schemas, models e casos de uso; não crie pastas globais como `models`, `schemas`, `services` ou `repositories` antecipadamente apenas para preencher um modelo arquitetural.

Mantenha infraestrutura transversal em `app/core` ou `app/db` somente quando ela for realmente compartilhada. Documente em ADR uma fronteira de domínio duradoura ou uma decisão importante de direção de dependências antes que ela vire convenção para o time.

## Erros e logging

Os erros seguem RFC 9457 com o tipo `application/problem+json`, um `code` estável em inglês e um identificador da requisição. Erros inesperados retornam detalhes seguros e nunca expõem mensagens privadas da implementação.

A API escreve na saída padrão um evento compacto por requisição, contendo horário UTC, método, template da rota, status, duração e identificador da requisição. As sondas de saúde são omitidas para reduzir ruído. Corpos de requisição, query strings, credenciais, dados pessoais, currículos e certificados nunca devem ser registrados nos logs.

## Contribuição

Antes de contribuir, leia [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md) e [docs/AI_USAGE.md](docs/AI_USAGE.md). O contexto arquitetural está em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), e as decisões aceitas ficam em [docs/adr](docs/adr).
