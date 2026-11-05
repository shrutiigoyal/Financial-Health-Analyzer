from collections.abc import Mapping


def calculate_financial_ratios(
    metrics: Mapping[str, float | None],
) -> dict[str, float | None]:
    revenue = metrics.get("revenue")
    gross_profit = metrics.get("gross_profit")
    operating_income = metrics.get("operating_income")
    net_income = metrics.get("net_income")
    current_assets = metrics.get("current_assets")
    current_liabilities = metrics.get("current_liabilities")
    total_debt = metrics.get("total_debt")
    equity = metrics.get("stockholders_equity")
    operating_cash_flow = metrics.get("operating_cash_flow")
    capital_expenditures = metrics.get("capital_expenditures")

    free_cash_flow = (
        operating_cash_flow - capital_expenditures
        if operating_cash_flow is not None and capital_expenditures is not None
        else None
    )

    return {
        "gross_margin": _divide(gross_profit, revenue),
        "operating_margin": _divide(operating_income, revenue),
        "net_margin": _divide(net_income, revenue),
        "current_ratio": _divide(current_assets, current_liabilities),
        "debt_to_equity": _divide(total_debt, equity),
        "operating_cash_flow_to_net_income": _divide(operating_cash_flow, net_income),
        "free_cash_flow": free_cash_flow,
        "free_cash_flow_margin": _divide(free_cash_flow, revenue),
    }


def _divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator
