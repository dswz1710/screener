#!/usr/bin/env python3
"""Turn the latest analyzer JSON into a human-readable daily Market Pulse.

The report is intentionally decision-support: it ranks setups, explains the
technical evidence, gives rule-based levels, records changes from the prior
report, and never fabricates IPO/news facts.
"""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'

def f(v, n=2):
    return '—' if v is None else f'{float(v):.{n}f}'

def stock_plan(r):
    im=r.get('intraday') or {}
    dm=r.get('technical') or r.get('market') or {}
    direction=im.get('intraday_direction','NO TRADE')
    if direction=='NO TRADE':
        return {'entry':'Wait for confirmation','trigger':'—','stop':'—','t1':'—','t2':'—','rr':'—'}
    return {'entry': 'Above trigger' if direction.startswith('LONG') else 'Below trigger',
            'trigger':f(im.get('trigger')),'stop':f(im.get('stop_loss')),
            't1':f(im.get('target1')),'t2':f(im.get('target2')),
            'rr':f(im.get('risk_reward'))}

def why(r):
    t=r.get('technical') or {}; i=r.get('intraday') or {}
    parts=[t.get('trend','MIXED')]
    if t.get('rsi') is not None: parts.append(f"RSI {t['rsi']}")
    if t.get('return20_pct') is not None: parts.append(f"20D {t['return20_pct']}%")
    if t.get('volume_ratio') is not None: parts.append(f"daily vol {t['volume_ratio']}x")
    if i.get('intraday_direction') and i.get('intraday_direction')!='NO TRADE': parts.append(i['intraday_direction'])
    return ', '.join(parts)

def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

def changed_today(current, previous):
    if not previous: return ['No prior report available for comparison.']
    cm=current.get('market',{}); pm=previous.get('market',{})
    out=[]
    for label,key in [('Market regime','regime'),('Nifty','price'),('RSI','rsi')]:
        if cm.get(key)!=pm.get(key): out.append(f"{label}: {pm.get(key,'—')} → {cm.get(key,'—')}")
    old={x.get('ticker'):x for x in previous.get('ranked_opportunities',[])}
    for x in current.get('ranked_opportunities',[])[:5]:
        o=old.get(x.get('ticker'))
        if o and o.get('view')!=x.get('view'): out.append(f"{x.get('name')}: {o.get('view')} → {x.get('view')}")
    return out or ['No major rule-based ranking/view changes detected.']

