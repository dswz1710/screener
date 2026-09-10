# NSE Equity Analyzer — Investment Desk

This repository is a rules-based Indian equity decision-support system. It is designed to help with **investment research, swing decisions and intraday setups**, while explicitly avoiding the claim that any signal can predict the market.

## What it now does

### 1. Investment engine
`investment_engine.py` ranks stocks using:
- business quality: ROE, margins, growth and leverage
- valuation: P/E, forward P/E and P/B
- technical trend: EMA20/50/200, RSI and momentum
- risk: volatility, drawdown and leverage checks
- relative strength versus Nifty 50

It produces **BUY / ACCUMULATE / WATCH / AVOID**, confidence, holding period, stop-loss/targets and a suggested quantity based on configurable capital and risk limits.

Default portfolio settings are deliberately conservative:
- capital: ₹1,00,000
- max position: 15%
- risk budget: 1% of capital per position

Override them in the workflow environment with `INVESTMENT_CAPITAL`, `MAX_POSITION_PCT` and `RISK_PER_POSITION_PCT`.

### 2. Market + chart engine
`intraday_analyzer.py` evaluates Nifty regime, daily trend, RSI, ATR, volume, VWAP and intraday price structure. A setup can be **NO TRADE** when the evidence is insufficient.

### 3. Daily Market Pulse
`daily_report.py` combines the engines into an investor-friendly report containing:
- market regime and key levels
- ranked trading opportunities
- ranked investment candidates
- thesis/metrics for the leading candidates
- intraday trigger / stop / target levels
- IPO radar status
- what changed today
- final action

### 4. Historical validation
`backtest.py` includes a rigorous momentum backtest with no look-ahead bias and a separately labelled approximate fundamental backtest. The latter must not be interpreted as proof of historical performance because current fundamentals are applied to historical dates.

## Automation
GitHub Actions runs the analyzer on trading days at:
- 08:45 IST — pre-open
- 09:15 IST — open
- 12:30 IST — midday
- 15:45 IST — post-market

The workflow runs the market/intraday engine, investment engine and daily report, then commits the generated files under `results/`.

## Dashboard
Open `dashboard/equity-analyzer.html` through GitHub Pages. It displays the latest market regime, investment ranking, trading setups, IPO status, changes and risk controls. Data refreshes automatically.

## IPO policy
IPO information is shown only when verified source data is available. **No GMP, subscription figure, anchor investor or IPO recommendation is fabricated.** GMP is an informal market indicator and is never used as the sole decision factor.

## Risk philosophy
The system is intended to improve process, not create certainty.

1. Never treat a score as a guarantee.
2. Position size from risk and stop distance, not from conviction alone.
3. Do not widen a stop after entry.
4. Do not average down automatically.
5. A broken fundamental thesis overrides a short-term technical signal.
6. Verify current prices, company filings, liquidity and material news before acting.
7. If data is missing or stale, prefer **WAIT** over a fabricated signal.

## Alerts
The original screener supports optional Telegram/email alerts. Keep alerts selective; high-frequency notifications are not a substitute for an investment process.

## Important limitation
The free `yfinance` data source can be incomplete, delayed or inconsistent for some fundamental fields. The analyzer therefore lowers confidence or skips a stock rather than inventing missing values.

**Decision-support only. Not financial advice. Markets are uncertain and losses are possible.**
