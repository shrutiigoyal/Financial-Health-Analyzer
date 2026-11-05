import os
from uuid import uuid4

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents import build_analysis_agent
from app.models import AnalysisResponse, FinancialMetric
from app.ratios import calculate_financial_ratios
from app.repository import EvidenceRepository
from app.sec_client import CompanyFacts, fetch_annual_facts

APP_NAME = "financial_analyzer"


class FinancialAnalysisService:
    def __init__(self, sec_user_agent: str, database_url: str, api_key: str) -> None:
        self.sec_user_agent = sec_user_agent
        self.repository = EvidenceRepository(database_url)
        self.session_service = InMemorySessionService()
        os.environ.setdefault("GOOGLE_API_KEY", api_key)
        self.runner = Runner(
            agent=build_analysis_agent(),
            app_name=APP_NAME,
            session_service=self.session_service,
        )

    async def analyze(self, ticker: str) -> AnalysisResponse:
        company = await fetch_annual_facts(ticker, self.sec_user_agent)
        report_source_ids = self.repository.store_facts(
            company.ticker,
            company.metrics,
            company.annual_report_text,
            company.fiscal_year,
            company.annual_report_url,
        )
        ratios = calculate_financial_ratios(
            {name: item["value"] for name, item in company.metrics.items()}
        )
        assessment = await self._run_agents(company, ratios)
        return self._response(company, ratios, assessment, report_source_ids)

    async def _run_agents(self, company: CompanyFacts, ratios: dict) -> str:
        user_id = "financial-analyzer"
        session_id = str(uuid4())
        await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={
                "ticker": company.ticker,
                "financial_facts": company.metrics,
                "financial_ratios": ratios,
            },
        )
        prompt = (
            f"Analyze {company.company_name} ({company.ticker}), fiscal year "
            f"{company.fiscal_year}, ending {company.period_end}.\n"
            f"SEC facts: {company.metrics}\nCalculated ratios: {ratios}\n"
            "Use the tools to retrieve and calculate evidence. Do not present this "
            "as investment advice."
        )
        final_text = ""
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "\n".join(
                    part.text for part in event.content.parts if part.text
                )
        if not final_text:
            raise RuntimeError("The financial analysis agents returned no assessment")
        return final_text

    @staticmethod
    def _response(
        company: CompanyFacts,
        ratios: dict,
        assessment: str,
        report_source_ids: list[str],
    ) -> AnalysisResponse:
        metrics = {
            name: FinancialMetric(
                value=item["value"],
                unit=item["unit"],
                fiscal_year=item["fiscal_year"],
                period_end=item["period_end"],
                source_id=item["source_id"],
                source_url=item["source_url"],
            )
            for name, item in company.metrics.items()
        }
        citations = {
            item["source_id"]: item["source_url"] for item in company.metrics.values()
        }
        citations.update(
            {source_id: company.annual_report_url for source_id in report_source_ids}
        )
        return AnalysisResponse(
            ticker=company.ticker,
            company_name=company.company_name,
            fiscal_year=company.fiscal_year,
            metrics=metrics,
            ratios=ratios,
            citations=citations,
            assessment=assessment,
        )