def main():
    latest=load(RESULTS/'intraday_latest.json')
    if not latest: raise SystemExit('intraday_latest.json not found')
    prev_files=sorted(RESULTS.glob('daily_report_*.json'))
    previous=load(prev_files[-1]) if prev_files else None
    now=dt.datetime.now().astimezone(); date_label=now.strftime('%-d %B %Y')
    m=latest.get('market',{}); rows=latest.get('ranked_opportunities',[])
    top=rows[:10]
    best=top[0] if top else None
    longs=latest.get('top_long_setups',[])
    report=[]
    report.append(f"## 🇮🇳 Market Pulse — {date_label}\n")
    report.append(f"**Analysis run:** {latest.get('mode','unknown').upper()} · {latest.get('generated_at','—')}\n")
    report.append(f"### 🔴 Market regime: {m.get('regime','UNKNOWN')}\n")
    report.append(f"Nifty: **{f(m.get('price'))}** ({f(m.get('change_pct'))}%) · RSI **{f(m.get('rsi'),1)}** · EMA20 **{f(m.get('ema20'))}** · EMA50 **{f(m.get('ema50'))}** · EMA200 **{f(m.get('ema200'))}**.\n")
    report.append(f"Support: **{f(m.get('support'))}** · Major support: **{f(m.get('major_support'))}** · Recovery zone: **{f(m.get('recovery_zone'))}**.\n")
    if m.get('regime')=='RISK-OFF': verdict='Do not aggressively buy the market; prefer selective, confirmed setups.'
    elif m.get('regime')=='RISK-ON': verdict='Trend supports longs, but still require trigger + volume confirmation.'
    else: verdict='Use selective trades and wait for stronger confirmation around key levels.'
    report.append(f"### Market verdict\n{verdict}\n")
    report.append("---\n# 🎯 Today's ranked opportunities\n")
    report.append("| Rank | Stock | Score | Strategy | View | Trend | RSI | Change |")
    report.append("|---:|---|---:|---|---|---|---:|---:|")
    for n,r in enumerate(top,1):
        t=r.get('technical') or {}; report.append(f"| {n} | {r.get('name')} | {f(r.get('combined_score'),1)} | {r.get('intraday',{}).get('intraday_direction','SWING')} | {r.get('view')} | {t.get('trend','—')} | {f(t.get('rsi'),1)} | {f(t.get('change_pct'),2)}% |")
    for n,r in enumerate(top[:5],1):
        t=r.get('technical') or {}; p=stock_plan(r)
        report.append(f"\n## {'🥇' if n==1 else '🥈' if n==2 else '🥉' if n==3 else '▪️'} {r.get('name')} — {r.get('view')}\n")
        report.append(f"**Why it ranks #{n}:** {why(r)}.\n")
        report.append(f"**Plan:** {p['entry']} · Trigger **{p['trigger']}** · Stop-loss **{p['stop']}** · Target 1 **{p['t1']}** · Target 2 **{p['t2']}** · R/R **{p['rr']}**.\n")
        report.append(f"**Holding:** {'intraday' if r.get('intraday') else 'swing/watchlist'} · **Confidence:** {'HIGH' if r.get('combined_score',0)>=80 else 'MEDIUM' if r.get('combined_score',0)>=70 else 'LOW'} · **Risk:** {'High' if t.get('rsi',0)>72 else 'Normal'}\n")
        report.append(f"**Verdict:** {r.get('view')}. Do not chase; invalidation is the stop-loss.\n")
    report.append("\n# ⚡ Intraday setups\n")
    if longs:
        for r in longs[:5]:
            p=stock_plan(r); report.append(f"- **{r.get('name')}** — {r.get('intraday',{}).get('intraday_direction')} · trigger {p['trigger']} · SL {p['stop']} · T1 {p['t1']} · T2 {p['t2']} · score {r.get('intraday',{}).get('intraday_score','—')}")
    else: report.append('- No confirmed long setup. **NO TRADE is valid.**')
    report.append("\n# 🚨 What I would avoid today\n- Chasing vertical moves after large candles.\n- Longs that conflict with a RISK-OFF market without strong confirmation.\n- Any setup with stale/missing data or an undefined stop-loss.\n- Treating an IPO GMP or headline alone as a buy signal.\n")
    report.append("# 🆕 IPO RADAR\n")
    if latest.get('ipo_radar'):
        report.append('| IPO | Subscription | GMP | Listing score | Long-term score | Verdict |\n|---|---:|---:|---:|---:|---|')
        for x in latest['ipo_radar']:
            report.append(f"| {x.get('name','—')} | {x.get('subscription','—')} | {x.get('gmp','—')} | {x.get('listing_score','—')} | {x.get('long_term_score','—')} | {x.get('verdict','—')} |")
    else: report.append('No verified IPO feed loaded. **No IPO recommendation is fabricated.**')
    report.append("\n# 🧠 WHAT CHANGED TODAY?\n")
    report.extend([f"- {x}" for x in changed_today(latest,previous)])
    report.append("\n# 🏆 TODAY'S FINAL CALL\n")
    report.append(f"- **Market Regime:** {m.get('regime','UNKNOWN')}\n- **Best single setup:** {best.get('name') if best else 'None'}\n- **Top 3:** {', '.join(x.get('name','—') for x in top[:3]) or 'None'}\n- **Best IPO:** Only if verified in IPO radar\n- **Avoid:** chasing and low-conviction trades\n- **Overall action:** {'Selective / wait for confirmation' if m.get('regime')!='RISK-ON' else 'Selective longs with confirmation'}\n")
    report.append("\n> **Risk note:** This is a rules-based decision-support report, not financial advice. Targets are estimates derived from volatility/structure, not predictions. Always verify live NSE prices, spreads and liquidity before entering a trade.\n")
    text='\n'.join(report)
    stamp=now.date().isoformat()
    (RESULTS/f'daily_report_{stamp}.md').write_text(text,encoding='utf-8')
    (RESULTS/f'daily_report_{stamp}.json').write_text(json.dumps(latest,indent=2,default=str),encoding='utf-8')
    (RESULTS/'daily_report_latest.md').write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__': main()
