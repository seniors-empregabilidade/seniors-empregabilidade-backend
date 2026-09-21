import os
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.db.models.enums import SkillType
from app.db.session import get_engine
from app.skills.schemas import SkillRequest
from app.skills.services import CatalogSkill, find_or_create_skills

pytestmark = pytest.mark.integration

# Each session here commits, so the rows outlive the test and are deleted by name.
# The names are already normalized and sorted, which keeps that cleanup exact.
ALPHA = "concurrency alpha"
BRAVO = "concurrency bravo"
CHARLIE = "concurrency charlie"
NAMES = (ALPHA, BRAVO, CHARLIE)


@pytest.fixture(autouse=True)
def clean_committed_skills() -> Iterator[None]:
    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip("requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL")

    _delete_skills()
    yield
    _delete_skills()


def test_two_sessions_creating_the_same_skill_share_one_catalog_entry() -> None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        with _new_session() as first:
            created = find_or_create_skills(_requests(ALPHA), session=first)
            second = executor.submit(_resolve_and_commit, ALPHA)
            _wait_until_sessions_wait_for_a_lock(1, second)
            first.commit()
        reused = second.result(timeout=10)

    assert reused == created
    assert _stored_count() == 1


def test_sessions_creating_overlapping_skills_in_opposite_order_both_succeed() -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        with _new_session() as gate:
            # The gate keeps the shared middle name uncommitted, so both sessions are
            # mid-insert when it commits. Inserting in request order would leave each
            # one waiting for the name the other inserted first: a deadlock.
            find_or_create_skills(_requests(BRAVO), session=gate)
            forward = executor.submit(_resolve_and_commit, ALPHA, BRAVO, CHARLIE)
            backward = executor.submit(_resolve_and_commit, CHARLIE, BRAVO, ALPHA)
            _wait_until_sessions_wait_for_a_lock(2, forward, backward)
            gate.commit()
        forward_found = forward.result(timeout=10)
        backward_found = backward.result(timeout=10)

    assert backward_found == forward_found[::-1]
    assert _stored_count() == 3


def _requests(*names: str) -> list[SkillRequest]:
    return [SkillRequest(name=name, type=SkillType.HARD) for name in names]


def _new_session() -> Session:
    return Session(bind=get_engine(), expire_on_commit=False, autoflush=False)


def _resolve_and_commit(*names: str) -> list[CatalogSkill]:
    with _new_session() as session:
        found = find_or_create_skills(_requests(*names), session=session)
        session.commit()
        return found


def _wait_until_sessions_wait_for_a_lock(
    count: int, *workers: Future[list[CatalogSkill]]
) -> None:
    waiting = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() "
        "AND cardinality(pg_blocking_pids(pid)) > 0"
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        # A worker that failed before blocking re-raises its own error here, instead
        # of surfacing later as a misleading timeout.
        for worker in workers:
            if worker.done():
                worker.result()
        # A new connection each time: activity is read once per transaction.
        with get_engine().connect() as connection:
            if connection.scalar(waiting) >= count:
                return
        time.sleep(0.01)
    raise AssertionError(f"expected {count} session(s) waiting for a lock")


def _stored_count() -> int:
    with _new_session() as session:
        stored = (
            select(func.count())
            .select_from(Skill)
            .where(Skill.normalized_name.in_(NAMES))
        )
        return session.scalar(stored) or 0


def _delete_skills() -> None:
    with get_engine().begin() as connection:
        connection.execute(delete(Skill).where(Skill.normalized_name.in_(NAMES)))
