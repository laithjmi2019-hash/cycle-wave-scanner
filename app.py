import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_fetcher import (
    get_regional_data, get_crypto_data, fetch_ticker_data_sync,
    US_EQUITIES, EU_EQUITIES, CHINA_EQUITIES, UAE_EQUITIES, CRYPTO
)
from analyzer import analyze_asset, analyze_crypto_asset, calculate_indicators
from mappings import TICKER_MAPPINGS

st.set_page_config(page_title="Cycle & Wave Scanner", layout="wide")

@st.cache_data(ttl=900)
def load_and_scan_region(tickers):
    market_data = get_regional_data(tickers)
    if "SPY" not in market_data:
        return pd.DataFrame(), market_data
        
    spy_data = market_data["SPY"]["1d"]
    results = []
    
    for ticker, data in market_data.items():
        if ticker == "SPY":
            continue
        res = analyze_asset(ticker, data["1d"], data["1h"], data["15m"], spy_data)
        results.append(res)
        
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_res = df_res.sort_values(by="score", ascending=False).reset_index(drop=True)
    return df_res, market_data

@st.cache_data(ttl=900)
def load_and_scan_crypto():
    market_data = get_crypto_data()
    if "BTC-USD" not in market_data:
        return pd.DataFrame(), market_data
        
    btc_data = market_data["BTC-USD"]["1d"]
    results = []
    
    for ticker, data in market_data.items():
        if ticker == "BTC-USD":
            continue
        res = analyze_crypto_asset(ticker, data["1d"], data["1h"], data["15m"], btc_data)
        results.append(res)
        
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_res = df_res.sort_values(by="score", ascending=False).reset_index(drop=True)
    return df_res, market_data

