#!/usr/bin/env python3
"""Build a lightweight current-market context snapshot for the dashboard/report."""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'
UA='Mozilla/5.0 (compatible; NSE-Equity-Analyzer/1.0)'

SYMBOLS={
    'Brent crude':'BZ=F','USD/INR':'INR=X','India VIX':'^INDIAVIX','Nifty Bank':'^NSEBANK',
    'S&P 500':'^GSPC','Nasdaq':'^IXIC'
}

def quote(symbol):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol,safe="")}?range=5d&interval=1d'
    r=requests.get(url,headers={'User-Agent':UA},timeout=12); r.raise_for_status()
    d=r.json()['chart']['result'][0]
    q=d['indicators']['quote'][0]; closes=[x for x in q.get('close',[]) if x is not None]
    if not closes:return None
    last=closes[-1]; prev=closes[-2] if len(closes)>1 else None
    return {'value':last,'change_pct':((last/prev)-1)*100 if prev else None,'asof':dt.datetime.fromtimestamp(d['timestamp'][-1],dt.timezone.utc).isoformat()}

def rss_headlines():
    feeds=[
      ('Reuters India','https://feeds.reuters.com/reuters/INbusinessNews'),
      ('Moneycontrol','https://www.moneycontrol.com/rss/marketreports.xml'),
      ('Economic Times','https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms')]
    out=[]
    for source,url in feeds:
        try:
            text=requests.get(url,headers={'User-Agent':UA},timeout=10).text
            import re
            items=re.findall(r'<item>(.*?)</item>',text,re.S|re.I)
            for item in items[:6]:
                title=re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>',item,re.S|re.I)
                link=re.search(r'<link>(.*?)</link>',item,re.S|re.I)
                if title:
                    t=(title.group(1) or title.group(2) or '').strip()
                    t=re.sub(r'<.*?>','',t)
                    if t:out.append({'source':source,'title':t,'link':(link.group(1).strip() if link else '')})
        except Exception:
            continue
    return out[:12]

def main():
    now=dt.datetime.now(dt.timezone.utc).astimezone()
    data={'generated_at':now.isoformat(),'quotes':{},'headlines':[],'notes':[]}
    for name,sym in SYMBOLS.items():
        try:data['quotes'][name]=quote(sym)
        except Exception as e:data['notes'].append(f'{name}: unavailable')
    data['headlines']=rss_headlines()
    if data['quotes'].get('Brent crude',{}).get('change_pct',0) and data['quotes']['Brent crude']['change_pct']>=3:
        data['notes'].append('Oil is moving sharply higher; watch inflation, INR and rate-sensitive sectors.')
    if data['quotes'].get('USD/INR',{}).get('change_pct',0) and data['quotes']['USD/INR']['change_pct']>=0.5:
        data['notes'].append('Rupee weakness is elevated; importers and margin-sensitive sectors may face pressure.')
    (RESULTS/'market_context_latest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps(data,indent=2))

if __name__=='__main__':main()
