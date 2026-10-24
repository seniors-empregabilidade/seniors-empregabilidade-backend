# Certifications

US-07-T01 lets a professional record certifications on the résumé and attach one
proof document to each. The document is personal data: only its owner and an
administrator can download it.

## Data

`certification` holds the name, issuer, issue date and expiration date. Only the
name is required, and the expiration date cannot precede the issue date.

`attached_certificate` holds at most one document per certification
(`uq_attached_certificate_certification_id`) and is removed with it. It stores
the storage key, the sanitized original filename, the detected content type, the
size and the upload time. It never stores a URL: links are created on demand and
expire.

## API contract

All paths start with `/api/v1/professionals` and require a candidate token,
except the administrator route.

| Endpoint | Request | Success |
| --- | --- | --- |
| `POST /me/certifications` | JSON `name`, `issuer`, `issued_date`, `expiration_date` | `201`: certification with `document: null` |
| `PATCH /me/certifications/{id}` | Any of the same fields; `name` cannot be cleared | `200`: certification |
| `DELETE /me/certifications/{id}` | — | `204`; the document goes with it |
| `PUT /me/certifications/{id}/document` | `multipart/form-data` with `file` | `200`: certification with `document` metadata; replaces any previous file |
| `DELETE /me/certifications/{id}/document` | — | `204` |
| `GET /me/certifications/{id}/document` | — | `200`: `url` and `expires_at` |
| `GET /{professional_id}/certifications/{id}/document` | Administrator token | `200`: `url` and `expires_at` |

`GET /me` lists the certifications, newest issue date first, with the same
`document` metadata (`filename`, `content_type`, `size_bytes`, `uploaded_at`).

The download `url` is a pre-signed storage link valid for five minutes. It forces
`Content-Disposition: attachment` with the original filename and the detected
content type, so a browser downloads the file instead of rendering it. The
frontend sends the access token in a header, so it requests the link first and
then opens it.

## Document rules

- PDF, PNG or JPEG, decided by the file's leading bytes. The extension and the
  declared content type are ignored.
- At most 5 MB (`MAX_DOCUMENT_BYTES`).
- The filename is reduced to a printable base name of at most 255 characters,
  keeping the extension.
- Both checks run before any storage call.
- Any request body over 5 MB plus 64 KB of multipart framing is refused with
  `413` while it is received, before parsing and authentication
  (`RequestBodyLimitMiddleware`).

| Failure | Status | `code` |
| --- | --- | --- |
| Certification missing or owned by someone else | `404` | `certification_not_found` |
| No document attached | `404` | `certification_document_not_found` |
| Expiration before issue | `422` | `invalid_certification_period` |
| Not a PDF, PNG or JPEG | `422` | `unsupported_document_type` |
| Larger than 5 MB | `422` | `document_too_large` |
| Request body larger than the upload limit | `413` | `http_413` |
| Storage unconfigured or failing | `503` | `document_storage_unavailable` |

## Storage

`app.storage.DocumentStorage` is the port; `S3DocumentStorage` implements it.
Objects are written under `certifications/{certification_id}/{random}` so the key
carries no personal data. Uploads and removals lock the certification row, so
a removal waits for a concurrent replacement and deletes the file it stored. The
upload stores the object, then commits the row. When the commit fails, the new
object is deleted. When a document is replaced or removed, the old object is
deleted after the commit. A failed cleanup is logged as `document_cleanup_failed` and leaves an
orphaned object rather than failing a request that already succeeded.

| Setting | Production | Local |
| --- | --- | --- |
| `UPLOADS_BUCKET` | From `/seniors/api/config` | `seniors-uploads-local` |
| `UPLOADS_REGION` | `us-east-2` (default) | `us-east-2` |
| `S3_ENDPOINT_URL` | unset | `http://localhost:9090` |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | unset; the instance role signs | any value |

Locally, `docker compose up -d s3` runs S3Mock with the bucket already created.
It does not check signatures, so it cannot catch a permission problem.

In production the API container signs S3 calls with the EC2 instance role. It
reads the credentials from the instance metadata service through the Docker
bridge, which needs an IMDSv2 hop limit of at least 2. The uploads bucket is
versioned, so a deleted object stays as a noncurrent version until a lifecycle
rule expires it. Both settings belong to the infrastructure repository.

## Out of scope

- Companies cannot download documents. Grant access when a story that shows a
  candidate's résumé to a company requires it.
- No virus scanning.
- Orphaned objects from failed cleanups are not swept.