def plot_chart(df: pd.DataFrame, ticker: str, timeframe: str):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name='Price'))
                
    fig.update_layout(title=f"{ticker} {timeframe} Institutional Chart", xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
    return fig

def render_scanner_tab(title, df, desc):
    st.header(title)
    st.markdown(desc)
    
    if st.button(f"🔄 Force Fresh Scan ({title})", key=title):
        if "Crypto" in title:
            load_and_scan_crypto.clear()
        else:
            load_and_scan_region.clear()
            
    with st.spinner("Fetching data asynchronously..."):
        if "Crypto" in title:
            scan_df, _ = load_and_scan_crypto()
        else:
            scan_df, _ = load_and_scan_region(tuple(df)) # Tuple for caching
            
    if not scan_df.empty:
        cols_to_show = ['ticker','recommendation','signal','score','upside','stop_loss','rsi','bb_status','reason']
        cols_to_show = [c for c in cols_to_show if c in scan_df.columns]
        
        def highlight_signals(s):
            styles = []
            for v in s:
                if v in ['LONG SNIPER']:
                    styles.append('background-color: #d4edda; color: #155724; font-weight: bold;')
                elif v in ['SHORT SNIPER']:
                    styles.append('background-color: #f8d7da; color: #721c24; font-weight: bold;')
                elif v in ['LONG MOMENTUM']:
                    styles.append('background-color: #cce5ff; color: #004085; font-weight: bold;')
                elif v in ['SHORT MOMENTUM']:
                    styles.append('background-color: #fff3cd; color: #856404; font-weight: bold;')
                else:
                    styles.append('')
            return styles
            
        styled_df = scan_df[cols_to_show].style.apply(highlight_signals, subset=['signal','recommendation'])
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.warning("No data returned.")

def main():
    st.title("Cycle & Wave Scanner V11.0 (Apex Multi-Factor Engine)")
    
    t_us, t_eu, t_cn, t_uae, t_cr, t_search = st.tabs([
        "🇺🇸 US Equities", "🇪🇺 EU Equities", "🇨🇳 Chinese Equities", "🇦🇪 UAE Equities", "🪙 Crypto", "🔍 Search & Analyze"
    ])
    
    desc = "**V11 Apex Engine:** ADX Regime Detection + RSI<30 + Z-Score<-1.5 + VWAP + 1:2 R:R (Backtest-Proven)"
    
    with t_us:
        render_scanner_tab("Top 100 US Equities", US_EQUITIES, desc)
    with t_eu:
        render_scanner_tab("Top 75 EU Equities", EU_EQUITIES, desc)
    with t_cn:
        render_scanner_tab("Top 25 Chinese Equities", CHINA_EQUITIES, desc)
    with t_uae:
        render_scanner_tab("Top 25 UAE Equities", UAE_EQUITIES, desc)
    with t_cr:
        render_scanner_tab("Top 25 Crypto", CRYPTO, desc)

    with t_search:
        st.header("Search Individual Ticker")
        
        options = list(TICKER_MAPPINGS.keys()) + ["Other (Custom Ticker)"]
        selected_option = st.selectbox(
            "Search Company, Crypto, or Ticker (Type to filter):", 
            options,
            index=None,
            placeholder="Type 'Apple', 'Bitcoin', or 'AAPL'..."
        )
        
        search_ticker = None
        if selected_option == "Other (Custom Ticker)":
            search_ticker = st.text_input("Enter Custom Ticker Symbol (e.g. PLTR):", "").upper()
        elif selected_option:
            search_ticker = TICKER_MAPPINGS[selected_option]
            
        analyze_clicked = st.button("Analyze")
        
        if "last_ticker" not in st.session_state:
            st.session_state.last_ticker = None
            
        ticker_changed = (search_ticker and search_ticker != st.session_state.last_ticker)
            
        if search_ticker and (analyze_clicked or ticker_changed):
            st.session_state.last_ticker = search_ticker
            with st.spinner("Fetching and analyzing..."):
                is_crypto = search_ticker.endswith("-USD")
                t, d1d, d1h, d15m = fetch_ticker_data_sync(search_ticker, fetch_15m=True)
                
                _, spy_1d, _, _ = fetch_ticker_data_sync("SPY", fetch_15m=False)
                
                btc_1d = None
                if is_crypto:
                    _, btc_1d, _, _ = fetch_ticker_data_sync("BTC-USD", fetch_15m=False)
                
                if d1d is not None and d1h is not None and d15m is not None and spy_1d is not None:
                    if is_crypto and btc_1d is not None:
                        res = analyze_crypto_asset(search_ticker, d1d, d1h, d15m, btc_1d)
                        header = f"MTF Institutional Crypto Analysis — {search_ticker}"
                    else:
                        res = analyze_asset(search_ticker, d1d, d1h, d15m, spy_1d)
                        header = f"Institutional Equity Analysis — {search_ticker}"
                        
                    df_1h_ind = calculate_indicators(d1h)
                    st.session_state.tab2_result = (header, res, df_1h_ind)
                else:
                    st.error("Failed to fetch data for ticker. Ensure it's a valid Yahoo Finance ticker.")
                    if "tab2_result" in st.session_state:
                        del st.session_state.tab2_result

        if "tab2_result" in st.session_state and search_ticker == st.session_state.last_ticker and search_ticker:
            header, res, df_1h_ind = st.session_state.tab2_result
            st.subheader(header)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Recommendation", res["recommendation"])
            col2.metric("Signal", res["signal"])
            col3.metric("Conviction Score", f"{res['score']}%")
            
            st.markdown("---")
            col4, col5, col6, col7 = st.columns(4)
            col4.metric("Predicted Move", res.get("upside", "N/A"))
            col5.metric("Stop Loss", res.get("stop_loss", "N/A"))
            col6.metric("Risk/Reward", res.get("rr", "N/A"))
            
            st.markdown("---")
            col8, col9 = st.columns(2)
            col8.metric("RSI-14 Extreme", res.get("rsi", "N/A"))
            col9.metric("Bollinger Extremes", res.get("bb_status", "N/A"))
            
            st.info(f"**Reason:** {res['reason']}")
            st.plotly_chart(plot_chart(df_1h_ind, search_ticker, "1H"), use_container_width=True)

if __name__ == "__main__":
    main()
