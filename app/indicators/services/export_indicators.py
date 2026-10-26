from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.csv_document import CsvFile, csv_document
from app.core.local_date import to_local_date
from app.db.models import Event
from app.indicators.domain.indicator_export import (
    INDICATOR_EXPORT_HEADER,
    indicator_export_rows,
)
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.services.platform_indicators import get_platform_indicators

DATA_EXPORTED_EVENT = "data_exported"


def export_indicators(
    session: Session,
    *,
    administrator_id: UUID,
    filters: IndicatorFilters,
    now: datetime | None = None,
) -> CsvFile:
    """The dashboard numbers for `filters`, with those filters, as a CSV file.

    The numbers come from `get_platform_indicators`, the calculation the
    dashboard shows. The administrative log records who exported and which
    filters were applied.
    """
    reference_now = now or datetime.now(UTC)
    indicators = get_platform_indicators(session, filters, now=reference_now)
    rows = indicator_export_rows(
        generated_at=reference_now,
        filters=filters,
        counts={
            **indicators.totals.model_dump(),
            **indicators.segments.model_dump(),
        },
    )
    try:
        session.add(
            Event(
                user_id=administrator_id,
                event_type=DATA_EXPORTED_EVENT,
                details={
                    "dataset": "indicators",
                    "filters": _applied(filters),
                    "row_count": len(rows),
                },
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return CsvFile(
        filename=f"relatorios-{to_local_date(reference_now).isoformat()}.csv",
        content=csv_document(INDICATOR_EXPORT_HEADER, rows),
    )


def _applied(filters: IndicatorFilters) -> dict[str, Any]:
    """The filters actually sent, as JSON values for the audit log."""
    # Dates become ISO strings; status filters are StrEnum members, whose
    # `str` is their stable value.
    return {
        name: value.isoformat() if isinstance(value, date) else str(value)
        for name, value in asdict(filters).items()
        if value is not None
    }
