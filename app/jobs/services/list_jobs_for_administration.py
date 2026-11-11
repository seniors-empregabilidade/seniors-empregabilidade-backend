from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import Company, Job
from app.jobs.schemas import AdminJobListResponse, AdminJobResponse


def list_jobs_for_administration(
    session: Session, *, search: str | None, limit: int, offset: int
) -> AdminJobListResponse:
    """List every job, in any status, for an administrator to pick from.

    The search matches part of the title, ignoring case, with LIKE wildcards
    taken as text. A search with a NUL character, which no stored title can
    contain, finds nothing instead of reaching the database.
    """
    term = search.strip() if search is not None else ""
    if "\x00" in term:
        return AdminJobListResponse(items=[], total=0)

    conditions: list[ColumnElement[bool]] = []
    if term:
        conditions.append(Job.title.icontains(term, autoescape=True))

    company_name = func.coalesce(Company.trade_name, Company.legal_name)
    total = session.scalar(select(func.count()).select_from(Job).where(*conditions))
    rows = session.execute(
        select(Job.id, Job.title, company_name.label("company_name"), Job.status)
        .join(Company, Company.id == Job.company_id)
        .where(*conditions)
        .order_by(Job.title, Job.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AdminJobListResponse(
        items=[
            AdminJobResponse(
                id=row.id,
                title=row.title,
                company_name=row.company_name,
                status=row.status,
            )
            for row in rows
        ],
        total=total or 0,
    )
