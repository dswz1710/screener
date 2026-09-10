#!/usr/bin/env python3
"""Generate the investor-facing daily Market Pulse from the latest engines."""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; RESULTS=ROOT/'results'

def load(p): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def f(v,n=2):
    if v is None:return '—'
    try:return f'{float(v):.{n}f}'
    except:return str(v)
def plan(r):
    i=r.get('intraday') or {}
    d=i.get('intraday_direction','NO TRADE')
    if d=='NO TRADE':return 'Wait for confirmation','—','—','—','—'
    return ('Above trigger' if d.startswith('LONG') else 'Below trigger',f(i.get('trigger')),f(i.get('stop_loss')),f(i.get('target1')),f(i.get('target2')))
def changed(cur,prev):
    if not prev:return ['No prior investment report available.']
    out=[]; a=cur.get('market',{}); b=prev.get('market',{})
    for label,key in [('Regime','regime'),('Nifty','price'),('RSI','rsi')]:
        if a.get(key)!=b.get(key):out.append(f'{label}: {b.get(key,"—")} → {a.get(key,"—")}')
    old={x.get('ticker'):x for x in prev.get('ranked_opportunities',[])}
    for x in cur.get('ranked_opportunities',[])[:10]:
        o=old.get(x.get('ticker'))
        if o and o.get('view')!=x.get('view'):out.append(f'{x.get("name")}: {o.get("view")} → {x.get("view")}')
    return out or ['No major rule-based changes detected.']

