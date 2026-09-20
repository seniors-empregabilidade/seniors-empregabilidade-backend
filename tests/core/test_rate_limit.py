import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import client_identifier, limiter
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider


def _request(headers: dict[str, str], client_host: str = "203.0.113.9") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": raw,
            "client": (client_host, 1234),
            "query_string": b"",
        }
    )


def test_o_ip_do_visitante_e_o_ultimo_da_cadeia_encaminhada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # O cliente controla o começo do X-Forwarded-For; o CloudFront anexa o IP
    # real no fim. Ler o primeiro elemento deixaria a chave falsificável.
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    forjado = "1.1.1.1, 2.2.2.2, 198.51.100.7"
    assert client_identifier(_request({"x-forwarded-for": forjado})) == "198.51.100.7"

    get_settings.cache_clear()


def test_sem_o_cabecalho_esperado_o_erro_e_registrado(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    with caplog.at_level(logging.ERROR, logger="app.rate_limit"):
        identificador = client_identifier(_request({}))

    assert identificador == "203.0.113.9"
    assert "x_forwarded_for_ausente" in caplog.text

    get_settings.cache_clear()


def test_fora_de_proxy_vale_o_ip_do_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    get_settings.cache_clear()

    # Mesmo com o cabeçalho presente, ele é ignorado: sem proxy na frente,
    # confiar nele seria deixar qualquer cliente escolher a própria chave.
    pedido = _request({"x-forwarded-for": "9.9.9.9"})
    assert client_identifier(pedido) == "203.0.113.9"

    get_settings.cache_clear()


def test_a_sexta_chamada_seguida_e_recusada_com_problem_details(
    application: FastAPI, client: TestClient
) -> None:
    # Sem provedor configurado, a dependência falha com 503 antes do endpoint —
    # e o limitador, que roda dentro do endpoint, nunca seria exercitado.
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider

    limiter.reset()
    caminho = "/api/v1/password-reset/send"
    corpo = {"email": "pessoa@example.invalid"}

    respostas = [client.post(caminho, json=corpo) for _ in range(6)]
    assert [r.status_code for r in respostas[:5]] == [202] * 5

    recusada = respostas[-1]
    assert recusada.status_code == 429
    corpo_resposta = recusada.json()
    assert corpo_resposta["code"] == "rate_limited"
    assert corpo_resposta["status"] == 429
    assert corpo_resposta["instance"] == caminho

    limiter.reset()
