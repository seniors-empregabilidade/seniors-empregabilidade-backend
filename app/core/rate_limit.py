"""Limite de requisições nas rotas que disparam e-mail ou tentam senha.

Existe por um motivo concreto: `/password-reset/send` e `/accounts/send`
disparam e-mail pelo Cognito, cujo remetente padrão tem teto de 50 por dia. Um
laço de cinquenta requisições deixa cadastro e recuperação de senha quebrados
pelo resto do dia, sem derrubar nada e sem chamar atenção.

O WAF, que seria a resposta nativa, é negado pela SCP da conta AGES, então o
limite mora aqui.
"""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_logger = logging.getLogger("app.rate_limit")

SENSITIVE_LIMIT = "5/minute"


def client_identifier(request: Request) -> str:
    """Identifica quem está chamando, para contar as requisições por origem.

    Atrás do CloudFront todo request chega do edge, então o IP do socket é
    sempre o mesmo e não serve de chave. O IP real do visitante vai no
    `X-Forwarded-For` — e o elemento confiável é o **último**: o CloudFront
    anexa o IP do viewer no fim da cadeia, enquanto os anteriores podem ter
    sido escolhidos pelo próprio cliente.
    """
    settings = get_settings()

    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()

        # Sem o cabeçalho, todo mundo cairia no mesmo balde e um único cliente
        # derrubaria o login de todos. Cair para o IP do socket não resolve
        # atrás de proxy, então o erro é registrado alto: indica proxy mal
        # configurado, não tráfego malicioso.
        _logger.error(
            "x_forwarded_for_ausente",
            extra={"event": "rate_limit_sem_cabecalho", "path": request.url.path},
        )

    return get_remote_address(request)


# headers_enabled fica desligado de propósito. Com ele, o X-RateLimit-Remaining
# muda entre a primeira e a segunda chamada — e isso quebra a garantia de que
# "código entregue" e "endereço desconhecido" respondem de forma indistinguível,
# que o teste em tests/password_reset/test_router.py protege. Um contador na
# resposta é conveniência; não valer a pena vazar contagem por ela.
limiter = Limiter(key_func=client_identifier, headers_enabled=False)
