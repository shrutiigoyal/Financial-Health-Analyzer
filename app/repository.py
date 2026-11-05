from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class EvidenceRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_evidence (
                    id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    search_vector TSVECTOR GENERATED ALWAYS AS
                        (to_tsvector('english', content)) STORED
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS financial_evidence_search_idx
                ON financial_evidence USING GIN (search_vector)
                """
            )

    def store_facts(
        self,
        ticker: str,
        metrics: dict[str, dict[str, Any]],
        annual_report_text: str,
        fiscal_year: int,
        annual_report_url: str,
    ) -> list[str]:
        rows = [
            (
                metric["source_id"],
                ticker,
                (
                    f"{ticker} {metric_name.replace('_', ' ')} for fiscal year "
                    f"{metric['fiscal_year']} ending {metric['period_end']}: "
                    f"{metric['value']} {metric['unit']}. SEC concept: {metric['concept']}."
                ),
                metric["source_url"],
                Jsonb(metric),
            )
            for metric_name, metric in metrics.items()
        ]
        report_chunks = _split_into_chunks(annual_report_text)
        report_id_prefix = f"SEC-{ticker}-{fiscal_year}-annual-report"
        rows.extend(
            (
                f"{report_id_prefix}-{index:04d}",
                ticker,
                chunk,
                annual_report_url,
                Jsonb(
                    {
                        "fiscal_year": fiscal_year,
                        "source_id": f"{report_id_prefix}-{index:04d}",
                        "source_type": "10-K annual report",
                    }
                ),
            )
            for index, chunk in enumerate(report_chunks)
        )
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO financial_evidence (id, ticker, content, source_url, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        source_url = EXCLUDED.source_url,
                        metadata = EXCLUDED.metadata
                    """,
                    rows,
                )
        return [row[0] for row in rows[len(metrics) :]]

    def search(self, ticker: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT id, content, source_url, metadata
                FROM financial_evidence
                WHERE ticker = %s
                  AND search_vector @@ websearch_to_tsquery('english', %s)
                ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC
                LIMIT %s
                """,
                (ticker, query, query, limit),
            ).fetchall()
        return [dict(row) for row in rows]


def _split_into_chunks(text: str, chunk_size: int = 1800, overlap: int = 200) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        if current and current_length + len(word) + 1 > chunk_size:
            chunks.append(" ".join(current))
            overlap_words: list[str] = []
            overlap_length = 0
            for previous_word in reversed(current):
                if overlap_length + len(previous_word) + 1 > overlap:
                    break
                overlap_words.append(previous_word)
                overlap_length += len(previous_word) + 1
            current = list(reversed(overlap_words))
            current_length = overlap_length
        current.append(word)
        current_length += len(word) + 1

    if current:
        chunks.append(" ".join(current))
    return chunks
