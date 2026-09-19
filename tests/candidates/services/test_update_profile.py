from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.schemas.profile import ProfessionalProfileUpdateRequest
from app.candidates.services import update_profile
from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.enums import UserType
from app.db.models.resume import Resume


def _create_candidate(session: Session) -> AppUser:
    user = AppUser(
        email=f"{uuid4().hex}@example.com",
        identity_subject=uuid4().hex,
        user_type=UserType.CANDIDATE,
    )
    session.add(user)
    session.flush()

    candidate = Candidate(
        id=user.id,
        full_name="Marcos Silveira",
        cpf=f"{uuid4().int % 10**11:011d}",
        birth_date=date(1968, 3, 15),
        phone="51999990000",
        city="São Paulo",
        state="SP",
    )
    session.add(candidate)
    session.flush()
    return user


def test_editable_fields_are_updated(database_session: Session) -> None:
    user = _create_candidate(database_session)

    profile = update_profile(
        user.id,
        ProfessionalProfileUpdateRequest(
            full_name="Marcos S. Silveira",
            phone="51988887777",
            city="Curitiba",
            state="pr",
        ),
        session=database_session,
    )

    assert profile.full_name == "Marcos S. Silveira"
    assert profile.phone == "51988887777"
    assert profile.city == "Curitiba"
    assert profile.state == "PR"


def test_omitted_fields_are_preserved(database_session: Session) -> None:
    user = _create_candidate(database_session)

    profile = update_profile(
        user.id,
        ProfessionalProfileUpdateRequest(city="Curitiba"),
        session=database_session,
    )

    assert profile.city == "Curitiba"
    assert profile.full_name == "Marcos Silveira"
    assert profile.phone == "51999990000"


def test_summary_creates_a_resume_when_missing(database_session: Session) -> None:
    user = _create_candidate(database_session)

    profile = update_profile(
        user.id,
        ProfessionalProfileUpdateRequest(summary="Profissional de operações."),
        session=database_session,
    )

    resume = database_session.scalar(
        select(Resume).where(Resume.candidate_id == user.id)
    )

    assert profile.summary == "Profissional de operações."
    assert resume is not None


def test_summary_updates_an_existing_resume(database_session: Session) -> None:
    user = _create_candidate(database_session)
    database_session.add(Resume(candidate_id=user.id, summary="Resumo antigo."))
    database_session.flush()

    profile = update_profile(
        user.id,
        ProfessionalProfileUpdateRequest(summary="Resumo novo."),
        session=database_session,
    )

    assert profile.summary == "Resumo novo."


def test_unknown_user_raises_profile_not_found(database_session: Session) -> None:
    with pytest.raises(ProfileNotFoundError):
        update_profile(
            uuid4(),
            ProfessionalProfileUpdateRequest(city="Curitiba"),
            session=database_session,
        )
