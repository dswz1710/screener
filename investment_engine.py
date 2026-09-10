#!/usr/bin/env python3
"""Investment decision layer for the NSE Equity Analyzer.

Designed for medium/long-term equity decisions. It deliberately separates
investment quality from intraday momentum and produces BUY / ACCUMULATE /
WATCH / AVOID decisions with valuation, quality, trend, risk and position-size
inputs. Missing data lowers confidence instead of being invented.
"""
from __future__ import annotations
import json, math, os
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parent; RESULTS=ROOT/'results'; RESULTS.mkdir(exist_ok=True)
WATCHLIST=['RELIANCE.NS','TCS.NS','HDFCBANK.NS','INFY.NS','ICICIBANK.NS','SBIN.NS','AXISBANK.NS','KOTAKBANK.NS','BHARTIARTL.NS','LT.NS','ITC.NS','MARUTI.NS','SUNPHARMA.NS','TITAN.NS','BAJFINANCE.NS','ASIANPAINT.NS','ULTRACEMCO.NS','NTPC.NS','ONGC.NS','OIL.NS','HAL.NS','TATASTEEL.NS','ADANIENT.NS','IRB.NS']
BENCH='^NSEI'
CAPITAL=float(os.getenv('INVESTMENT_CAPITAL','100000'))
MAX_POSITION=float(os.getenv('MAX_POSITION_PCT','0.15'))
RISK_PER_POSITION=float(os.getenv('RISK_PER_POSITION_PCT','0.01'))

def percentile_rank(values, reverse=False):
    s=pd.Series(values,dtype='float64'); r=s.rank(pct=True)
    return (1-r if reverse else r).to_dict()

def get_info(t):
    try:return yf.Ticker(t).info
    except Exception:return {}

def price_metrics(t):
    try:d=yf.download(t,period='1y',interval='1d',auto_adjust=False,progress=False)
    except Exception:return None
    if d.empty:return None
    if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
    d=d.dropna(subset=['Close','High','Low','Volume'])
    if len(d)<220:return None
    c=d.Close
    ema20=c.ewm(span=20,adjust=False).mean(); ema50=c.ewm(span=50,adjust=False).mean(); ema200=c.ewm(span=200,adjust=False).mean()
    delta=c.diff(); up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); dn=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean(); rs=up/dn.replace(0,np.nan); rsi=100-100/(1+rs)
    p=float(c.iloc[-1]); atr=float(pd.concat([d.High-d.Low,(d.High-c.shift()).abs(),(d.Low-c.shift()).abs()],axis=1).max(axis=1).rolling(14).mean().iloc[-1])
    return {'price':round(p,2),'rsi':round(float(rsi.iloc[-1]),1),'ema20':round(float(ema20.iloc[-1]),2),'ema50':round(float(ema50.iloc[-1]),2),'ema200':round(float(ema200.iloc[-1]),2),'atr':round(atr,2),'ret3m':round(float(c.pct_change(63).iloc[-1]*100),2),'ret6m':round(float(c.pct_change(126).iloc[-1]*100),2),'ret1y':round(float(c.pct_change(252).iloc[-1]*100),2),'from_high_pct':round(float((p/d.High.max()-1)*100),2),'vol_ratio':round(float(d.Volume.iloc[-1]/max(d.Volume.tail(20).mean(),1)),2)}

def fundamentals(t):
    i=get_info(t)
    return {'pe':i.get('trailingPE'),'forward_pe':i.get('forwardPE'),'pb':i.get('priceToBook'),'roe':i.get('returnOnEquity'),'roa':i.get('returnOnAssets'),'de':i.get('debtToEquity'),'profit_margin':i.get('profitMargins'),'revenue_growth':i.get('revenueGrowth'),'earnings_growth':i.get('earningsGrowth'),'dividend_yield':i.get('dividendYield'),'market_cap':i.get('marketCap'),'sector':i.get('sector'),'industry':i.get('industry')}

def valuation_score(f):
    pe=f.get('pe'); fpe=f.get('forward_pe'); pb=f.get('pb')
    score=50
    if isinstance(pe,(int,float)) and pe>0: score += 15 if pe<20 else 8 if pe<30 else -5 if pe<45 else -15
    if isinstance(fpe,(int,float)) and fpe>0 and isinstance(pe,(int,float)): score += 8 if fpe<pe else -4
    if isinstance(pb,(int,float)) and pb>0: score += 8 if pb<4 else 2 if pb<7 else -6
    return max(0,min(100,score))

def quality_score(f):
    score=50
    roe=f.get('roe'); de=f.get('de'); pm=f.get('profit_margin'); eg=f.get('earnings_growth'); rg=f.get('revenue_growth')
    if isinstance(roe,(int,float)): score += 15 if roe>=.20 else 8 if roe>=.12 else -5 if roe<.05 else 0
    if isinstance(de,(int,float)): score += 12 if de<60 else 5 if de<120 else -12 if de>200 else 0
    if isinstance(pm,(int,float)): score += 8 if pm>.15 else 3 if pm>.08 else -5 if pm<0 else 0
    if isinstance(eg,(int,float)): score += 8 if eg>.15 else 3 if eg>0 else -8
    if isinstance(rg,(int,float)): score += 7 if rg>.10 else 2 if rg>0 else -7
    return max(0,min(100,score))

