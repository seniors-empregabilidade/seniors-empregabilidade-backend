from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.services import get_profile
from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.education import Education
from app.db.models.enums import SkillType, UserType
from app.db.models.experience import Experience
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill


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


def test_profile_is_returned_for_a_registered_candidate(
    database_session: Session,
) -> None:
    user = _create_candidate(database_session)

    profile = get_profile(user.id, session=database_session)

    assert profile.id == user.id
    assert profile.full_name == "Marcos Silveira"
    assert profile.email == user.email
    assert profile.city == "São Paulo"
    assert profile.state == "SP"


def test_age_is_derived_from_the_birth_date(database_session: Session) -> None:
    user = _create_candidate(database_session)

    profile = get_profile(user.id, session=database_session)

    assert profile.age >= 45


def test_profile_without_a_resume_returns_empty_collections(
    database_session: Session,
) -> None:
    user = _create_candidate(database_session)

    profile = get_profile(user.id, session=database_session)

    assert profile.summary is None
    assert profile.experiences == ()
    assert profile.education == ()
    assert profile.skills == ()


def test_profile_includes_resume_experiences_education_and_skills(
    database_session: Session,
) -> None:
    user = _create_candidate(database_session)

    resume = Resume(candidate_id=user.id, summary="Profissional de operações.")
    database_session.add(resume)
    database_session.flush()

    database_session.add(
        Experience(
            resume_id=resume.id,
            company_name="Log Brasil",
            role="Gerente de Operações",
            start_date=date(2012, 1, 1),
            end_date=date(2023, 12, 31),
            description="Equipe de 40 pessoas.",
        )
    )
    database_session.add(
        Education(
            resume_id=resume.id,
            institution="FGV",
            degree="MBA em Gestão Empresarial",
            field="Gestão",
            start_date=date(2009, 1, 1),
            end_date=date(2011, 12, 31),
        )
    )

    name = f"Lideranca {uuid4().hex[:6]}"
    skill = Skill(name=name, normalized_name=name.casefold(), type=SkillType.SOFT)
    database_session.add(skill)
    database_session.flush()
    database_session.add(ResumeSkill(resume_id=resume.id, skill_id=skill.id))
    database_session.flush()

    profile = get_profile(user.id, session=database_session)

    assert profile.summary == "Profissional de operações."
    assert len(profile.experiences) == 1
    assert profile.experiences[0].company_name == "Log Brasil"
    assert len(profile.education) == 1
    assert profile.education[0].degree == "MBA em Gestão Empresarial"
    assert [item.name for item in profile.skills] == [skill.name]


def test_unknown_user_raises_profile_not_found(database_session: Session) -> None:
    with pytest.raises(ProfileNotFoundError):
        get_profile(uuid4(), session=database_session)


def test_education_is_ordered_by_most_recent_start_date(
    database_session: Session,
) -> None:
    user = _create_candidate(database_session)
    resume = Resume(candidate_id=user.id)
    database_session.add(resume)
    database_session.flush()
    for year in (2005, 2015, 2010):
        database_session.add(
            Education(
                resume_id=resume.id,
                institution=f"Instituicao {year}",
                start_date=date(year, 1, 1),
            )
        )
    database_session.add(Education(resume_id=resume.id, institution="Sem data"))
    database_session.flush()

    profile = get_profile(user.id, session=database_session)

    assert [item.institution for item in profile.education] == [
        "Instituicao 2015",
        "Instituicao 2010",
        "Instituicao 2005",
        "Sem data",
    ]
