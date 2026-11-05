from app.sec_client import _extract_metrics, _html_to_text, _latest_annual_filing


def test_extracts_only_facts_from_the_selected_annual_filing() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "val": 1250,
                                "fy": 2025,
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "accn": "000001-25-000001",
                            },
                            {
                                "val": 900,
                                "fy": 2025,
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "accn": "000001-25-000002",
                            },
                        ]
                    }
                }
            }
        }
    }

    metrics = _extract_metrics(
        facts,
        fiscal_year=2025,
        period_end="2025-12-31",
        accession="000001-25-000001",
        cik="0000000001",
    )

    assert metrics["revenue"]["value"] == 1250
    assert metrics["revenue"]["source_url"].endswith(
        "/00000125000001/000001-25-000001.txt"
    )


def test_latest_annual_filing_includes_primary_report_document() -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-Q", "10-K", "8-K"],
                "filingDate": ["2026-02-01", "2026-02-15", "2026-03-01"],
                "accessionNumber": [
                    "000001-26-000001",
                    "000001-26-000002",
                    "000001-26-000003",
                ],
                "reportDate": ["2025-12-31", "2025-12-31", "2026-02-28"],
                "primaryDocument": ["quarterly.htm", "annual.htm", "current.htm"],
            }
        }
    }

    assert _latest_annual_filing(submissions) == (
        2025,
        "2025-12-31",
        "000001-26-000002",
        "annual.htm",
    )


def test_html_to_text_omits_script_and_style_content() -> None:
    text = _html_to_text(
        "<html><style>hidden style</style><body>Annual <b>report</b>"
        "<script>hidden script</script></body></html>"
    )

    assert text == "Annual report"