def technical_score(p):
    score=50
    if p['price']>p['ema20']>p['ema50']>p['ema200']: score+=35
    elif p['price']>p['ema50']>p['ema200']: score+=25
    elif p['price']>p['ema200']: score+=12
    else: score-=15
    if 50<=p['rsi']<=68: score+=10
    elif 68<p['rsi']<=75: score+=3
    elif p['rsi']>75: score-=8
    else: score-=5
    if p['ret6m']>10: score+=8
    elif p['ret6m']<0: score-=5
    return max(0,min(100,score))

def risk_score(p,f):
    score=50
    if p['from_high_pct']>-5: score-=8
    if p['atr']/p['price']>.04: score-=10
    de=f.get('de')
    if isinstance(de,(int,float)) and de>200: score-=15
    return max(0,min(100,score))

def main():
    benchmark=price_metrics(BENCH) or {}
    records=[]
    for t in WATCHLIST:
        p=price_metrics(t)
        if not p: continue
        f=fundamentals(t); v=valuation_score(f); q=quality_score(f); tech=technical_score(p); risk=risk_score(p,f)
        rs=round(p['ret6m']-benchmark.get('ret6m',0),2) if benchmark else 0
        investment_score=round(.30*q+.25*v+.25*tech+.10*risk+.10*max(0,min(100,50+rs*2)),1)
        if investment_score>=80 and risk>=55: view='BUY'
        elif investment_score>=72: view='ACCUMULATE'
        elif investment_score>=62: view='WATCH'
        else: view='AVOID'
        stop=round(p['price']-1.5*p['atr'],2); t1=round(p['price']+2*p['atr'],2); t2=round(p['price']+4*p['atr'],2)
        per_share_risk=max(p['price']-stop,.01); risk_budget=CAPITAL*RISK_PER_POSITION; risk_size=math.floor(risk_budget/per_share_risk); cap_size=math.floor((CAPITAL*MAX_POSITION)/p['price']); shares=max(0,min(risk_size,cap_size))
        records.append({'ticker':t,'name':t.replace('.NS',''),'sector':f.get('sector'),'investment_score':investment_score,'view':view,'quality_score':q,'valuation_score':v,'technical_score':tech,'risk_score':risk,'relative_strength_6m_pct':rs,'price':p['price'],'rsi':p['rsi'],'ema20':p['ema20'],'ema50':p['ema50'],'ema200':p['ema200'],'atr':p['atr'],'ret3m_pct':p['ret3m'],'ret6m_pct':p['ret6m'],'ret1y_pct':p['ret1y'],'from_52w_high_pct':p['from_high_pct'],'pe':f.get('pe'),'forward_pe':f.get('forward_pe'),'pb':f.get('pb'),'roe_pct':round(f['roe']*100,2) if isinstance(f.get('roe'),(int,float)) else None,'debt_to_equity':f.get('de'),'revenue_growth_pct':round(f['revenue_growth']*100,2) if isinstance(f.get('revenue_growth'),(int,float)) else None,'earnings_growth_pct':round(f['earnings_growth']*100,2) if isinstance(f.get('earnings_growth'),(int,float)) else None,'stop_loss':stop,'target1':t1,'target2':t2,'suggested_shares':shares,'max_capital':round(shares*p['price'],2),'position_cap_pct':MAX_POSITION*100,'risk_budget':round(risk_budget,2),'confidence':'HIGH' if investment_score>=80 and min(q,v,tech)>=65 else 'MEDIUM' if investment_score>=65 else 'LOW','holding_period':'1–3 years' if view in ('BUY','ACCUMULATE') else 'watch / reassess'} )
    records.sort(key=lambda x:x['investment_score'],reverse=True)
    payload={'generated_at':pd.Timestamp.now(tz='Asia/Kolkata').isoformat(),'capital':CAPITAL,'risk_per_position_pct':RISK_PER_POSITION*100,'max_position_pct':MAX_POSITION*100,'benchmark':'NIFTY 50','benchmark_6m_return_pct':benchmark.get('ret6m'),'ranked_investments':records,'top_buys':[x for x in records if x['view']=='BUY'][:5],'accumulate':[x for x in records if x['view']=='ACCUMULATE'][:5],'risk_rules':['Position size is capped by both portfolio allocation and stop-loss risk.','Never risk more than the configured risk budget on one position.','Do not buy solely because the score is high; verify the latest result, valuation and catalyst.','Avoid averaging down unless the original thesis remains intact and valuation/risk have been reassessed.','A broken long-term thesis overrides a technical BUY signal.'],'methodology':{'quality':30,'valuation':25,'technical':25,'risk':10,'relative_strength':10},'disclaimer':'Decision-support only; scores are heuristics, not forecasts or guarantees. Fundamental fields from free market-data sources may be incomplete or delayed.'}
    (RESULTS/'investment_latest.json').write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'top_buys':payload['top_buys'],'accumulate':payload['accumulate']},indent=2))
if __name__=='__main__':main()
