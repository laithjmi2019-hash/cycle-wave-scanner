"""
FULL DEEP VERIFICATION: 
1. Independently verify TTE.PA (SHORT SNIPER) and SGO.PA (LONG SNIPER)
2. Deep scan of all EU equities
3. Deep scan of all UAE equities
"""
import yfinance as yf
import pandas as pd
import ta
import warnings
warnings.filterwarnings("ignore")

EU_EQUITIES = [
    "ASML.AS", "MC.PA",   "NVO",     "SAP.DE",  "SHEL.L",  "AZN.L",   "NOVN.SW", "TTE.PA",  "HSBA.L",
    "OR.PA",   "SAN.PA",  "SIE.DE",  "ULVR.L",  "SU.PA",   "IBE.MC",  "AI.PA",   "ALV.DE",  "CDI.PA",  "BP.L",
    "BNP.PA",  "DTE.DE",  "AIR.PA",  "EL.PA",   "CS.PA",   "ITX.MC",  "MUV2.DE", "ZURN.SW", "RIO.L",
    "ENEL.MI", "BATS.L",  "IFX.DE",  "GSK.L",   "ADYEN.AS","ISP.MI",  "UBSG.SW", "BAS.DE",  "INGA.AS", "ABI.BR",
    "GLEN.L",  "REL.L",   "ABN.AS",  "SAF.PA",  "PRU.L",   "BMW.DE",  "MBG.DE",  "VOW3.DE",
    "NG.L",    "AD.AS",   "SSE.L",   "SGE.L",   "BARC.L",  "UCG.MI",  "SGO.PA",  "BAYN.DE", "HEIA.AS",
    "RWE.DE",  "ALC.SW",  "HOLN.SW", "LR.PA",   "NOKIA.HE","ERIC-B.ST","VOLV-B.ST","EQNR.OL", "KER.PA",  "DHL.DE"
]

UAE_EQUITIES = [
    "EMAAR.AE", "DIB.AE", "EMIRATESNBD.AE", "SALIK.AE", "TECOM.AE",
    "EMPOWER.AE", "DFM.AE", "ARMX.AE", "AIRARABIA.AE", "TABREED.AE", "DU.AE"
]

