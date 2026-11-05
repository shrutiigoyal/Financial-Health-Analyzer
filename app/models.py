from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    ticker: str = Field(
        min_length=1,
        max_length=10,
        pattern=r"^[A-Za-z0-9.-]+$",
        description="U.S. SEC-listed company ticker symbol",
    )


class FinancialMetric(BaseModel):
    value: float | None
    unit: str
    fiscal_year: int
    period_end: str
    source_id: str
    source_url: str


class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    fiscal_year: int
    metrics: dict[str, FinancialMetric]
    ratios: dict[str, float | None]
    citations: dict[str, str]
    assessment: str
