import pytest

from app.ratios import calculate_financial_ratios


def test_calculates_margins_liquidity_debt_and_cash_flow() -> None:
    ratios = calculate_financial_ratios(
        {
            "revenue": 1000,
            "gross_profit": 400,
            "operating_income": 200,
            "net_income": 100,
            "current_assets": 500,
            "current_liabilities": 250,
            "total_debt": 300,
            "stockholders_equity": 600,
            "operating_cash_flow": 150,
            "capital_expenditures": 50,
        }
    )

    assert ratios["gross_margin"] == pytest.approx(0.4)
    assert ratios["operating_margin"] == pytest.approx(0.2)
    assert ratios["net_margin"] == pytest.approx(0.1)
    assert ratios["current_ratio"] == pytest.approx(2)
    assert ratios["debt_to_equity"] == pytest.approx(0.5)
    assert ratios["operating_cash_flow_to_net_income"] == pytest.approx(1.5)
    assert ratios["free_cash_flow"] == pytest.approx(100)
    assert ratios["free_cash_flow_margin"] == pytest.approx(0.1)


def test_missing_values_and_zero_denominators_are_reported_as_unavailable() -> None:
    ratios = calculate_financial_ratios(
        {
            "revenue": 0,
            "net_income": 10,
            "current_assets": 100,
            "current_liabilities": 0,
        }
    )

    assert ratios["net_margin"] is None
    assert ratios["current_ratio"] is None
    assert ratios["gross_margin"] is None
    assert ratios["free_cash_flow"] is None
