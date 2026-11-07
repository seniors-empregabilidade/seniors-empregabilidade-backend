# Company profile (US-30-T01)

An approved company reads and edits its own profile. Both routes take no company
id: the company is the one behind the access token, so no other organization can
be read or changed. Other accounts receive `403 approved_company_required`.

## Contract

`GET /api/v1/companies/me/profile` and `PUT /api/v1/companies/me/profile` answer
the same body, with `Cache-Control: no-store`:

```json
{
  "id": "<uuid>",
  "cnpj": "11222333000181",
  "display_name": "Nome da empresa",
  "legal_name": "Razão Social Ltda",
  "industry": "Tecnologia",
  "address": {
    "street": "Rua", "number": "10", "complement": null, "neighborhood": "Centro",
    "city": "Porto Alegre", "state": "RS", "zip_code": "90010000"
  },
  "contact_email": "contato@empresa.com.br",
  "contact_phone": "+55 51 3333-0000"
}
```

`PUT` replaces the editable profile, as the edit modal sends it:

- `display_name`, `legal_name`, `address` and `contact_email` are required;
  `industry` and `contact_phone` are optional, and blank or missing clears them.
- `address` follows the registration rules (`AddressRequest`, US-14): the ZIP code
  is normalized to 8 digits and the state to an uppercase UF.
- `contact_email` follows the registration e-mail rules, so personal providers
  answer `422 company_email_domain_blocked` with `errors.contact_email`.
- `cnpj` may be sent only with the stored value (formatted or not). Any other
  value answers `422 cnpj_read_only` with `errors.cnpj`; the change is made by
  support.
- Invalid fields answer `422 validation_error` with one entry per field in
  `errors`. Any refusal writes nothing.

## What does not change

- `contact_email` and `contact_phone` are new `company` columns. They never touch
  `app_user.email` or `company.corporate_email`, which are the login e-mail.
  Until a company edits its profile, `contact_email` is `null` and the API
  shows the login e-mail.
- The CNPJ, the approval status and the identity credentials stay as they are.
- Jobs read the company live, so `GET /jobs` and `GET /jobs/{job_id}` show the
  new `company_name` (`trade_name`, falling back to `legal_name`),
  `company_industry` and `company_city` (from the company address) as soon as
  the edit commits. A job's own `location` is set per job and is not changed.
