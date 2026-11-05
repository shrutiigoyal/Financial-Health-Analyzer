import asyncio
from unittest.mock import AsyncMock, MagicMock

from google.adk.events import Event
from google.genai import types

from app.sec_client import CompanyFacts
from app.service import FinancialAnalysisService


def test_agent_run_reads_final_adk_event_response() -> None:
    event = MagicMock(spec=Event)
    event.is_final_response.return_value = True
    event.content = types.Content(
        role="model",
        parts=[types.Part(text="Verified assessment")],
    )

    class RunnerStub:
        async def run_async(self, **kwargs):
            del kwargs
            yield event

    service = object.__new__(FinancialAnalysisService)
    service.session_service = MagicMock()
    service.session_service.create_session = AsyncMock()
    service.runner = RunnerStub()
    company = CompanyFacts(
        ticker="TEST",
        company_name="Test Company",
        cik="0000000001",
        fiscal_year=2025,
        period_end="2025-12-31",
        metrics={},
        annual_report_text="",
        annual_report_url="https://www.sec.gov/example",
    )

    result = asyncio.run(service._run_agents(company, {}))

    assert result == "Verified assessment"
    service.session_service.create_session.assert_awaited_once()
