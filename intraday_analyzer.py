#!/usr/bin/env python3
"""Advanced NSE equity decision-support engine.

Combines daily technical structure, intraday price action, relative strength,
volatility-based risk levels and a report schema suitable for the dashboard.
It does not predict prices or force trades: WAIT/NO TRADE is a valid result.
"""
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parent; RESULTS=ROOT/'results'; RESULTS.mkdir(exist_ok=True)
WATCHLIST=['RELIANCE.NS','TCS.NS','HDFCBANK.NS','INFY.NS','ICICIBANK.NS','SBIN.NS','AXISBANK.NS','KOTAKBANK.NS','BHARTIARTL.NS','LT.NS','ITC.NS','MARUTI.NS','SUNPHARMA.NS','TITAN.NS','BAJFINANCE.NS','ASIANPAINT.NS','ULTRACEMCO.NS','NTPC.NS','ONGC.NS','OIL.NS','HAL.NS','TATASTEEL.NS','ADANIENT.NS','HBLPOWER.NS','SHKTIMPL.NS','ATHERENERGY.NS','IRB.NS','ENVIRO.NS']
INDEX='^NSEI'; MIN_RR=2.0

def rsi(s,n=14):
 d=s.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean(); rs=up/dn.replace(0,np.nan); return 100-100/(1+rs)

def atr(d,n=14):
 pc=d.Close.shift(1); tr=pd.concat([d.High-d.Low,(d.High-pc).abs(),(d.Low-pc).abs()],axis=1).max(axis=1); return tr.rolling(n).mean()

def daily_metrics(ticker):
 d=yf.download(ticker,period='1y',interval='1d',auto_adjust=False,progress=False)
 if d.empty:return None
 if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
 d=d.dropna(subset=['Open','High','Low','Close','Volume']);
 if len(d)<220:return None
 d['ema20']=d.Close.ewm(span=20,adjust=False).mean(); d['ema50']=d.Close.ewm(span=50,adjust=False).mean(); d['ema200']=d.Close.ewm(span=200,adjust=False).mean(); d['rsi']=rsi(d.Close); d['atr']=atr(d); d['vol20']=d.Volume.rolling(20).mean(); d['high20']=d.High.rolling(20).max(); d['low20']=d.Low.rolling(20).min(); d['ret20']=d.Close.pct_change(20)*100; d['ret60']=d.Close.pct_change(60)*100
 x=d.iloc[-1]; prev=d.iloc[-2]; p=float(x.Close); a=float(x.atr)
 trend=sum([p>x.ema20,p>x.ema50,p>x.ema200]); momentum=60 if 50<=x.rsi<=72 else 45 if 40<=x.rsi<50 else 35 if x.rsi>72 else 25
 volume=15 if x.Volume>=1.5*x.vol20 else 8 if x.Volume>=x.vol20 else 0
 score=min(100,30+trend*15+momentum/5+volume+(10 if x.ret60>0 else 0))
 return d,{'price':round(p,2),'change_pct':round((p/float(prev.Close)-1)*100,2),'rsi':round(float(x.rsi),1),'ema20':round(float(x.ema20),2),'ema50':round(float(x.ema50),2),'ema200':round(float(x.ema200),2),'atr':round(a,2),'volume_ratio':round(float(x.Volume/max(x.vol20,1)),2),'return20_pct':round(float(x.ret20),2),'return60_pct':round(float(x.ret60),2),'52w_high':round(float(d.High.max()),2),'52w_low':round(float(d.Low.min()),2),'technical_score':round(float(score),1),'trend':'STRONG BULLISH' if trend==3 else 'BULLISH' if trend==2 else 'MIXED' if trend==1 else 'BEARISH'}