def compute(ticker):
    try:
        t   = yf.Ticker(ticker)
        d1h = t.history(period="60d", interval="1h", prepost=False)
        d1d = t.history(period="1y",  interval="1d", prepost=False)
        if len(d1h) < 30:
            return None

        c, h, l, v = d1h['Close'], d1h['High'], d1h['Low'], d1h['Volume']

        rsi      = ta.momentum.RSIIndicator(c, 14).rsi().iloc[-1]
        bb       = ta.volatility.BollingerBands(c, 20, 2)
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_upper = bb.bollinger_hband().iloc[-1]
        adx      = ta.trend.ADXIndicator(h, l, c, 14).adx().iloc[-1]
        atr      = ta.volatility.AverageTrueRange(h, l, c, 10).average_true_range().iloc[-1]
        vol_sma  = v.rolling(20).mean().iloc[-1]
        vol_ratio= v.iloc[-1] / vol_sma if vol_sma > 0 else 0
        zscore   = ((c - c.rolling(20).mean()) / c.rolling(20).std()).iloc[-1]
        vwap     = ((c * v).rolling(24).sum() / v.rolling(24).sum()).iloc[-1]
        macd_obj = ta.trend.MACD(c)
        macd_h   = macd_obj.macd_diff().iloc[-1]
        macd_p   = macd_obj.macd_diff().iloc[-2]
        price    = c.iloc[-1]

        sma200d = None
        if len(d1d) >= 200:
            sma200d = ta.trend.SMAIndicator(d1d['Close'], 200).sma_indicator().iloc[-1]

        ranging  = adx < 25
        trending = adx >= 25

        signal = "WAIT"
        reason = ""
        blocked_by = ""
        stop = target = 0

        if ranging and rsi < 30 and zscore < -1.5 and price <= bb_lower:
            if sma200d and price < sma200d * 0.90:
                signal = "BLOCKED"
                blocked_by = "Below 200D SMA >10%"
            else:
                signal = "LONG SNIPER"
                stop   = price - 2 * atr
                target = price + 4 * atr
                reason = f"RSI={rsi:.1f}, Z={zscore:.2f}, BB touched, VWAP={'below' if price<vwap else 'above'}"

        elif ranging and rsi > 70 and zscore > 1.5 and price >= bb_upper:
            signal = "SHORT SNIPER"
            stop   = price + 2 * atr
            target = price - 4 * atr
            reason = f"RSI={rsi:.1f}, Z={zscore:.2f}, BB extended"

        elif trending and price > bb_upper and vol_ratio > 1.5 and macd_h > 0 and macd_p <= 0:
            if sma200d and price < sma200d:
                signal = "BLOCKED"
                blocked_by = "Below 200D SMA"
            else:
                signal = "LONG MOMENTUM"
                stop   = price - 2 * atr
                target = price + 4 * atr
                reason = f"ADX={adx:.1f}, Vol={vol_ratio:.1f}x, MACD+"

        elif trending and price < bb_lower and vol_ratio > 1.5 and macd_h < 0 and macd_p >= 0:
            signal = "SHORT MOMENTUM"
            stop   = price + 2 * atr
            target = price - 4 * atr
            reason = f"ADX={adx:.1f}, Vol={vol_ratio:.1f}x, MACD-"

        near_long  = rsi < 35 and zscore < -1.0 and adx < 28
        near_short = rsi > 65 and zscore > 1.0  and adx < 28

        return {
            "ticker": ticker, "price": price, "rsi": round(rsi,1),
            "adx": round(adx,1), "zscore": round(zscore,2),
            "vol_ratio": round(vol_ratio,2),
            "regime": "RANGING" if ranging else "TRENDING",
            "at_lower": price <= bb_lower, "at_upper": price >= bb_upper,
            "below_vwap": price < vwap,
            "sma200d": round(sma200d,2) if sma200d else None,
            "above_200d": (price > sma200d) if sma200d else None,
            "signal": signal, "reason": reason, "blocked_by": blocked_by,
            "stop": round(stop,2), "target": round(target,2),
            "upside": f"+{((target-price)/price*100):.2f}%" if target and price else "N/A",
            "near_long": near_long, "near_short": near_short,
            "atr": round(atr, 4)
        }
    except Exception as e:
        return None

