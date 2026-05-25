"""
SET stock chart screenshot service.

Uses Playwright (headless Chromium, async API) to capture a TradingView
candlestick chart for any SET/MAI listed stock and returns it as a
base64-encoded PNG.
"""
from __future__ import annotations

import base64

# Interval label mapping
INTERVAL_LABELS: dict[str, str] = {
    "D":   "รายวัน",
    "W":   "รายสัปดาห์",
    "M":   "รายเดือน",
    "60":  "1 ชั่วโมง",
    "240": "4 ชั่วโมง",
}


async def capture_set_chart(symbol: str, interval: str = "D") -> dict:
    """
    Async: Screenshot a TradingView chart for a SET/MAI stock.

    Args:
        symbol:   Thai SET/MAI stock symbol, e.g. KBANK, PTT, CHASE
        interval: Timeframe — D (daily, default), W (weekly), M (monthly),
                  60 (1-hour), 240 (4-hour)

    Returns:
        dict with keys:
            label  (str)  — human-readable label
            base64 (str)  — PNG screenshot encoded as base64
            mime   (str)  — "image/png"
    """
    from playwright.async_api import async_playwright  # lazy import

    sym = symbol.upper().strip()
    ticker = f"SET%3A{sym}"
    url = (
        f"https://www.tradingview.com/chart/"
        f"?symbol={ticker}"
        f"&interval={interval}"
        f"&theme=dark"
        f"&style=1"
        f"&toolbar_bg=%23f1f3f6"
        f"&withdateranges=1"
        f"&hide_side_toolbar=0"
        f"&allow_symbol_change=1"
        f"&save_image=false"
    )

    label = f"📊 กราฟ {sym} ({INTERVAL_LABELS.get(interval, interval)}) — TradingView"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(6_000)   # wait for chart to fully render
            await page.keyboard.press("Escape")  # dismiss any popup/overlay
            await page.wait_for_timeout(1_000)
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
        finally:
            await browser.close()

    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return {"label": label, "base64": b64, "mime": "image/png"}
