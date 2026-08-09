import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def classify_narrative(ticker: str) -> str:
    return config.TICKER_NARRATIVE.get(ticker, "unknown")

def get_narrative_peers(ticker: str) -> list:
    narr = classify_narrative(ticker)
    if narr == "unknown":
        return []
    return config.CRYPTO_NARRATIVES.get(narr, [])

def calc_narrative_momentum(peer_tickers: list, data_dict: dict) -> dict:
    res = {
        "narrative_trend": "MODERATE",
        "score": 0.0,
        "leaders": [],
        "laggards": []
    }
    return res
