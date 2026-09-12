import uuid
from unittest.mock import patch, Mock

import pytest
from fastapi import status

from typing import Any
from sqlalchemy.orm import Session

from app.core.errors import ProblemException
from app.schemas.professional import ProfessionalCreateRequest
from app.use_cases.register_professional import register_candidate


# Helper to build a valid request
def _valid_request(**overrides: Any) -> ProfessionalCreateRequest:
    """Helper to build a valid ProfessionalCreateRequest with optional overrides.

    The default ``date_of_birth`` is a ``date`` instance.
    """
    from datetime import date
    full_name = overrides.get("full_name", "John Doe")
    cpf = overrides.get("cpf", "123.456.789-09")
    date_of_birth = overrides.get("date_of_birth", date(1970, 1, 1))
    email = overrides.get("email", "john.doe@example.com")
    password = overrides.get("password", "Aa1!aaaa")
    phone = overrides.get("phone", "+55 11 99999-9999")
    return ProfessionalCreateRequest(
        full_name=full_name,
        cpf=cpf,
        date_of_birth=date_of_birth,
        email=email,
        password=password,
        phone=phone,
    )


def test_invalid_cpf_fails_before_db_calls() -> None:
    """CPF inválido deve abortar antes de qualquer consulta ao banco."""
    request = _valid_request(cpf="111.111.111-11")

    # Use a mock Session to satisfy type checking
    mock_session = Mock(spec=Session)
    with (
        patch("app.repositories.candidate.exists_by_cpf") as mock_cpf,
        patch("app.repositories.candidate.exists_by_email") as mock_email,
    ):
        mock_cpf.side_effect = AssertionError("exists_by_cpf should not be called")
        mock_email.side_effect = AssertionError("exists_by_email should not be called")
        with pytest.raises(ProblemException) as exc_info:
            register_candidate(request, session=mock_session)

    err = exc_info.value.errors
    assert err is not None
    assert "cpf" in err
    assert "CPF inválido" in err["cpf"]
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_duplicate_cpf_returns_409() -> None:
    request = _valid_request()
    mock_session = Mock(spec=Session)
    with (
        patch("app.repositories.candidate.exists_by_cpf", return_value=True),
        patch("app.repositories.candidate.exists_by_email", return_value=False),
        patch("app.repositories.candidate.create") as mock_create,
    ):
        mock_create.side_effect = AssertionError(
            "create should not be called on duplicate"
        )
        with pytest.raises(ProblemException) as exc_info:
            register_candidate(request, session=mock_session)
    err = exc_info.value.errors
    assert err is not None
    assert "cpf" in err and "CPF já cadastrado" in err["cpf"]
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


def test_successful_registration_returns_uuid_string() -> None:
    request = _valid_request()
    fake_uuid = uuid.uuid4()

    class FakeCandidate:
        def __init__(self, id: uuid.UUID):
            self.id = id

    mock_session = Mock(spec=Session)
    with (
        patch("app.repositories.candidate.exists_by_cpf", return_value=False),
        patch("app.repositories.candidate.exists_by_email", return_value=False),
        patch(
            "app.repositories.candidate.create", return_value=FakeCandidate(fake_uuid)
        ),
    ):
        result = register_candidate(request, session=mock_session)
    assert isinstance(result, str)
    assert result == str(fake_uuid)
