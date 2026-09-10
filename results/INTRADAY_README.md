# Intraday Analyzer

The repository now supports four automated NSE analysis sessions in addition to the original daily screener.

## Schedule (IST)

- 08:45 — **Pre-open scan:** market context and setup universe.
- 09:15 — **Post-open scan:** price action, VWAP, EMA structure, volume and breakout/breakdown setups.
- 12:30 — **Midday scan:** continuation/reversal check and refreshed ranking.
- 15:45 — **Post-market review:** closing-state scan and next-session watchlist data.

## Output

`results/intraday_latest.json` always contains the latest session.

Each setup includes:

- direction: LONG WATCH / SHORT WATCH / NO TRADE
- setup score
- price, VWAP, EMA20 and EMA50
- 20-bar high/low
- volume ratio
- trigger
- stop loss
- target 1 / target 2
- risk/reward

The analyzer requires a clean setup and at least a 1:2 risk/reward profile; otherwise it returns **NO TRADE**. It is decision-support software, not a guaranteed prediction or investment recommendation.
