#!/usr/bin/env python3
"""IPO radar for the NSE Equity Analyzer.

Pulls current IPO subscription data from a public market-data page when available,
keeps a transparent company-performance profile for the active IPOs, ranks them
for listing-interest vs long-term quality, and records recently listed IPOs.
GMP is explicitly treated as unofficial sentiment, never as a fundamental input.
"""
from __future__ import annotations
import json, math, re
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'; RESULTS.mkdir(exist_ok=True)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; NSE-Equity-Analyzer/1.0)'}
GROWW_URL='https://groww.in/ipo'

# Latest prospectus/company-performance notes. These are deliberately separated
# from live subscription fields so stale market-demand data cannot masquerade as
# company fundamentals.
PROFILES={
 'Kanohar Electricals': {'type':'Mainboard','sector':'Power equipment / transformers','revenue_fy24':276.69,'revenue_fy25':450.61,'revenue_fy26':653.84,'pat_fy24':17.75,'pat_fy25':65.12,'pat_fy26':129.73,'view':'CONSIDER','note':'Strong FY24-FY26 revenue and PAT growth; transformer/EPC exposure; large PSU/utility customer base.'},
 'Glass Wall Systems': {'type':'Mainboard','sector':'Building materials / façades','view':'WATCH','note':'Very strong subscription and GMP signal, but listing-demand indicators should not replace valuation and RHP checks.'},
 'Rentomojo': {'type':'Mainboard','sector':'Consumer rental / subscription','revenue_fy24':192.70,'revenue_fy25':265.96,'revenue_fy26':386.99,'pat_fy24':22.41,'pat_fy25':43.11,'pat_fy26':104.30,'view':'CONSIDER','note':'Strong revenue/PAT growth and recurring subscription model; rich valuation and legal/operational risks require caution.'},
 'Karamtara Engineering': {'type':'Mainboard','sector':'Renewables / transmission equipment','revenue_fy24':2425.15,'revenue_fy25':3158.44,'revenue_fy26':4311.98,'pat_fy24':102.65,'pat_fy25':139.33,'pat_fy26':228.75,'view':'CONSIDER','note':'Strong multi-year growth and renewable/transmission exposure; higher debt and commodity/regulatory sensitivity increase risk.'},
 'Manipal Payment and Identity Solutions': {'type':'Mainboard','sector':'Payments / identity','view':'WATCH','note':'Strong position in payment-card issuance, but current subscription is weak; assess growth and capital-deployment economics before applying.'},
 'LCC Projects': {'type':'Mainboard','sector':'Infrastructure / EPC','view':'WATCH','note':'Moderate subscription response; evaluate order book, cash conversion and debt before subscribing.'},
 'Asset Reconstruction': {'type':'Mainboard','sector':'Financial services / ARC','view':'WATCH','note':'Specialised financial-services business; subscription demand is currently weak, so fundamentals and valuation matter more than GMP.'},
 'Steamhouse India': {'type':'Mainboard','sector':'Engineering / industrial','view':'WATCH','note':'Early subscription demand is modest; wait for stronger institutional participation and verify earnings quality.'},
 'Veegaland Developers': {'type':'Mainboard','sector':'Real estate / leisure','view':'CONSIDER','note':'Kerala-focused real-estate/leisure developer; anchor participation and positive analyst commentary, but execution and concentration risks remain.'},
 'Prasol Chemicals': {'type':'Mainboard','sector':'Specialty chemicals','view':'WATCH','note':'Diversified specialty-chemical portfolio and global presence; valuation is demanding, so margin and earnings delivery matter.'},
}

# Current manually verified listing snapshot; refreshed as the tracker runs when
# the source exposes the listed table. This fallback prevents a blank dashboard.
LISTED_FALLBACK=[
 {'name':'Deepa Jewellers','type':'Mainboard','issue_price':177,'listing_open':221,'listing_close':194.37,'listing_gain_pct':24.86,'ltp':201.23,'today_gain_pct':-8.95,'subscription':42.61},
 {'name':'Rays of Belief','type':'Mainboard','issue_price':239,'listing_open':239,'listing_close':228.34,'listing_gain_pct':0.0,'ltp':229.81,'today_gain_pct':-3.85,'subscription':107.71},
 {'name':'Shanti Inorganics','type':'SME','issue_price':83,'listing_open':157.7,'listing_close':165.55,'listing_gain_pct':90.0,'ltp':167.80,'today_gain_pct':6.40,'subscription':132.30},
 {'name':'Phychem Technologies','type':'SME','issue_price':54,'ltp':53.07,'subscription':19.38},
 {'name':'Fly-Hi Maritime Travels','type':'SME','issue_price':102,'ltp':73.70,'subscription':2.07},
]

def num(x):
    if x is None: return None
    if isinstance(x,(int,float)): return float(x) if math.isfinite(float(x)) else None
    m=re.search(r'-?[0-9]+(?:\.[0-9]+)?',str(x).replace(',',''))
    return float(m.group()) if m else None

def fetch_tables():
    try:
        r=requests.get(GROWW_URL,headers=HEADERS,timeout=25); r.raise_for_status()
        return pd.read_html(r.text)
    except Exception as e:
        print('IPO source fetch failed:',e); return []

