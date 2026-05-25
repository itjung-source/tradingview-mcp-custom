"""
SET Thailand Financial Data Service — via TradingView Screener API (direct urllib).

Fetches fundamental metrics, income statement, balance sheet, and
growth rates for Thai SET/MAI stocks by calling the TradingView scanner
endpoint directly with urllib (avoids requests-library async conflicts in FastMCP).

Data is the most recent fiscal quarter (FQ) + trailing twelve months (TTM).
All monetary values from TradingView Screener are in THB (บาท).
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

_URL = "https://scanner.tradingview.com/global/scan"
_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "authority": "scanner.tradingview.com",
}
_TIMEOUT = 15


def _fmt(val: Any, decimals: int = 2) -> str | None:
    """Format numeric value with commas."""
    if val is None:
        return None
    try:
        f = float(val)
        if decimals == 0:
            return f"{f:,.0f}"
        return f"{f:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def _pct(val: Any) -> str | None:
    """Format as percentage."""
    if val is None:
        return None
    try:
        return f"{float(val):.2f}%"
    except (TypeError, ValueError):
        return str(val)


def _mil(val: Any) -> str | None:
    """Convert THB -> million THB with commas."""
    if val is None:
        return None
    try:
        return f"{float(val) / 1_000_000:,.2f}"
    except (TypeError, ValueError):
        return str(val)


# Fundamental columns to query from TradingView Screener
_FUNDAMENTAL_COLS = [
    # Price
    "close", "change",
    # Market
    "market_cap_basic", "dividends_yield",
    # Valuation
    "price_earnings_ttm", "price_book_ratio",
    "price_sales_ratio", "enterprise_value_ebitda_ttm",
    # Profitability
    "gross_profit_margin_ttm", "net_profit_margin_ttm",
    "operating_margin_ttm", "return_on_equity",
    "return_on_assets", "return_on_invested_capital",
    # Income (most recent quarter, FQ)
    "total_revenue_fq", "gross_profit_fq", "operating_income_fq",
    "net_income_fq", "ebitda",
    # Income (TTM)
    "total_revenue_ttm", "net_income_ttm_yoy_growth", "net_income_yoy_growth_ttm",
    "revenue_yoy_growth_ttm",
    # EPS
    "earnings_per_share_basic_ttm", "earnings_per_share_diluted_ttm",
    "earnings_per_share_diluted_yoy_growth_ttm",
    "eps_diluted",
    "book_value_per_share_fq",
    # Balance sheet (FQ)
    "total_assets_fq", "total_liabilities_fq", "total_equity_fq",
    "cash_n_short_term_invest_fq",
    "short_term_debt_fq", "long_term_debt_fq",
    "net_debt",
    # Leverage
    "debt_to_equity", "current_ratio_fq",
    # Cash flow (TTM)
    "free_cash_flow", "capital_expenditures_ttm",
    "ebitda_ttm",
]


def _fetch_raw(ticker: str) -> dict[str, Any]:
    """
    Call TradingView scanner API directly with urllib and return
    a dict mapping column name -> value for the requested ticker.
    """
    payload = json.dumps({
        "markets": [],
        "symbols": {"tickers": [ticker]},
        "options": {"lang": "en"},
        "columns": _FUNDAMENTAL_COLS,
        "filter": [{"left": "is_primary", "operation": "equal", "right": True}],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1],
        "ignore_unknown_fields": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        _URL,
        data=payload,
        headers=_HEADERS,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    rows = body.get("data", [])
    if not rows:
        return {}

    values = rows[0].get("d", [])
    return dict(zip(_FUNDAMENTAL_COLS, values))


def get_set_financials(symbol: str) -> dict:
    """
    Fetch financial statements and key metrics for a Thai SET/MAI stock.

    Calls TradingView scanner API directly via urllib (no API key needed).
    Data represents: most recent fiscal quarter (FQ) + trailing twelve months (TTM).

    Args:
        symbol: SET/MAI stock symbol -- e.g. "FORTH", "PTT", "ADVANC", "KBANK"

    Returns:
        dict with:
          - symbol, exchange
          - valuation:    P/E, P/B, P/S, market cap, dividend yield
          - profitability: gross margin, net margin, ROE, ROA, ROIC
          - income_fq:    recent quarter revenue, gross profit, net income, EPS
          - income_ttm:   TTM revenue, net income, EBITDA, EPS
          - yoy_growth:   YoY revenue growth, net income growth, EPS growth
          - balance_fq:   total assets, equity, debt, cash (recent quarter)
          - cashflow:     free cash flow (TTM), capex
    """
    sym = symbol.upper().strip()
    ticker = f"SET:{sym}" if ":" not in sym else sym

    try:
        r = _fetch_raw(ticker)
    except Exception as e:
        return {"symbol": sym, "error": str(e)}

    if not r:
        return {"symbol": sym, "error": f"ไม่พบข้อมูลสำหรับ {ticker}"}

    def g(col: str):
        v = r.get(col)
        return None if (v is None or (isinstance(v, float) and str(v) == "nan")) else v

    return {
        "symbol": sym,
        "exchange": "SET Thailand",
        "note": "หน่วยเงิน: ล้านบาท (ยกเว้น EPS/Book Value = บาท/หุ้น, อัตราส่วน = %, เท่า)",
        "source": "TradingView Screener",

        "valuation": {
            "ราคาปัจจุบัน (บาท)":        _fmt(g("close"), 2),
            "เปลี่ยนแปลงวันนี้ (%)":      _pct(g("change")),
            "มูลค่าตลาด (ล้านบาท)":       _mil(g("market_cap_basic")),
            "P/E (เท่า)":                  _fmt(g("price_earnings_ttm"), 2),
            "P/B (เท่า)":                  _fmt(g("price_book_ratio"), 2),
            "P/S (เท่า)":                  _fmt(g("price_sales_ratio"), 2),
            "EV/EBITDA (เท่า)":            _fmt(g("enterprise_value_ebitda_ttm"), 2),
            "Dividend Yield (%)":          _pct(g("dividends_yield")),
        },

        "profitability": {
            "Gross Profit Margin TTM (%)": _pct(g("gross_profit_margin_ttm")),
            "Net Profit Margin TTM (%)":   _pct(g("net_profit_margin_ttm")),
            "Operating Margin TTM (%)":    _pct(g("operating_margin_ttm")),
            "ROE (%)":                     _pct(g("return_on_equity")),
            "ROA (%)":                     _pct(g("return_on_assets")),
            "ROIC (%)":                    _pct(g("return_on_invested_capital")),
        },

        "income_fq": {
            "คำอธิบาย":                    "ข้อมูลไตรมาสล่าสุด (Most Recent Fiscal Quarter)",
            "รายได้รวม FQ (ล้านบาท)":      _mil(g("total_revenue_fq")),
            "กำไรขั้นต้น FQ (ล้านบาท)":   _mil(g("gross_profit_fq")),
            "กำไรจากดำเนินงาน FQ (ล้านบาท)": _mil(g("operating_income_fq")),
            "กำไรสุทธิ FQ (ล้านบาท)":     _mil(g("net_income_fq")),
            "EPS (บาท)":                   _fmt(g("eps_diluted"), 4),
        },

        "income_ttm": {
            "คำอธิบาย":                    "Trailing Twelve Months (TTM)",
            "รายได้รวม TTM (ล้านบาท)":     _mil(g("total_revenue_ttm")),
            "EBITDA TTM (ล้านบาท)":        _mil(g("ebitda_ttm")),
            "EPS TTM (บาท)":               _fmt(g("earnings_per_share_diluted_ttm"), 4),
        },

        "yoy_growth": {
            "คำอธิบาย":                    "Year-over-Year Growth (%)",
            "รายได้รวม YoY (%)":           _pct(g("revenue_yoy_growth_ttm")),
            "กำไรสุทธิ YoY (%)":           _pct(g("net_income_yoy_growth_ttm")),
            "EPS YoY (%)":                 _pct(g("earnings_per_share_diluted_yoy_growth_ttm")),
        },

        "balance_fq": {
            "คำอธิบาย":                    "งบดุลไตรมาสล่าสุด (FQ)",
            "สินทรัพย์รวม FQ (ล้านบาท)":   _mil(g("total_assets_fq")),
            "หนี้สินรวม FQ (ล้านบาท)":     _mil(g("total_liabilities_fq")),
            "ส่วนของผู้ถือหุ้น FQ (ล้านบาท)": _mil(g("total_equity_fq")),
            "เงินสด & ลงทุนระยะสั้น (ล้านบาท)": _mil(g("cash_n_short_term_invest_fq")),
            "หนี้ระยะสั้น FQ (ล้านบาท)":   _mil(g("short_term_debt_fq")),
            "หนี้ระยะยาว FQ (ล้านบาท)":    _mil(g("long_term_debt_fq")),
            "Net Debt (ล้านบาท)":          _mil(g("net_debt")),
            "Book Value/Share (บาท)":      _fmt(g("book_value_per_share_fq"), 4),
        },

        "leverage": {
            "D/E Ratio (เท่า)":            _fmt(g("debt_to_equity"), 2),
            "Current Ratio (เท่า)":        _fmt(g("current_ratio_fq"), 2),
        },

        "cashflow": {
            "คำอธิบาย":                    "กระแสเงินสด TTM",
            "Free Cash Flow TTM (ล้านบาท)": _mil(g("free_cash_flow")),
            "CAPEX TTM (ล้านบาท)":         _mil(g("capital_expenditures_ttm")),
        },
    }
