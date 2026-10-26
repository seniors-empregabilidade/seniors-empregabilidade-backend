"""CSV files that open directly in a Brazilian Portuguese Excel installation.

Excel in pt-BR uses the comma as its decimal separator, so its list separator
is the semicolon. Without a byte order mark it reads UTF-8 as the system code
page and breaks accented text. Both choices live here so every export shares
them.
"""

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import Response

from app.core.local_date import LOCAL_TIMEZONE, to_local_date

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"

_BYTE_ORDER_MARK = "﻿"
# A spreadsheet evaluates a cell that starts with one of these characters as a
# formula, so text typed by a user could run in the administrator's Excel
# (OWASP "CSV injection"). A leading apostrophe makes Excel show it as text.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True, slots=True)
class CsvFile:
    filename: str
    content: bytes


def csv_document(header: Sequence[str], rows: Iterable[Sequence[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    buffer.write(_BYTE_ORDER_MARK)
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([_neutralized(cell) for cell in header])
    writer.writerows([_neutralized(cell) for cell in row] for row in rows)
    return buffer.getvalue().encode("utf-8")


def csv_attachment(file: CsvFile) -> Response:
    return Response(
        content=file.content,
        media_type=CSV_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
            "Cache-Control": "no-store",
        },
    )


def local_day(moment: datetime) -> str:
    """Format the Brazil calendar day of `moment` as dd/mm/aaaa."""
    return brazilian_date(to_local_date(moment))


def local_minute(moment: datetime) -> str:
    """Format `moment` in Brazil time as dd/mm/aaaa HH:MM."""
    return moment.astimezone(LOCAL_TIMEZONE).strftime("%d/%m/%Y %H:%M")


def brazilian_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _neutralized(cell: str) -> str:
    return f"'{cell}" if cell.startswith(_FORMULA_PREFIXES) else cell
