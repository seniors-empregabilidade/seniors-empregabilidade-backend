from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.jobs.exceptions import ClosingDateInThePastError
from app.jobs.schemas import CreateJobRequest
from app.jobs.services.publish_job import publish_job
from tests.jobs.conftest import ManageJobsScenario

pytestmark = pytest.mark.integration

# 22:30 on January 1st in America/Sao_Paulo, already January 2nd in UTC.
EVENING_IN_BRAZIL = datetime(2020, 1, 2, 1, 30, tzinfo=UTC)


def request_closing_on(closing_date: date) -> CreateJobRequest:
    return CreateJobRequest.model_validate(
        {
            "title": "Analista de operações",
            "skills": [{"name": "Gestão de equipes", "type": "soft"}],
            "work_mode": "remote",
            "closing_date": closing_date,
        }
    )


def test_a_job_can_close_on_the_local_today_late_in_the_evening(
    database_session: Session, manage_jobs_scenario: ManageJobsScenario
) -> None:
    job = publish_job(
        request_closing_on(date(2020, 1, 1)),
        session=database_session,
        company_id=manage_jobs_scenario.owner_company_id,
        now=EVENING_IN_BRAZIL,
    )

    assert job.closing_date == date(2020, 1, 1)


def test_the_local_yesterday_is_in_the_past(
    database_session: Session, manage_jobs_scenario: ManageJobsScenario
) -> None:
    with pytest.raises(ClosingDateInThePastError):
        publish_job(
            request_closing_on(date(2019, 12, 31)),
            session=database_session,
            company_id=manage_jobs_scenario.owner_company_id,
            now=EVENING_IN_BRAZIL,
        )