def main():
    intr=load(RESULTS/'intraday_latest.json') or {}; inv=load(RESULTS/'investment_latest.json') or {}
    prevs=sorted(RESULTS.glob('daily_report_*.json')); prev=load(prevs[-1]) if prevs else None
    now=dt.datetime.now(dt.timezone.utc).astimezone(); label=now.strftime('%-d %B %Y')
    m=intr.get('market',{}); rows=intr.get('ranked_opportunities',[]); invrows=inv.get('ranked_investments',[])
    report=[f'## 🇮🇳 Market Pulse — {label}\n',f'**Analysis:** {intr.get("mode","—").upper()} · {intr.get("generated_at","—")}\n',f'### Market regime: **{m.get("regime","UNKNOWN")}**\n',f'Nifty **{f(m.get("price"))}** · Change **{f(m.get("change_pct"))}%** · RSI **{f(m.get("rsi"),1)}** · EMA20 **{f(m.get("ema20"))}** · EMA50 **{f(m.get("ema50"))}** · EMA200 **{f(m.get("ema200"))}**.\n',f'Support **{f(m.get("support"))}** · Major support **{f(m.get("major_support"))}** · Recovery **{f(m.get("recovery_zone"))}**.\n']
    report.append('### Market verdict\n'+('Avoid aggressive buying; use selective entries.' if m.get('regime')=='RISK-OFF' else 'Trend is supportive, but require confirmation.' if m.get('regime')=='RISK-ON' else 'Stay selective and wait for confirmation.')+'\n')
    report += ['---\n# 🎯 Trading opportunities\n','| Rank | Stock | Score | View | Trend | RSI | Change |','|---:|---|---:|---|---|---:|---:|']
    for n,r in enumerate(rows[:10],1):
        t=r.get('technical') or {}; report.append(f'| {n} | {r.get("name")} | {f(r.get("combined_score"),1)} | {r.get("view")} | {t.get("trend","—")} | {f(t.get("rsi"),1)} | {f(t.get("change_pct"))}% |')
    report.append('\n# 💰 Investment ranking\n')
    report.append('| Rank | Stock | Invest score | View | Quality | Valuation | Technical | Risk | 6M RS vs Nifty |\n|---:|---|---:|---|---:|---:|---:|---:|---:|')
    for n,r in enumerate(invrows[:15],1): report.append(f'| {n} | {r["name"]} | {f(r.get("investment_score"),1)} | **{r.get("view")}** | {f(r.get("quality_score"),1)} | {f(r.get("valuation_score"),1)} | {f(r.get("technical_score"),1)} | {f(r.get("risk_score"),1)} | {f(r.get("relative_strength_6m_pct"),1)}% |')
    if invrows:
        report.append('\n## 🏆 Best investment candidates\n')
        for n,r in enumerate(invrows[:5],1):
            report.append(f'### {"🥇" if n==1 else "🥈" if n==2 else "🥉" if n==3 else "▪️"} {r["name"]} — {r["view"]}\n')
            report.append(f'**Score:** {f(r.get("investment_score"),1)}/100 · **Confidence:** {r.get("confidence")} · **Holding:** {r.get("holding_period")}\n')
            report.append(f'Quality {f(r.get("quality_score"),1)} · Valuation {f(r.get("valuation_score"),1)} · Technical {f(r.get("technical_score"),1)} · Risk {f(r.get("risk_score"),1)} · 6M relative strength {f(r.get("relative_strength_6m_pct"),1)}%.\n')
            report.append(f'Price **₹{f(r.get("price"))}** · P/E {f(r.get("pe"))} · ROE {f(r.get("roe_pct"))}% · D/E {f(r.get("debt_to_equity"))} · Revenue growth {f(r.get("revenue_growth_pct"))}% · Earnings growth {f(r.get("earnings_growth_pct"))}%.\n')
            report.append(f'Risk-defined levels: SL **₹{f(r.get("stop_loss"))}** · T1 **₹{f(r.get("target1"))}** · T2 **₹{f(r.get("target2"))}**. Suggested quantity at configured capital/risk: **{r.get("suggested_shares",0)} shares**.\n')
    report.append('\n# ⚡ Intraday setups\n')
    longs=intr.get('top_long_setups',[]); shorts=intr.get('top_short_setups',[])
    report.extend([f'- **{r.get("name")}** — {r.get("intraday",{}).get("intraday_direction")} · trigger {f(r.get("intraday",{}).get("trigger"))} · SL {f(r.get("intraday",{}).get("stop_loss"))} · T1 {f(r.get("intraday",{}).get("target1"))} · T2 {f(r.get("intraday",{}).get("target2"))}' for r in (longs+shorts)[:8]] or ['- No confirmed setup. **NO TRADE is valid.**'])
    report.append('\n# 🚨 What to avoid\n- Chasing vertical moves.\n- Buying a weak fundamental business only because its chart is strong.\n- Averaging down without rechecking the thesis.\n- Any trade without a defined invalidation/stop.\n- Treating IPO GMP/headlines as standalone buy signals.\n')
    report.append('# 🆕 IPO RADAR\n'+('No verified IPO feed loaded; no IPO recommendation fabricated.' if not intr.get('ipo_radar') else json.dumps(intr['ipo_radar'],indent=2)))
    report.append('\n# 🧠 WHAT CHANGED TODAY?\n'+'\n'.join('- '+x for x in changed(intr,prev)))
    best=invrows[0] if invrows else None; besttrade=rows[0] if rows else None
    report.append('\n# 🏆 TODAY\'S FINAL CALL\n')
    report.append(f'- **Market:** {m.get("regime","UNKNOWN")}\n- **Best investment:** {best.get("name") if best else "None"}\n- **Investment view:** {best.get("view") if best else "No signal"}\n- **Best trading setup:** {besttrade.get("name") if besttrade else "None"}\n- **Top 3 investments:** {", ".join(x["name"] for x in invrows[:3]) or "None"}\n- **Overall action:** Do not force a trade; act only when price, risk and thesis agree.\n')
    report.append('\n> **Risk note:** This is decision-support software, not financial advice. Scores are heuristics, targets are estimates, and free-data fundamentals can be incomplete or delayed. Verify current NSE prices, company filings and liquidity before investing.\n')
    text='\n'.join(report); stamp=now.date().isoformat(); (RESULTS/f'daily_report_{stamp}.md').write_text(text,encoding='utf-8'); (RESULTS/'daily_report_latest.md').write_text(text,encoding='utf-8')
    print(text)
if __name__=='__main__':main()
