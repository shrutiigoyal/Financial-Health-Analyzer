from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import ToolContext

from app.config import get_settings
from app.ratios import calculate_financial_ratios
from app.repository import EvidenceRepository


def search_financial_evidence(query: str, tool_context: ToolContext) -> dict:
    """Search SEC-sourced financial evidence for the company under analysis."""
    ticker = str(tool_context.state["ticker"])
    repository = EvidenceRepository(get_settings().database_url)
    evidence = repository.search(ticker, query)
    return {"results": evidence}


def calculate_company_ratios(tool_context: ToolContext) -> dict:
    """Calculate financial ratios from the retrieved SEC-reported metrics."""
    facts = tool_context.state["financial_facts"]
    values = {name: item["value"] for name, item in facts.items()}
    return calculate_financial_ratios(values)


def build_analysis_agent() -> SequentialAgent:
    model = get_settings().gemini_model
    researcher = Agent(
        name="financial_researcher",
        model=model,
        description="Retrieves SEC evidence relevant to a company's financial health.",
        instruction=(
            "You are a financial research agent. Search the evidence store for revenue, "
            "profitability, liquidity, debt, and cash flows. Return concise notes with "
            "the exact evidence IDs and SEC URLs. Do not infer missing data. The company "
            "facts are {financial_facts}."
        ),
        tools=[search_financial_evidence],
        output_key="research_notes",
    )
    analyst = Agent(
        name="financial_analyst",
        model=model,
        description="Analyzes financial statements and calculates ratios.",
        instruction=(
            "Assess trends and financial health using only the supplied SEC evidence. "
            "Call calculate_company_ratios for the deterministic ratios. Explain what "
            "the available values indicate, note missing data and limitations, and "
            "cite claims with evidence IDs in square brackets. Research notes: "
            "{research_notes}. SEC facts: {financial_facts}."
        ),
        tools=[calculate_company_ratios],
        output_key="analysis_notes",
    )
    verifier = Agent(
        name="financial_verifier",
        model=model,
        description="Verifies evidence and citations in financial assessments.",
        instruction=(
            "Verify the analysis against the provided metrics and research notes. "
            "Reject unsupported claims, confirm citations match evidence IDs, and "
            "flag missing or potentially misleading comparisons. Return a concise "
            "investor-oriented assessment with source IDs and URLs. Research notes: "
            "{research_notes}. Analysis: {analysis_notes}. SEC facts: {financial_facts}."
        ),
        output_key="verified_assessment",
    )
    return SequentialAgent(
        name="financial_health_workflow",
        description="Researches, analyzes, and verifies a company's financial health.",
        sub_agents=[researcher, analyst, verifier],
    )