def intraday_metrics(ticker):
 try:d=yf.download(ticker,period='5d',interval='5m',auto_adjust=False,progress=False)
 except Exception:return None
 if d.empty:return None
 if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
 d=d.dropna(subset=['Open','High','Low','Close','Volume']);
 if len(d)<25:return None
 tp=(d.High+d.Low+d.Close)/3; d['vwap']=(tp*d.Volume).cumsum()/d.Volume.replace(0,np.nan).cumsum(); d['ema20']=d.Close.ewm(span=20,adjust=False).mean(); d['ema50']=d.Close.ewm(span=50,adjust=False).mean(); d['vol20']=d.Volume.rolling(20).mean(); x=d.iloc[-1]; p=float(x.Close); vr=float(x.Volume/max(x.vol20,1)); hi=float(d.High.tail(20).max()); lo=float(d.Low.tail(20).min()); v=float(x.vwap); e20=float(x.ema20); e50=float(x.ema50)
 long=30*(p>v)+20*(e20>e50)+25*(vr>=1.5)+15*(p>float(d.Close.iloc[-6]))+10*(p>=hi*.998); short=30*(p<v)+20*(e20<e50)+25*(vr>=1.5)+15*(p<float(d.Close.iloc[-6]))+10*(p<=lo*1.002)
 if long>=60 and long>=short: direction='LONG WATCH'; trigger=max(hi,v); sl=min(v,e20,lo*.995); score=long
 elif short>=60: direction='SHORT WATCH'; trigger=min(lo,v); sl=max(v,e20,hi*1.005); score=short
 else: direction='NO TRADE'; trigger=sl=None; score=max(long,short)
 if trigger is not None:
  risk=abs(trigger-sl); t1=trigger+(2*risk if 'LONG' in direction else -2*risk); t2=trigger+(3*risk if 'LONG' in direction else -3*risk); rr=3.0
 else:t1=t2=rr=None
 return {'intraday_price':round(p,2),'vwap':round(v,2),'intraday_ema20':round(e20,2),'intraday_ema50':round(e50,2),'intraday_volume_ratio':round(vr,2),'opening_range_high':round(hi,2),'opening_range_low':round(lo,2),'intraday_direction':direction,'intraday_score':int(score),'trigger':round(trigger,2) if trigger else None,'stop_loss':round(sl,2) if sl else None,'target1':round(t1,2) if t1 else None,'target2':round(t2,2) if t2 else None,'risk_reward':rr}

def market_context():
 q=daily_metrics(INDEX)
 if not q:return {'regime':'UNKNOWN'}
 _,m=q; regime='RISK-ON' if m['price']>m['ema50']>m['ema200'] else 'RISK-OFF' if m['price']<m['ema50']<m['ema200'] else 'SELECTIVE'
 return {**m,'regime':regime,'support':m['ema50'],'major_support':m['ema200'],'recovery_zone':round(m['ema20'],2)}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['preopen','open','midday','postmarket'],default='open'); mode=ap.parse_args().mode
 market=market_context(); rows=[]
 for t in WATCHLIST:
  try:
   q=daily_metrics(t)
   if not q:continue
   _,dm=q; im=intraday_metrics(t) if mode in ('open','midday') else None
   row={'ticker':t,'name':t.replace('.NS',''),'market':dm, 'technical':dm, 'intraday':im,'catalyst':None}
   combined=dm['technical_score'] if not im else round(.55*dm['technical_score']+.45*im['intraday_score'],1)
   row['combined_score']=combined; row['view']='BUY WATCH' if combined>=78 else 'BUY-ON-DIPS' if combined>=70 else 'WAIT' if combined>=55 else 'AVOID'
   rows.append(row)
  except Exception as e: rows.append({'ticker':t,'error':str(e)})
 rows.sort(key=lambda z:z.get('combined_score',0),reverse=True)
 payload={'generated_at':dt.datetime.now().astimezone().isoformat(),'mode':mode,'market':market,'ranked_opportunities':rows,'top_long_setups':[r for r in rows if r.get('intraday',{} ) and r['intraday'].get('intraday_direction','').startswith('LONG')][:5],'top_short_setups':[r for r in rows if r.get('intraday',{}) and r['intraday'].get('intraday_direction','').startswith('SHORT')][:5],'ipo_radar':[],'report_sections':['Market Pulse','Ranked Equity Opportunities','Chart/Technical Analysis','Intraday Long Setups','Intraday Short Setups','Buy/Sell/Stop Levels','IPO Radar','What Changed Today','Risk Controls','Final Call'],'risk_controls':['Risk a fixed small fraction of capital per trade; size from stop distance.','Never average down blindly.','Do not chase a vertical candle or breakout without volume confirmation.','Move to breakeven only after the setup has materially moved in your favour; do not widen stops.','If market regime is RISK-OFF, require stronger confirmation for longs.','If data is stale/missing, return WAIT rather than inventing a signal.'],'disclaimer':'Decision-support only; not financial advice. Targets are rule-based estimates, not predictions.'}
 stamp=dt.date.today().isoformat();
 for p in [RESULTS/f'intraday_{mode}_{stamp}.json',RESULTS/'intraday_latest.json']:p.write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
 print(json.dumps({'mode':mode,'market_regime':market.get('regime'),'top':rows[:10]},indent=2))
if __name__=='__main__':main()
