import csv
import io
from datetime import UTC, date, datetime

import pytest

from app.core.csv_document import (
    CSV_MEDIA_TYPE,
    CsvFile,
    brazilian_date,
    csv_attachment,
    csv_document,
    local_day,
    local_minute,
)

BYTE_ORDER_MARK = b"\xef\xbb\xbf"


def _cells(document: bytes) -> list[list[str]]:
    text = document.removeprefix(BYTE_ORDER_MARK).decode("utf-8")
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))


def test_document_opens_in_brazilian_excel() -> None:
    document = csv_document(("Nome", "Situação"), [("José", "Ativa")])

    assert document.startswith(BYTE_ORDER_MARK)
    assert document.removeprefix(BYTE_ORDER_MARK) == (
        "Nome;Situação\r\nJosé;Ativa\r\n".encode()
    )


def test_separators_and_quotes_inside_a_value_stay_in_one_cell() -> None:
    value = 'Empresa; "Matriz"\nFilial'

    assert _cells(csv_document(("Nome",), [(value,)])) == [["Nome"], [value]]


def test_document_without_rows_keeps_the_header() -> None:
    assert _cells(csv_document(("Nome", "Tipo"), [])) == [["Nome", "Tipo"]]


@pytest.mark.parametrize(
    "value",
    ['=HYPERLINK("https://x.invalid")', "+1", "-1", "@SUM(A1)", "\tx", "\rx"],
)
def test_text_that_excel_would_run_as_a_formula_is_neutralized(value: str) -> None:
    assert _cells(csv_document(("Nome",), [(value,)]))[1] == [f"'{value}"]


def test_ordinary_text_is_kept_as_typed() -> None:
    assert _cells(csv_document(("Nome",), [("Maria-Clara 1",)]))[1] == ["Maria-Clara 1"]


def test_attachment_downloads_the_file_without_caching() -> None:
    response = csv_attachment(
        CsvFile(filename="cadastros-2026-10-26.csv", content=b"x")
    )

    assert response.body == b"x"
    assert response.media_type == CSV_MEDIA_TYPE
    assert response.headers["content-disposition"] == (
        'attachment; filename="cadastros-2026-10-26.csv"'
    )
    assert response.headers["cache-control"] == "no-store"


def test_dates_use_the_brazilian_calendar_day() -> None:
    # 01:30 UTC is still the previous evening in São Paulo (UTC-3).
    moment = datetime(2026, 10, 2, 1, 30, tzinfo=UTC)

    assert local_day(moment) == "01/10/2026"
    assert local_minute(moment) == "01/10/2026 22:30"
    assert brazilian_date(date(2026, 1, 5)) == "05/01/2026"
