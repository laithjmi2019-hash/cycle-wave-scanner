import sys
import os
import yfinance as yf
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def get_catalyst_score(ticker: str) -> dict:
    res = {
        'score': 0.0,
        'risk_score': 0.0,
        'summary': 'No recent news.'
    }
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return res
            
        pos_score = 0.0
        neg_score = 0.0
        summaries = []
        
        pos_keywords = ['upgrade', 'buy', 'outperform', 'target raised']
        neg_keywords = config.TOXIC_KEYWORDS
        
        for item in news[:5]:
            title = item.get('title', '').lower()
            if any(k in title for k in pos_keywords):
                pos_score += 5.0
                summaries.append("Positive keyword found.")
            if any(k in title for k in neg_keywords):
                neg_score += 10.0
                summaries.append("Toxic keyword found.")
                
        res['score'] = min(10.0, pos_score)
        res['risk_score'] = min(10.0, neg_score)
        if summaries:
            res['summary'] = " | ".join(set(summaries))
            
    except:
        pass
        
    return res

def has_earnings_soon(ticker: str, hours: int = 72) -> bool:
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is not None and not cal.empty:
            if 'Earnings Date' in cal.index:
                dates = cal.loc['Earnings Date']
                if isinstance(dates, list) and len(dates) > 0:
                    earliest = dates[0]
                    if hasattr(earliest, 'tzinfo') and earliest.tzinfo is None:
                        earliest = earliest.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    diff = (earliest - now).total_seconds() / 3600.0
                    if 0 <= diff <= hours:
                        return True
    except:
        pass
    return False
