from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
import httpx
import psycopg

from app.config import get_settings
from app.models import AnalysisResponse, AnalyzeRequest
from app.repository import EvidenceRepository
from app.service import FinancialAnalysisService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repository = EvidenceRepository(settings.database_url)
    repository.initialize()
    app.state.analysis_service = FinancialAnalysisService(
        sec_user_agent=settings.sec_user_agent,
        database_url=settings.database_url,
        api_key=settings.gemini_api_key,
    )
    yield


app = FastAPI(
    title="Financial Health Analyzer",
    description="SEC-sourced financial analysis with RAG and Google ADK agents.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_company(
    request: AnalyzeRequest, http_request: Request
) -> AnalysisResponse:
    service: FinancialAnalysisService = http_request.app.state.analysis_service
    try:
        return await service.analyze(request.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve SEC data") from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Financial evidence database unavailable") from exc
