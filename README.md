# Seniors – Empregabilidade Backend

API do projeto Seniors – Empregabilidade, desenvolvida pela equipe da AGES com FastAPI. Ela recebe requisições do frontend e usa PostgreSQL como banco de dados local.

## O que já está implementado

O repositório contém a fundação técnica: configuração, conexão com PostgreSQL, tratamento de erros, logs, endpoints de monitoramento, documentação interativa e testes automatizados.

Ainda não existem entidades, tabelas, rotas de produto ou módulos de negócio. Autenticação, autorização, auditoria e armazenamento de arquivos também não foram definidos. A futura API do produto está reservada em `/api/v1`.

## Pré-requisitos

- [Git](https://git-scm.com/downloads), para baixar e versionar o projeto;
- [uv 0.11.33](https://docs.astral.sh/uv/getting-started/installation/), que gerencia o Python e as dependências;
- [Docker](https://docs.docker.com/get-started/get-docker/) com Docker Compose, para executar o PostgreSQL local;
- portas 5432 e 8000 livres.

O projeto usa Python 3.14. O `uv` prepara o ambiente Python e instala as versões registradas no lockfile. Como todos os comandos Python usam `uv run`, você não precisa criar ou ativar um ambiente virtual manualmente.

Antes de usar `docker compose`, o Docker deve estar em execução. No Windows e no macOS, abra o Docker Desktop e aguarde o mecanismo iniciar. No Linux, confirme que o serviço do Docker está ativo conforme a [documentação oficial](https://docs.docker.com/engine/install/).

## Escolha do terminal

Os comandos `git`, `uv` e `docker compose` são iguais no Windows PowerShell, Windows com WSL, Linux e macOS. Blocos marcados como **Bash** funcionam no Linux, macOS e WSL. Use blocos **PowerShell** no PowerShell do Windows.

WSL é um ambiente Linux dentro do Windows. Escolha um ambiente e mantenha o repositório e os comandos nele: caminhos como `C:\Users\...` pertencem ao PowerShell, enquanto `/home/...` pertence ao WSL. Se usar Docker Desktop com WSL, habilite a integração da distribuição nas configurações do Docker.

## Primeira configuração

Execute uma vez:

```bash
git clone https://github.com/seniors-empregabilidade/seniors-empregabilidade-backend.git
cd seniors-empregabilidade-backend
uv sync --frozen
uv run pre-commit install --install-hooks
```

`uv sync --frozen` reproduz o ambiente descrito no lockfile. O último comando instala os hooks para quem contribuirá com código ou documentação; ele não é necessário toda vez que a API iniciar. Hooks são verificações automáticas executadas durante commits e pushes.

## Inicialização diária

Com o Docker em execução, abra um terminal na raiz do repositório e inicie o PostgreSQL:

```bash
docker compose up -d postgres
```

Depois, inicie a API:

```bash
uv run uvicorn app.main:app --reload --no-access-log
```

O terminal da API permanece ocupado enquanto o servidor está ativo. A opção `--reload` reinicia o servidor automaticamente após alterações no código.

## Como verificar se funcionou

Com a API e o PostgreSQL ativos, abra:

- [http://localhost:8000/health](http://localhost:8000/health): confirma que o processo da API está vivo; deve retornar `{"status":"ok"}`;
- [http://localhost:8000/ready](http://localhost:8000/ready): confirma que a API também consegue acessar o PostgreSQL; deve retornar `{"status":"ok"}`;
- [http://localhost:8000/docs](http://localhost:8000/docs): interface no navegador para conhecer e testar os endpoints.

Em termos operacionais, `/health` é a verificação de vida (*liveness*) e `/ready` é a verificação de prontidão (*readiness*). Se `/health` funcionar e `/ready` falhar, a API iniciou, mas o banco provavelmente não está disponível.

## Como parar

No terminal da API, pressione `Ctrl+C`. Depois, pare o PostgreSQL sem apagar os dados:

```bash
docker compose stop postgres
```

Para remover os contêineres, a rede e **todos os dados locais do banco**, use `docker compose down --volumes`. Esse comando é destrutivo e só deve ser executado quando esses dados não forem mais necessários.

## Variáveis de ambiente (opcional)

O projeto já possui padrões seguros para desenvolvimento local, então não é necessário criar `.env` no primeiro uso. Para personalizar a configuração, copie o exemplo uma vez:

**Bash (Linux, macOS ou WSL):**

```bash
cp .env.example .env
```

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `APP_ENV` | `local` | Nome do ambiente atual |
| `DATABASE_URL` | PostgreSQL local do Compose | Endereço de conexão com o banco |
| `LOG_LEVEL` | `INFO` | Quantidade de detalhes nos logs |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Endereços de frontend autorizados no navegador |

Nunca versione credenciais ou configurações de produção. Reinicie a API após alterar `.env`.

## Migrações

Migrações são alterações versionadas na estrutura do banco. Ainda não existem migrações de produto, portanto o primeiro uso não exige um comando adicional. Quando revisões forem adicionadas em `alembic/versions`, inicie o PostgreSQL e aplique-as com:

```bash
uv run alembic upgrade head
```

Não crie migrações vazias. Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [CONTRIBUTING.md](CONTRIBUTING.md) antes de trabalhar no banco.

## Principais comandos de qualidade

| Comando | O que verifica |
| --- | --- |
| `uv run ruff format --check .` | Formatação Python |
| `uv run ruff check .` | Lint: erros e padrões indesejados |
| `uv run mypy` | Coerência dos tipos Python |
| `uv run pytest` | Testes e cobertura mínima de 80% |
| `uv run python scripts/validate.py` | Todas as verificações locais acima |

Os hooks de pre-commit podem formatar arquivos e verificar tipos antes do commit. O pre-push pode demorar porque repete toda a validação antes de enviar mudanças. Eles existem para detectar problemas antes da revisão e da CI. Se não foram instalados, execute uma vez `uv run pre-commit install --install-hooks`; não use `--no-verify`.

## Problemas comuns

- **`uv`: command not found:** instale o uv pela documentação oficial, abra um terminal novo e confirme com `uv --version`.
- **`docker`: command not found:** instale o Docker pelo link oficial e abra um terminal novo. `docker compose version` deve reconhecer o plugin Compose.
- **Docker não está em execução:** abra o Docker Desktop ou inicie o serviço do Docker no Linux; aguarde e tente `docker compose up -d postgres` novamente.
- **Porta 5432 em uso:** pare outra instalação ou outro contêiner PostgreSQL antes de iniciar o Compose. Verifique contêineres ativos com `docker ps`.
- **Porta 8000 em uso:** encerre a outra API com `Ctrl+C` ou identifique o processo que ocupa a porta antes de reiniciar.
- **`/ready` falha ou o frontend não alcança a API:** confirme `docker compose ps`, teste `/health` e `/ready`, verifique `DATABASE_URL` e confirme que o frontend usa `http://localhost:8000/api/v1`.
- **Dependências não sincronizadas:** execute `uv sync --frozen` na raiz. Não altere o lockfile manualmente.
- **Hooks não executam:** rode `uv run pre-commit install --install-hooks` na raiz do repositório.
- **Comando de cópia ou caminho falha no Windows:** confirme se o terminal é PowerShell ou WSL. Use `Copy-Item` e caminhos do Windows no PowerShell; use `cp` e caminhos Linux no WSL.

## Estrutura técnica resumida

- `app/`: aplicação FastAPI e fronteiras técnicas;
- `alembic/`: infraestrutura de migrações, ainda sem revisões;
- `tests/`: testes unitários e de integração com PostgreSQL;
- `scripts/`: validação do repositório;
- `docs/`: arquitetura, decisões e políticas do projeto.

O backend é um único serviço organizado para receber módulos coesos quando o domínio for confirmado. Detalhes sobre erros, logs, acesso ao banco e limites de domínio estão em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e nas [decisões arquiteturais](docs/adr).

## Arquitetura e contribuição

Leia [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir uma contribuição. Consulte também [AGENTS.md](AGENTS.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), as [decisões arquiteturais](docs/adr) e a [política de uso de IA](docs/AI_USAGE.md).
