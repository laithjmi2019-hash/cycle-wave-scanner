import sys
import os
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def validate_ohlcv(df: pd.DataFrame, ticker: str, market: str) -> tuple[bool, list[str]]:
    if df is None or df.empty:
        return False, ["Dataframe is empty or None."]
    
    issues = []
    
    if not check_ohlc_integrity(df):
        issues.append("OHLC integrity failed (e.g. neg prices or Close outside H/L).")
        
    if not check_data_freshness(df, config.STALE_DATA_MINUTES):
        issues.append("Data is stale.")
        
    if not check_volume_quality(df, config.MIN_VOLUME_BARS):
        issues.append("Insufficient non-zero volume bars.")
        
    is_valid = len(issues) == 0
    return is_valid, issues

def check_data_freshness(df: pd.DataFrame, max_stale_minutes: int = 120) -> bool:
    if df.empty:
        return False
    last_idx = df.index[-1]
    if isinstance(last_idx, pd.Timestamp):
        now = pd.Timestamp.now(tz=last_idx.tzinfo) if last_idx.tzinfo else pd.Timestamp.now()
        diff = (now - last_idx).total_seconds() / 60
        return diff <= max_stale_minutes
    return True

def check_volume_quality(df: pd.DataFrame, min_nonzero_bars: int = 3) -> bool:
    if 'Volume' not in df.columns or len(df) < 5:
        return False
    recent_vols = df['Volume'].tail(5)
    nonzero_count = (recent_vols > 0).sum()
    return nonzero_count >= min_nonzero_bars

def check_ohlc_integrity(df: pd.DataFrame) -> bool:
    req_cols = ['Open', 'High', 'Low', 'Close']
    if not all(c in df.columns for c in req_cols):
        return False
    
    if (df[req_cols] < 0).any().any():
        return False
        
    if (df['Close'] > df['High']).any() or (df['Close'] < df['Low']).any():
        return False
        
    if (df['Open'] > df['High']).any() or (df['Open'] < df['Low']).any():
        return False
        
    return True
