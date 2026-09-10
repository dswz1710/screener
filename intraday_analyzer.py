#!/usr/bin/env python3
"""
Intraday + post-market analysis layer for the NSE screener.

The script is deliberately decision-support oriented: it ranks setups and
calculates trigger/SL/targets from recent price action, but it never forces a
trade. A clean NO TRADE result is valid when conditions are weak.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

# Broader liquid universe for practical intraday scanning. Extend as needed.
INTRADAY_WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "BHARTIARTL.NS", "LT.NS",
    "ITC.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS",
    "ASIANPAINT.NS", "ULTRACEMCO.NS", "NTPC.NS", "ONGC.NS", "OIL.NS",
    "SHKTIMPL.NS", "ATHERENERGY.NS", "IRB.NS", "ENVIRO.NS",
]

MIN_RR = 2.0


def get_intraday(ticker: str) -> pd.DataFrame:
    """Download recent 5-minute data. Yahoo may return less history on some days."""
    try:
        df = yf.download(ticker, period="5d", interval="5m", auto_adjust=False, progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.title)
        needed = ["Open", "High", "Low", "Close", "Volume"]
        return df.dropna(subset=[c for c in needed if c in df.columns])
    except Exception:
        return pd.DataFrame()


def metrics(df: pd.DataFrame) -> dict | None:
    if len(df) < 25:
        return None
    x = df.copy()
    tp = (x["High"] + x["Low"] + x["Close"]) / 3.0
    x["vwap"] = (tp * x["Volume"]).cumsum() / x["Volume"].replace(0, np.nan).cumsum()
    x["ema20"] = x["Close"].ewm(span=20, adjust=False).mean()
    x["ema50"] = x["Close"].ewm(span=50, adjust=False).mean()
    x["vol_ma20"] = x["Volume"].rolling(20).mean()

    last = x.iloc[-1]
    recent = x.tail(20)
    high20 = float(recent["High"].max())
    low20 = float(recent["Low"].min())
    price = float(last["Close"])
    vwap = float(last["vwap"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    volume_ratio = float(last["Volume"] / last["vol_ma20"]) if last["vol_ma20"] else 0.0
    ret5 = float((price / float(x["Close"].iloc[-6])) - 1.0) * 100 if len(x) >= 6 else 0.0

    return {
        "price": round(price, 2),
        "vwap": round(vwap, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "high20": round(high20, 2),
        "low20": round(low20, 2),
        "volume_ratio": round(volume_ratio, 2),
        "return_5bar_pct": round(ret5, 2),
    }


def classify(m: dict) -> dict:
    p, v, e20, e50 = m["price"], m["vwap"], m["ema20"], m["ema50"]
    vr = m["volume_ratio"]
    breakout = p > m["high20"] * 0.998
    breakdown = p < m["low20"] * 1.002

    long_score = 0
    short_score = 0
    long_score += 30 if p > v else 0
    long_score += 20 if e20 > e50 else 0
    long_score += 25 if vr >= 1.5 else 0
    long_score += 15 if m["return_5bar_pct"] > 0 else 0
    long_score += 10 if breakout else 0

    short_score += 30 if p < v else 0
    short_score += 20 if e20 < e50 else 0
    short_score += 25 if vr >= 1.5 else 0
    short_score += 15 if m["return_5bar_pct"] < 0 else 0
    short_score += 10 if breakdown else 0

    if long_score >= short_score and long_score >= 60:
        direction = "LONG WATCH"
        trigger = round(max(m["high20"], v), 2)
        sl = round(min(v, e20, m["low20"] * 0.995), 2)
        risk = max(trigger - sl, 0.0)
        target1 = round(trigger + risk * 2.0, 2)
        target2 = round(trigger + risk * 3.0, 2)
        rr = 3.0 if risk > 0 else 0.0
        score = long_score
    elif short_score >= 60:
        direction = "SHORT WATCH"
        trigger = round(min(m["low20"], v), 2)
        sl = round(max(v, e20, m["high20"] * 1.005), 2)
        risk = max(sl - trigger, 0.0)
        target1 = round(trigger - risk * 2.0, 2)
        target2 = round(trigger - risk * 3.0, 2)
        rr = 3.0 if risk > 0 else 0.0
        score = short_score
    else:
        direction = "NO TRADE"
        trigger = sl = target1 = target2 = None
        rr = 0.0
        score = max(long_score, short_score)

    if rr and rr < MIN_RR:
        direction = "NO TRADE"

    return {
        **m,
        "direction": direction,
        "setup_score": score,
        "trigger": trigger,
        "stop_loss": sl,
        "target1": target1,
        "target2": target2,
        "risk_reward": rr,
    }


def run(mode: str) -> Path:
    rows = []
    for ticker in INTRADAY_WATCHLIST:
        df = get_intraday(ticker)
        m = metrics(df)
        if not m:
            continue
        row = classify(m)
        row["ticker"] = ticker
        rows.append(row)

    ranked = pd.DataFrame(rows)
    if not ranked.empty:
        ranked = ranked.sort_values(["direction", "setup_score"], ascending=[True, False])

    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    payload = {
        "generated_at": stamp,
        "mode": mode,
        "market": "NSE",
        "setups": ranked.to_dict(orient="records") if not ranked.empty else [],
    }

    path = RESULTS / f"intraday_{mode}_{dt.date.today().isoformat()}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (RESULTS / "intraday_latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preopen", "open", "midday", "postmarket"], default="open")
    args = parser.parse_args()
    print(run(args.mode))