def normalize_tables(tables):
    open_rows=[]; listed_rows=[]
    for df in tables:
        cols=' '.join(str(c) for c in df.columns).lower()
        txt=' '.join(str(v) for v in df.head(3).astype(str).values.flatten()).lower()
        if 'subscription' in cols and ('open' in cols or 'close' in cols or 'company' in cols):
            for _,r in df.iterrows():
                row={str(k).strip().lower():v for k,v in r.to_dict().items()}
                name=next((str(v) for k,v in row.items() if 'company' in k and pd.notna(v)),None)
                if name and name not in ('Company Name','nan'): open_rows.append({'name':name,'raw':row})
        if 'listing' in cols and ('ltp' in cols or 'issue' in cols):
            for _,r in df.iterrows():
                row={str(k).strip().lower():v for k,v in r.to_dict().items()}
                name=next((str(v) for k,v in row.items() if 'company' in k and pd.notna(v)),None)
                if name and name not in ('Company Name','nan'): listed_rows.append({'name':name,'raw':row})
    return open_rows,listed_rows

def lookup(row,terms):
    for k,v in row.items():
        if any(t in k for t in terms): return v
    return None

def score(item):
    sub=item.get('subscription') or 0
    sub_score=min(100,20+math.log10(max(sub,0.05))*38) if sub>0 else 10
    gmp=item.get('gmp_pct')
    gmp_score=min(100,max(0,50+(gmp or 0)*1.2)) if gmp is not None else 50
    growth=item.get('pat_growth_pct')
    growth_score=min(100,max(20,50+(growth or 0)*0.8)) if growth is not None else 50
    base={'CONSIDER':75,'WATCH':55}.get(item.get('profile_view'),50)
    # Demand 35%, company performance 40%, unofficial GMP sentiment 10%, qualitative 15%.
    s=round(.35*sub_score+.40*growth_score+.10*gmp_score+.15*base,1)
    return s

def main():
    tables=fetch_tables(); open_rows,listed_rows=normalize_tables(tables)
    current=[]
    for x in open_rows:
        name=x['name']; match=next((k for k in PROFILES if k.lower() in name.lower() or name.lower() in k.lower()),None)
        p=PROFILES.get(match,{})
        sub=num(lookup(x['raw'],['overall subscription','subscription']))
        band=str(lookup(x['raw'],['issue price','price range']) or '')
        dates=str(lookup(x['raw'],['open date','close date','dates']) or '')
        item={'name':name,'type':p.get('type') or 'Unknown','sector':p.get('sector'),'subscription':sub,'price_band':band,'dates':dates,'profile_view':p.get('view','WATCH'),'company_note':p.get('note','Company-performance profile not yet mapped; verify the RHP before applying.'),'revenue_fy26':p.get('revenue_fy26'),'pat_fy26':p.get('pat_fy26'),'revenue_growth_pct':round((p['revenue_fy26']/p['revenue_fy25']-1)*100,1) if p.get('revenue_fy25') else None,'pat_growth_pct':round((p['pat_fy26']/p['pat_fy25']-1)*100,1) if p.get('pat_fy25') else None,'source':'Groww IPO dashboard + mapped company/RHP notes'}
        item['score']=score(item); item['verdict']='TOP PICK' if item['score']>=75 and item['profile_view']=='CONSIDER' else 'CONSIDER' if item['score']>=62 else 'WATCH'
        current.append(item)
    # If the live parser returns nothing, use a transparent current fallback.
    if not current:
        for f in LISTED_FALLBACK: pass
        for name,p in PROFILES.items():
            if name in ('Kanohar Electricals','Rentomojo','Karamtara Engineering','Glass Wall Systems','Manipal Payment and Identity Solutions','LCC Projects','Asset Reconstruction','Steamhouse India','Veegaland Developers','Prasol Chemicals'):
                current.append({'name':name,**{k:v for k,v in p.items()},'subscription':None,'score':score({'subscription':0,'profile_view':p.get('view'),'pat_growth_pct':None}),'verdict':'WATCH','source':'Profile fallback; live subscription unavailable'})
    current.sort(key=lambda x:x.get('score',0),reverse=True)
    listed=[]
    for x in listed_rows:
        name=x['name']; row=x['raw']; listed.append({'name':name,'issue_price':num(lookup(row,['issue price','issue'])), 'listing_open':num(lookup(row,['listing open','open'])), 'listing_close':num(lookup(row,['listing close','close'])), 'listing_gain_pct':num(lookup(row,['listing gain','gain'])), 'ltp':num(lookup(row,['ltp','last traded'])), 'today_gain_pct':num(lookup(row,['today gain'])), 'subscription':num(lookup(row,['total subscription','subscription']))})
    if not listed: listed=LISTED_FALLBACK
    payload={'generated_at':datetime.now().astimezone().isoformat(),'source':'Groww IPO dashboard; listed IPO fallback from verified market-data snapshot','open_ipos':current[:20],'trending':sorted(current,key=lambda x:(x.get('subscription') or 0),reverse=True)[:10],'top_picks':[x for x in current if x.get('verdict') in ('TOP PICK','CONSIDER')][:5],'recent_listings':listed[:10],'upcoming_focus':[{'name':'NSE','type':'Mainboard','status':'Upcoming','note':'Reuters reports the IPO subscription is planned for 17–21 Sep 2026 after the issue-size revision.'},{'name':'Reliance Jio','type':'Mainboard','status':'Upcoming / watch','note':'Track only once official price band and dates are announced.'}],'methodology':['Subscription measures demand, not intrinsic value.','Company-performance score uses latest mapped FY26 RHP/financial information where available.','GMP is unofficial and is not used as proof of value.','A TOP PICK means the model sees a favourable combination of demand and available fundamentals; it is not a guaranteed listing gain.'],'disclaimer':'IPO data can change during the bidding day. Verify NSE/BSE subscription, RHP financials, valuation, lot size and latest company disclosures before applying.'}
    (RESULTS/'ipo_latest.json').write_text(json.dumps(payload,indent=2,allow_nan=False,default=str),encoding='utf-8')
    print('IPO radar updated:',len(current),'open,',len(listed),'listed')
if __name__=='__main__': main()
