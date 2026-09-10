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
def pct(v,n=1): return '—' if v is None else f'{f(v,n)}%'
def money(v): return '—' if v is None else f'₹{f(v)}'
def bar(v,width=12):
    try:
        x=max(0,min(100,float(v))); full=round(x/100*width); return '█'*full+'░'*(width-full)
    except:return '—'
def changed(cur,prev):
    if not prev:return ['No prior report snapshot available; future runs will compare against today.']
    out=[]; a=cur.get('market',{}); b=prev.get('market',{})
    for label,key in [('Regime','regime'),('Nifty','price'),('RSI','rsi')]:
        if a.get(key)!=b.get(key):out.append(f'{label}: {b.get(key,"—")} → {a.get(key,"—")}')
    old={x.get('ticker'):x for x in prev.get('ranked_opportunities',[])}
    for x in cur.get('ranked_opportunities',[])[:10]:
        o=old.get(x.get('ticker'))
        if o and o.get('view')!=x.get('view'):out.append(f'{x.get("name")}: {o.get("view")} → {x.get("view")}')
    return out or ['No major rule-based changes detected.']
def quote(ctx,name): return (ctx.get('quotes',{}).get(name) or {})
def main():
    intr=load(RESULTS/'intraday_latest.json') or {}; inv=load(RESULTS/'investment_latest.json') or {}; ctx=load(RESULTS/'market_context_latest.json') or {}; ipo=load(RESULTS/'ipo_latest.json') or {}
    prevs=sorted(RESULTS.glob('daily_snapshot_*.json')); prev=load(prevs[-1]) if prevs else None
    now=dt.datetime.now(dt.timezone.utc).astimezone(); label=now.strftime('%-d %B %Y')
    m=intr.get('market',{}); rows=intr.get('ranked_opportunities',[]); invrows=inv.get('ranked_investments',[])
    report=[f'## 🇮🇳 Market Pulse — {label}\n',f'**Scan:** {intr.get("mode","—").upper()} · **Engine timestamp:** {intr.get("generated_at","—")}\n',f'### Market regime: **{m.get("regime","UNKNOWN")}**\n',f'Nifty **{f(m.get("price"))}** · Change **{pct(m.get("change_pct"),2)}** · RSI **{f(m.get("rsi"),1)}** · EMA20 **{f(m.get("ema20"))}** · EMA50 **{f(m.get("ema50"))}** · EMA200 **{f(m.get("ema200"))}**.\n',f'**Support:** {f(m.get("support"))} · **Major support:** {f(m.get("major_support"))} · **Recovery:** {f(m.get("recovery_zone"))}.\n']
    report.append('### Market verdict\n'+('🟥 Avoid aggressive buying; protect capital and wait for confirmation.' if m.get('regime')=='RISK-OFF' else '🟩 Trend is supportive; still require price/volume confirmation.' if m.get('regime')=='RISK-ON' else '🟨 Stay selective; trade only when setup and risk agree.')+'\n')
    report += ['---\n# 🌐 Current market context\n','| Indicator | Latest | Change | Analyst read |','|---|---:|---:|---|']
    reads={'Brent crude':'Oil/inflation risk','USD/INR':'Rupee pressure','India VIX':'Volatility gauge','Nifty Bank':'Banking breadth','S&P 500':'Global risk cue','Nasdaq':'Global tech cue'}
    for name in ['Brent crude','USD/INR','India VIX','Nifty Bank','S&P 500','Nasdaq']:
        q=quote(ctx,name); report.append(f'| {name} | {f(q.get("value"))} | {pct(q.get("change_pct"),2)} | {reads[name]} |')
    if ctx.get('notes'): report.append('\n'+'\n'.join('- '+x for x in ctx['notes']))
    if ctx.get('headlines'):
        report.append('\n### 📰 Fresh market headlines\n')
        for h in ctx['headlines'][:8]: report.append(f'- **{h.get("source","Market")}:** {h.get("title","—")}')
    report += ['\n# 🎯 Trading opportunities\n','| # | Stock | Score | View | Trend | RSI | 1D | 20D | 60D | Trigger | SL | T1 | T2 | R/R |','|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,r in enumerate(rows[:15],1):
        t=r.get('technical') or {}; q=r.get('intraday') or {}; report.append(f'| {n} | **{r.get("name")}** | **{f(r.get("combined_score"),1)}** | **{r.get("view")}** | {t.get("trend","—")} | {f(t.get("rsi"),1)} | {pct(t.get("change_pct"),2)} | {pct(t.get("return20_pct"))} | {pct(t.get("return60_pct"))} | {f(q.get("trigger"))} | {f(q.get("stop_loss"))} | {f(q.get("target1"))} | {f(q.get("target2"))} | {f(q.get("risk_reward"),1)} |')
    report.append('\n### 📊 Opportunity score map\n')
    for r in rows[:10]: report.append(f'- **{r.get("name")}** `{bar(r.get("combined_score"))}` **{f(r.get("combined_score"),1)}/100** — {r.get("view")}')
    report += ['\n# 💼 Investment ranking\n','| # | Stock | Score | View | Quality | Valuation | Technical | Risk | 6M RS | P/E | ROE | D/E | Price | SL | Qty |','|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,r in enumerate(invrows[:20],1): report.append(f'| {n} | **{r["name"]}** | **{f(r.get("investment_score"),1)}** | **{r.get("view")}** | {f(r.get("quality_score"),1)} | {f(r.get("valuation_score"),1)} | {f(r.get("technical_score"),1)} | {f(r.get("risk_score"),1)} | {pct(r.get("relative_strength_6m_pct"))} | {f(r.get("pe"))} | {pct(r.get("roe_pct"))} | {f(r.get("debt_to_equity"))} | {money(r.get("price"))} | {money(r.get("stop_loss"))} | {r.get("suggested_shares","—")} |')
    if invrows:
        report.append('\n## 📈 Investment score cards\n')
        for n,r in enumerate(invrows[:5],1):
            report.append(f'### {"🥇" if n==1 else "🥈" if n==2 else "🥉" if n==3 else "▪️"} {r["name"]} — {r["view"]}\n')
            report.append(f'**{f(r.get("investment_score"),1)}/100** `{bar(r.get("investment_score"),20)}` · **Confidence:** {r.get("confidence","—")} · **Horizon:** {r.get("holding_period","—")}\n')
            report.append(f'| Metric | Score | Metric | Value |\n|---|---:|---|---:|\n| Quality | {f(r.get("quality_score"),1)} | P/E | {f(r.get("pe"))} |\n| Valuation | {f(r.get("valuation_score"),1)} | ROE | {pct(r.get("roe_pct"))} |\n| Technical | {f(r.get("technical_score"),1)} | D/E | {f(r.get("debt_to_equity"))} |\n| Risk | {f(r.get("risk_score"),1)} | Rev growth | {pct(r.get("revenue_growth_pct"))} |')
            report.append(f'\n**Levels:** Reference {money(r.get("price"))} · SL **{money(r.get("stop_loss"))}** · T1 **{money(r.get("target1"))}** · T2 **{money(r.get("target2"))}** · Position **{r.get("suggested_shares",0)} shares**.\n')
    report += ['\n# ⚡ Intraday setups\n','| Stock | Direction | Trigger | Stop | T1 | T2 | R/R |','|---|---|---:|---:|---:|---:|---:|']
    setups=(intr.get('top_long_setups',[])+intr.get('top_short_setups',[]))[:10]
    for r in setups:
        q=r.get('intraday') or {}; report.append(f'| **{r.get("name")}** | **{q.get("intraday_direction","NO TRADE")}** | {f(q.get("trigger"))} | {f(q.get("stop_loss"))} | {f(q.get("target1"))} | {f(q.get("target2"))} | {f(q.get("risk_reward"),1)} |')
    if not setups: report.append('| — | **NO TRADE** | — | — | — | — | — |')
    report += ['\n# 🚨 Risk / avoid\n','| Rule | Why it matters |','|---|---|','| No defined stop | Limits downside before entry |','| No chasing vertical moves | Poor risk/reward after expansion |','| No averaging down blindly | Thesis may be invalid |','| Reduce size in RISK-OFF | Volatility and false breakouts increase |','| IPO GMP is not a valuation proof | GMP is unofficial sentiment |']
    report.append('\n# 🆕 IPO radar\n')
    opens=ipo.get('open_ipos',[])
    if opens:
        report.append('| # | IPO | Price band | Subscription | Rev growth | PAT growth | Score | Verdict |\n|---:|---|---|---:|---:|---:|---:|---|')
        for n,x in enumerate(sorted(opens,key=lambda z:float(z.get('score') or 0),reverse=True)[:15],1): report.append(f'| {n} | **{x.get("name")}** | {x.get("price_band","—")} | {f(x.get("subscription"),2)}x | {pct(x.get("revenue_growth_pct"))} | {pct(x.get("pat_growth_pct"))} | **{f(x.get("score"),1)}** | **{x.get("verdict","WATCH")}** |')
        report.append('\n*IPO subscription measures demand, not quality. GMP is unofficial; verify the RHP and official exchange disclosures.*')
    else: report.append('No verified IPO feed available in this run.')
    report += ['\n# 🧠 What changed today?\n'+'\n'.join('- '+x for x in changed(intr,prev))]
    best=invrows[0] if invrows else None; besttrade=rows[0] if rows else None
    report += ['\n# 🏆 Today\'s final call\n',f'| Decision | Current view |\n|---|---|\n| Market | **{m.get("regime","UNKNOWN")}** |\n| Best investment | **{best.get("name") if best else "None"}** · {best.get("view") if best else "No signal"} |\n| Best trading setup | **{besttrade.get("name") if besttrade else "None"}** |\n| Top 3 investments | **{", ".join(x["name"] for x in invrows[:3]) or "None"}** |\n| Action | **Do not force a trade; wait for price + risk + thesis alignment.** |']
    report.append('\n> **Risk note:** Decision-support only, not financial advice. Scores are heuristics and data can be delayed or incomplete. Verify live prices, filings, liquidity and official IPO disclosures before acting.\n')
    text='\n'.join(report); stamp=now.date().isoformat(); (RESULTS/f'daily_report_{stamp}.md').write_text(text,encoding='utf-8'); (RESULTS/'daily_report_latest.md').write_text(text,encoding='utf-8')
    snap={'generated_at':now.isoformat(),'market':m,'ranked_opportunities':rows[:15]}; (RESULTS/f'daily_snapshot_{stamp}.json').write_text(json.dumps(snap,indent=2),encoding='utf-8'); (RESULTS/'daily_snapshot_latest.json').write_text(json.dumps(snap,indent=2),encoding='utf-8')
    print(text)
if __name__=='__main__':main()
