"""Request limits for the routes that send email or check a password.

`/password-reset/send` and `/accounts/send` trigger email through Cognito,
whose default sender is capped at 50 messages a day. Fifty requests in a loop
would break sign-up and password recovery for the rest of the day. WAF, the
native answer, is denied by the account's service control policy.
"""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_logger = logging.getLogger("app.rate_limit")

SENSITIVE_LIMIT = "5/minute"


def client_identifier(request: Request) -> str:
    """Identify the caller so requests can be counted per origin.

    Behind CloudFront every request arrives from the edge, so the socket
    address is always the same and is useless as a key. The viewer address is
    in `X-Forwarded-For`, and the trustworthy element is the **last** one:
    CloudFront appends the viewer there, while earlier entries can be chosen by
    the client itself.
    """
    settings = get_settings()

    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()

        # Without the header everyone shares one bucket and a single client
        # locks out the rest, so this is logged loudly: it means the proxy is
        # misconfigured, not that the traffic is hostile.
        _logger.error(
            "x_forwarded_for_missing",
            extra={"event": "rate_limit_header_missing", "path": request.url.path},
        )

    return get_remote_address(request)


# Headers stay off: X-RateLimit-Remaining changes between calls and would break
# the guarantee that a delivered code and an unknown address are
# indistinguishable, which tests/password_reset/test_router.py protects.
limiter = Limiter(key_func=client_identifier, headers_enabled=False)
