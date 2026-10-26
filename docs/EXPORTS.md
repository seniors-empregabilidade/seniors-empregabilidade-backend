# CSV exports

US-25-T01 (CU-86e3ke4t6). An administrator downloads, as a CSV file, the same
results the "Cadastros" list and the "Relatórios" dashboard show for the filters
currently applied. The export reuses the listing query and the indicator
calculation, so the file always matches the screen. It adds no table, column or
dependency.

## Endpoints

| Route | Same filters as | File name |
|---|---|---|
| `GET /api/v1/admin/accounts/export` | `GET /api/v1/admin/accounts`, without `limit` and `offset` | `cadastros-AAAA-MM-DD.csv` |
| `GET /api/v1/indicators/export` | `GET /api/v1/indicators` | `relatorios-AAAA-MM-DD.csv` |

Both routes require `require_administrator`. A missing or invalid token answers
`401 invalid_access_token`, a candidate or a company `403 administrator_required`,
and a suspended or blocked administrator `403 account_unavailable`. Invalid
filters answer exactly as the matching list route does (`422 validation_error`,
`422 invalid_completion_range` or `422 invalid_period`). A refused request
writes nothing.

A successful export answers `200` with:

- `Content-Type: text/csv; charset=utf-8`;
- `Content-Disposition: attachment; filename="..."`, dated with the Brazil
  calendar day (`America/Sao_Paulo`);
- `Cache-Control: no-store`.

CORS exposes `Content-Disposition`, so the browser client can read the file
name.

## File format

`app/core/csv_document.py` writes every export for Excel in Brazilian
Portuguese:

- UTF-8 with a byte order mark, so Excel does not misread accented text;
- `;` as the separator, because pt-BR Excel uses `,` as the decimal separator;
- CRLF line endings, with quotes only where a value needs them;
- dates as `dd/mm/aaaa` (and `dd/mm/aaaa HH:MM`) in Brazil time;
- header and values in Brazilian Portuguese, with the screen's labels.

A text cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets
a leading `'`. Names are typed by users, and without it a name such as
`=HYPERLINK(...)` would run as a formula in the administrator's spreadsheet
(OWASP CSV injection). Excel shows the apostrophe-prefixed value as text.

An export with no matching rows still answers `200` with the header row.

## Accounts file

Every account that the listing would return for the filters, newest first,
with no pagination.

| Column | Value |
|---|---|
| `Nome` | Candidate full name, or company trade name, or legal name; blank when none exists |
| `Tipo` | `Profissional` or `Empresa` |
| `E-mail` | The account email |
| `Status da conta` | `Ativa`, `Suspensa` or `Bloqueada` |
| `Situação da empresa` | `Pendente`, `Aprovada`, `Recusada` or `Bloqueada`; blank for a candidate |
| `Currículo` | `Completo` or `Incompleto` under the US-08 rule; blank for a company |
| `Campos faltantes` | The missing US-08 fields (`Cidade`, `Estado`, `Resumo profissional`, `Experiência profissional`, `Formação`, `Habilidades`), comma separated |
| `Data de cadastro` | Account creation day |

Only fields the listing already shows to an administrator are exported. CPF,
phone, birth date, address, résumé content, certificate documents, block
justifications, ids and the legacy `completion_percentage` never leave in the
file. The labels live in `app/account_management/domain/account_export.py`.

## Indicators file

A two-column `Item;Valor` sheet. The rows are, in order:

1. `Gerado em`, the generation time;
2. every dashboard filter: `Data inicial` and `Data final` (`Sem limite` when
   not sent), then the five status filters (`Todos` or `Todas` when not sent);
3. the eight dashboard numbers: `Profissionais`, `Empresas`, `Vagas`,
   `Candidaturas`, `Matches`, `Profissionais sem colocação`,
   `Situação profissional não informada` and `Currículos incompletos`.

The numbers come from `get_platform_indicators`, so their rules are the ones in
[INDICATORS.md](INDICATORS.md). The labels live in
`app/indicators/domain/indicator_export.py`.

## Administrative log

Each delivered export writes one `event` row in the same transaction:

| Column | Value |
|---|---|
| `user_id` | The administrator who exported |
| `event_type` | `data_exported` |
| `details` | `{"dataset": "accounts" \| "indicators", "filters": {...}, "row_count": N}` |

`filters` holds only the filters actually sent, as their API values (dates in
ISO format). `row_count` is the number of data rows in the file. The exported
values themselves are never logged. If the log cannot be written, the request
fails and no file is delivered.

## Tests

- `tests/core/test_csv_document.py`: byte order mark, separator, quoting,
  formula neutralization and Brazil dates.
- `tests/account_management/domain/test_account_export.py` and
  `tests/indicators/domain/test_indicator_export.py`: column labels.
- `tests/account_management/test_export_integration.py` and
  `tests/indicators/test_indicator_export_integration.py`: the file matches
  the list or the dashboard for the same filters, roles, the audit row and
  rollback when the log cannot be written. They compare the export with the
  API response instead of fixed totals, so they also pass on a database that
  holds seed or manual data.

## Local verification

```bash
uv run uvicorn app.main:app --reload --no-access-log
```

Open `/docs`, authorize with an administrator access token and call either
export route. Open the downloaded file in Excel configured for Brazilian
Portuguese and check accents, columns and dates.
