from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from typing import Any
import re

import httpx


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

CONCEPTS: dict[str, tuple[tuple[str, ...], str]] = {
    "revenue": (
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
        "USD",
    ),
    "gross_profit": (("GrossProfit",), "USD"),
    "operating_income": (("OperatingIncomeLoss",), "USD"),
    "net_income": (("NetIncomeLoss",), "USD"),
    "current_assets": (("AssetsCurrent",), "USD"),
    "current_liabilities": (("LiabilitiesCurrent",), "USD"),
    "long_term_debt": (
        ("LongTermDebtAndFinanceLeaseObligations", "LongTermDebtNoncurrent"),
        "USD",
    ),
    "short_term_debt": (
        ("ShortTermBorrowings", "LongTermDebtCurrent"),
        "USD",
    ),
    "stockholders_equity": (("StockholdersEquity",), "USD"),
    "operating_cash_flow": (
        ("NetCashProvidedByUsedInOperatingActivities",),
        "USD",
    ),
    "capital_expenditures": (
        ("PaymentsToAcquirePropertyPlantAndEquipment",),
        "USD",
    ),
}


@dataclass(frozen=True)
class CompanyFacts:
    ticker: str
    company_name: str
    cik: str
    fiscal_year: int
    period_end: str
    metrics: dict[str, dict[str, Any]]
    annual_report_text: str
    annual_report_url: str


async def fetch_annual_facts(ticker: str, user_agent: str) -> CompanyFacts:
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(
        headers=headers, timeout=30, follow_redirects=True
    ) as client:
        ticker_response = await client.get(SEC_TICKERS_URL)
        ticker_response.raise_for_status()
        company = _find_company(ticker_response.json(), ticker)

        cik = str(company["cik_str"]).zfill(10)
        facts_response = await client.get(SEC_COMPANYFACTS_URL.format(cik=cik))
        facts_response.raise_for_status()
        submissions_response = await client.get(SEC_SUBMISSIONS_URL.format(cik=cik))
        submissions_response.raise_for_status()
        facts = facts_response.json()
        submissions = submissions_response.json()
        fiscal_year, period_end, accession, primary_document = _latest_annual_filing(
            submissions
        )
        report_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{primary_document}"
        )
        report_response = await client.get(report_url)
        report_response.raise_for_status()
        annual_report_text = _html_to_text(report_response.text)

    extracted = _extract_metrics(facts, fiscal_year, period_end, accession, cik)

    if "revenue" not in extracted:
        raise ValueError(f"No annual revenue data found for {ticker} in SEC company facts")

    if "long_term_debt" in extracted or "short_term_debt" in extracted:
        extracted["total_debt"] = _derived_metric(
            "total_debt",
            extracted.get("long_term_debt"),
            extracted.get("short_term_debt"),
        )

    return CompanyFacts(
        ticker=ticker.upper(),
        company_name=company["title"],
        cik=cik,
        fiscal_year=fiscal_year,
        period_end=period_end,
        metrics=extracted,
        annual_report_text=annual_report_text,
        annual_report_url=report_url,
    )


def _find_company(ticker_data: dict[str, dict[str, Any]], ticker: str) -> dict[str, Any]:
    normalized = ticker.upper()
    for company in ticker_data.values():
        if company["ticker"].upper() == normalized:
            return company
    raise ValueError(f"Ticker {ticker!r} was not found in the SEC company ticker list")


def _latest_annual_filing(
    submissions: dict[str, Any],
) -> tuple[int, str, str, str]:
    recent = submissions["filings"]["recent"]
    filings = [
        (index, filed)
        for index, (form, filed) in enumerate(zip(recent["form"], recent["filingDate"]))
        if form == "10-K"
    ]
    if not filings:
        raise ValueError("No 10-K filing was found for this SEC registrant")

    index, _ = max(filings, key=lambda item: item[1])
    accession = recent["accessionNumber"][index]
    period_end = recent["reportDate"][index]
    primary_document = recent["primaryDocument"][index]
    if not period_end or not primary_document:
        raise ValueError("The latest 10-K is missing its report date or primary document")
    fiscal_year = date.fromisoformat(period_end).year
    return fiscal_year, period_end, accession, primary_document


def _extract_metrics(
    facts: dict[str, Any],
    fiscal_year: int,
    period_end: str,
    accession: str,
    cik: str,
) -> dict[str, dict[str, Any]]:
    extracted: dict[str, dict[str, Any]] = {}
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
    accession_directory = accession.replace("-", "")
    filing_url = f"{filing_url}{accession_directory}/{accession}.txt"

    for metric_name, (concept_names, unit_name) in CONCEPTS.items():
        fact = _find_fact_value(
            us_gaap, concept_names, unit_name, fiscal_year, period_end, accession
        )
        if fact is not None:
            extracted[metric_name] = {
                "value": float(fact["val"]),
                "unit": unit_name,
                "fiscal_year": fiscal_year,
                "period_end": period_end,
                "source_id": f"SEC-{cik}-{fiscal_year}-{metric_name}",
                "source_url": filing_url,
                "concept": fact["concept"],
            }
    return extracted


def _find_fact_value(
    us_gaap: dict[str, Any],
    concept_names: tuple[str, ...],
    unit_name: str,
    fiscal_year: int,
    period_end: str,
    accession: str,
) -> dict[str, Any] | None:
    for concept_name in concept_names:
        concept = us_gaap.get(concept_name)
        if concept is None:
            continue
        entries = concept.get("units", {}).get(unit_name, [])
        matches = [
            item
            for item in entries
            if item.get("form") == "10-K"
            and item.get("fy") == fiscal_year
            and item.get("end") == period_end
            and item.get("accn", "").replace("-", "") == accession.replace("-", "")
            and (
                "start" not in item
                or 330 <= (date.fromisoformat(item["end"]) - date.fromisoformat(item["start"])).days <= 400
            )
        ]
        if matches:
            result = max(matches, key=lambda item: item.get("filed", ""))
            return {**result, "concept": concept_name}
    return None


class _FilingTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self, tag: str, _attrs: list[tuple[str, str | None]]
    ) -> None:
        del _attrs
        if tag.lower() in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _html_to_text(document: str) -> str:
    parser = _FilingTextParser()
    parser.feed(document)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _derived_metric(
    name: str,
    long_term: dict[str, Any] | None,
    short_term: dict[str, Any] | None,
) -> dict[str, Any]:
    values = [metric for metric in (long_term, short_term) if metric is not None]
    first = values[0]
    return {
        **first,
        "value": sum(metric["value"] for metric in values),
        "source_id": f"{first['source_id'].rsplit('-', 1)[0]}-{name}",
        "concept": "sum of reported long- and short-term debt",
    }
