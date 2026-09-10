from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.companies.domain.exceptions import (
    CompanySegmentBlockedError,
    InvalidCNPJError,
    PersonalEmailDomainError,
)
from app.companies.domain.value_objects.cnpj import CNPJ
from app.companies.integrations.brasil_api import (
    BrasilAPIClient,
    RegistryProviderUnavailableError,
    RegistryRecordNotFoundError,
)
from app.companies.schemas import (
    CompanyRegistrationRequest,
    CompanyResponse,
    RegistryRecordResponse,
)
from app.companies.services.company_registry import CompanyRegistry
from app.companies.services.register_company import (
    CompanyCNPJConflictError,
    CompanyEmailConflictError,
    register_company,
)
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(tags=["companies"])


def get_company_registry(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[CompanyRegistry]:
    with BrasilAPIClient(
        base_url=str(settings.brasil_api_base_url),
        timeout_seconds=settings.brasil_api_timeout_seconds,
    ) as client:
        yield client


def _problem(status_code: int, code: str, detail: str) -> ProblemException:
    titles = {
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Content",
        503: "Service Unavailable",
    }
    field = {
        "invalid_cnpj": "cnpj",
        "cnpj_not_found": "cnpj",
        "company_cnpj_conflict": "cnpj",
        "company_email_conflict": "corporate_email",
        "company_email_domain_blocked": "corporate_email",
        "company_segment_blocked": "cnpj",
    }.get(code)
    return ProblemException(
        status_code=status_code,
        title=titles[status_code],
        code=code,
        detail=detail,
        errors={field: [detail]} if field else None,
    )


@router.get(
    "/company-registry-records/{cnpj:path}",
    response_model=RegistryRecordResponse,
    responses={404: PROBLEM_RESPONSE, 422: PROBLEM_RESPONSE, 503: PROBLEM_RESPONSE},
)
def get_registry_record(
    cnpj: Annotated[str, Path(min_length=1, max_length=18)],
    registry: Annotated[CompanyRegistry, Depends(get_company_registry)],
) -> RegistryRecordResponse:
    try:
        return registry.get_record(CNPJ(cnpj).value)
    except InvalidCNPJError as exc:
        raise _problem(422, "invalid_cnpj", "The CNPJ is invalid.") from exc
    except RegistryRecordNotFoundError as exc:
        raise _problem(404, "cnpj_not_found", "The CNPJ was not found.") from exc
    except RegistryProviderUnavailableError as exc:
        raise _problem(
            503,
            "cnpj_provider_unavailable",
            "The company registry is temporarily unavailable.",
        ) from exc


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: PROBLEM_RESPONSE,
        403: PROBLEM_RESPONSE,
        429: PROBLEM_RESPONSE,
        404: PROBLEM_RESPONSE,
        409: PROBLEM_RESPONSE,
        422: PROBLEM_RESPONSE,
        503: PROBLEM_RESPONSE,
    },
)
def create_company(
    request: CompanyRegistrationRequest,
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[CompanyRegistry, Depends(get_company_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
    identity_provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> CompanyResponse:
    try:
        return register_company(
            request,
            session=session,
            registry=registry,
            identity_provider=identity_provider,
            blocked_cnae_prefixes=tuple(settings.blocked_cnae_prefixes),
            personal_email_domains=frozenset(settings.personal_email_domains),
        )
    except InvalidCNPJError as exc:
        raise _problem(422, "invalid_cnpj", "The CNPJ is invalid.") from exc
    except PersonalEmailDomainError as exc:
        raise _problem(
            422,
            "company_email_domain_blocked",
            "A corporate email address is required.",
        ) from exc
    except CompanySegmentBlockedError as exc:
        raise _problem(
            422, "company_segment_blocked", "This company segment cannot register."
        ) from exc
    except CompanyCNPJConflictError as exc:
        raise _problem(
            409, "company_cnpj_conflict", "A company with this CNPJ already exists."
        ) from exc
    except CompanyEmailConflictError as exc:
        raise _problem(
            409, "company_email_conflict", "An account with this email already exists."
        ) from exc
    except RegistryRecordNotFoundError as exc:
        raise _problem(404, "cnpj_not_found", "The CNPJ was not found.") from exc
    except RegistryProviderUnavailableError as exc:
        raise _problem(
            503,
            "cnpj_provider_unavailable",
            "The company registry is temporarily unavailable.",
        ) from exc
