from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.account_management.domain.account_export import (
    ACCOUNT_EXPORT_HEADER,
    account_export_row,
)
from app.account_management.services.account_filters import AccountFilters
from app.account_management.services.list_accounts import account_summaries
from app.core.csv_document import CsvFile, csv_document
from app.core.local_date import to_local_date
from app.db.models import Event

DATA_EXPORTED_EVENT = "data_exported"


def export_accounts(
    session: Session,
    *,
    administrator_id: UUID,
    filters: AccountFilters,
    now: datetime | None = None,
) -> CsvFile:
    """Every account the listing would show for `filters`, as a CSV file.

    The export runs the listing's own query without pagination, so the file
    always matches the screen. The administrative log records who exported,
    which filters were applied and how many rows left the platform; it never
    stores the exported values.
    """
    reference_now = now or datetime.now(UTC)
    summaries = account_summaries(session, filters)
    content = csv_document(
        ACCOUNT_EXPORT_HEADER,
        (
            account_export_row(
                display_name=summary.display_name,
                user_type=summary.user_type,
                email=summary.email,
                account_status=summary.account_status,
                company_status=summary.company_status,
                missing_fields=summary.missing_fields,
                created_at=summary.created_at,
            )
            for summary in summaries
        ),
    )
    try:
        session.add(
            Event(
                user_id=administrator_id,
                event_type=DATA_EXPORTED_EVENT,
                details={
                    "dataset": "accounts",
                    "filters": filters.applied(),
                    "row_count": len(summaries),
                },
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return CsvFile(
        filename=f"cadastros-{to_local_date(reference_now).isoformat()}.csv",
        content=content,
    )
