# WhatsApp support contact (US-27)

`GET /api/v1/support/contact` gives the front end what it needs to build the
WhatsApp support link (`https://wa.me/<whatsapp_number>?text=<initial_message>`).
It is public, so the support button also works on the login and registration
pages.

| Status | Body |
| --- | --- |
| `200` | `{"whatsapp_number": "5551999990000", "initial_message": "..."}` |
| `404` | `support_contact_not_configured`: no number is set; hide the button |

## Configuration

| Variable | Default | Rule |
| --- | --- | --- |
| `SUPPORT_WHATSAPP_NUMBER` | unset | Digits only, country code first, 10 to 15 digits, as `wa.me` expects (`5551999990000`). Empty means unset. |
| `SUPPORT_WHATSAPP_MESSAGE` | `Olá! Preciso de ajuda com a plataforma Seniors.` | 1 to 500 characters. |

The message is fixed configuration. The backend never adds CPF, name, e-mail or
any other user data to it, and the front end must not either.
