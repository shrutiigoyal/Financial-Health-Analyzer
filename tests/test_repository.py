from unittest.mock import MagicMock, patch

from app.repository import EvidenceRepository


def test_store_facts_bulk_inserts_through_psycopg_cursor() -> None:
    connection = MagicMock()
    cursor = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    metric = {
        "source_id": "SEC-0001-2025-revenue",
        "value": 100,
        "unit": "USD",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "source_url": "https://www.sec.gov/example",
        "concept": "Revenue",
    }

    with patch("app.repository.psycopg.connect", return_value=connection):
        source_ids = EvidenceRepository("postgresql://test").store_facts(
            ticker="TEST",
            metrics={"revenue": metric},
            annual_report_text="Revenue reported in annual filing.",
            fiscal_year=2025,
            annual_report_url="https://www.sec.gov/annual-report",
        )

    cursor.executemany.assert_called_once()
    assert source_ids == ["SEC-TEST-2025-annual-report-0000"]