def print_full(r, label=""):
    p = r['price']
    print(f"\n  {'='*55}")
    print(f"  {r['ticker']} {label}")
    print(f"  {'='*55}")
    print(f"  Price:      {p:.4f}")
    print(f"  RSI-14:     {r['rsi']} {'<-- OVERSOLD' if r['rsi']<30 else ('<-- OVERBOUGHT' if r['rsi']>70 else '')}")
    print(f"  ADX:        {r['adx']} ({r['regime']})")
    print(f"  Z-Score:    {r['zscore']} {'<-- EXTREME LOW' if r['zscore']<-1.5 else ('<-- EXTREME HIGH' if r['zscore']>1.5 else '')}")
    print(f"  Volume:     {r['vol_ratio']}x avg")
    print(f"  BB:         {'AT LOWER BAND' if r['at_lower'] else ('AT UPPER BAND' if r['at_upper'] else 'Inside Bands')}")
    print(f"  VWAP:       {'below (bearish pressure)' if r['below_vwap'] else 'above'}")
    print(f"  200D SMA:   {r['sma200d']} | Price {'ABOVE' if r['above_200d'] else 'BELOW'} SMA")
    print(f"  ATR:        {r['atr']}")
    print(f"  ---- V11 VERDICT ----")
    if r['signal'] not in ["WAIT","BLOCKED",""]:
        print(f"  SIGNAL:     *** {r['signal']} ***")
        print(f"  Stop:       {r['stop']}")
        print(f"  Target:     {r['target']} ({r['upside']})")
        print(f"  Reason:     {r['reason']}")
    elif r['signal'] == "BLOCKED":
        print(f"  SIGNAL:     WAIT (BLOCKED: {r['blocked_by']})")
    else:
        print(f"  SIGNAL:     WAIT FOR EXTREME")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("STEP 1: INDEPENDENTLY VERIFY TELEGRAM SIGNALS")
    print("="*60)

    for ticker, label in [("TTE.PA", "SHORT SNIPER VERIFICATION"), ("SGO.PA", "LONG SNIPER VERIFICATION")]:
        r = compute(ticker)
        if r:
            print_full(r, f"[{label}]")
        else:
            print(f"\n  {ticker}: Could not fetch data.")

    print("\n\n" + "="*60)
    print("STEP 2: FULL EU EQUITY SCAN")
    print("="*60)
    print(f"  {'TICKER':<14} {'PRICE':>9} {'RSI':>5} {'ADX':>5} {'Z':>6} {'REGIME':<10} {'SIGNAL':<18}")
    print("  " + "-"*65)

    eu_signals, eu_near = [], []
    for ticker in EU_EQUITIES:
        r = compute(ticker)
        if not r: continue
        note = ""
        if r['signal'] not in ["WAIT","BLOCKED",""]: note = "<<< SIGNAL"
        elif r['near_long']:  note = "~ near long"
        elif r['near_short']: note = "~ near short"
        print(f"  {ticker:<14} {r['price']:>9.2f} {r['rsi']:>5} {r['adx']:>5} {r['zscore']:>6} {r['regime']:<10} {r['signal']:<18} {note}")
        if r['signal'] not in ["WAIT","BLOCKED",""]: eu_signals.append(r)
        if r['near_long'] or r['near_short']: eu_near.append(r)

    print("\n\n" + "="*60)
    print("STEP 3: FULL UAE EQUITY SCAN")
    print("="*60)
    print(f"  {'TICKER':<16} {'PRICE':>9} {'RSI':>5} {'ADX':>5} {'Z':>6} {'REGIME':<10} {'SIGNAL':<18}")
    print("  " + "-"*65)

    uae_signals, uae_near = [], []
    for ticker in UAE_EQUITIES:
        r = compute(ticker)
        if not r:
            print(f"  {ticker:<16} {'NO DATA':>9}")
            continue
        note = ""
        if r['signal'] not in ["WAIT","BLOCKED",""]: note = "<<< SIGNAL"
        elif r['near_long']:  note = "~ near long"
        elif r['near_short']: note = "~ near short"
        print(f"  {ticker:<16} {r['price']:>9.4f} {r['rsi']:>5} {r['adx']:>5} {r['zscore']:>6} {r['regime']:<10} {r['signal']:<18} {note}")
        if r['signal'] not in ["WAIT","BLOCKED",""]: uae_signals.append(r)
        if r['near_long'] or r['near_short']: uae_near.append(r)

    print("\n\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    all_sigs = eu_signals + uae_signals
    if all_sigs:
        print(f"\n  ACTIVE SIGNALS ({len(all_sigs)}):")
        for s in all_sigs:
            print(f"    [{s['signal']}] {s['ticker']} | RSI:{s['rsi']} | Z:{s['zscore']} | {s['upside']} | Stop:{s['stop']}")
    else:
        print("  No active signals found beyond what was already sent.")

    all_near = eu_near + uae_near
    if all_near:
        print(f"\n  NEAR-MISS (Developing, watch these) ({len(all_near)}):")
        for s in all_near:
            tag = "NEAR LONG" if s['near_long'] else "NEAR SHORT"
            print(f"    [{tag}] {s['ticker']} | RSI:{s['rsi']} | Z:{s['zscore']} | ADX:{s['adx']} ({s['regime']})")
    print()
