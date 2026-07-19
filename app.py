import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_fetcher import get_market_data, get_crypto_data, fetch_ticker_data_sync
from analyzer import analyze_asset, analyze_crypto_asset, calculate_indicators
from mappings import TICKER_MAPPINGS

st.set_page_config(page_title="Cycle & Wave Scanner", layout="wide")

@st.cache_data(ttl=3600)
def load_and_scan_market():
    market_data = get_market_data()
    if "SPY" not in market_data:
        return pd.DataFrame(), market_data
        
    spy_data = market_data["SPY"]["1d"]
    results = []
    
    for ticker, data in market_data.items():
        if ticker == "SPY":
            continue
        res = analyze_asset(ticker, data["1d"], data["1h"], spy_data)
        results.append(res)
        
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_res = df_res.sort_values(by="score", ascending=False).reset_index(drop=True)
    return df_res, market_data

@st.cache_data(ttl=900) # Crypto is faster moving, 15 min cache
def load_and_scan_crypto():
    market_data = get_crypto_data()
    if "BTC-USD" not in market_data:
        return pd.DataFrame(), market_data
        
    btc_data = market_data["BTC-USD"]["1d"]
    results = []
    
    for ticker, data in market_data.items():
        if ticker == "BTC-USD":
            continue
        # MTF Logic: Pass 1d, 1h, and 15m. BTC acts as macro.
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
                
    # Add active FVG zones if requested (simplified as just lines here, or skip for performance)
    if 'active_bull_fvg_top' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['active_bull_fvg_top'], line=dict(color='green', dash='dot'), name='FVG Top'))
        fig.add_trace(go.Scatter(x=df.index, y=df['active_bull_fvg_bottom'], line=dict(color='green', dash='dot'), name='FVG Bottom'))
        
    fig.update_layout(title=f"{ticker} {timeframe} Institutional Chart", xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
    return fig

def main():
    st.title("🌊 Institutional Cycle & Wave Scanner (SMC Edition)")
    
    tab1, tab2, tab3 = st.tabs(["Top 100 Scanner", "Search & Analyze", "Top 25 Crypto Scanner"])
    
    # Highlight 'Good Entry' and 'STRONG BUY'
    def highlight_good_entry(s):
        return ['background-color: #d4edda; color: #155724; font-weight: bold;' if v in ['Good Entry', 'STRONG BUY'] else '' for v in s]
            
    with tab1:
        st.header("Top 100 US Equities Scanner")
        st.markdown("**Strict Confluence Requirements:** 1D Trend UP + Bullish Divergence + Liquidity Tap (FVG/Pin Bar/Engulfing)")
        
        if st.button("🔄 Force Fresh Market Scan"):
            load_and_scan_market.clear()
            
        with st.spinner("Fetching data asynchronously (Zero Lookahead)..."):
            scan_df, market_data = load_and_scan_market()
            
        if not scan_df.empty:
            styled_df = scan_df.style.apply(highlight_good_entry, subset=['signal', 'recommendation'])
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.warning("No data returned.")
            
    with tab3:
        st.header("Top 25 Crypto Scanner")
        st.markdown("**Strict Confluence Requirements:** 1D Trend UP + Bullish Divergence + Liquidity Tap (FVG/Pin Bar/Engulfing)")
        st.info("💡 **Smart Money Logic:** Bitcoin (`BTC-USD`) is acting as the macro-breadth filter for this tab. If Bitcoin's 1D Trend is DOWN, altcoins face a major conviction penalty.")
        
        if st.button("🔄 Force Fresh Crypto Scan"):
            load_and_scan_crypto.clear()
            
        with st.spinner("Fetching data asynchronously (Zero Lookahead)..."):
            crypto_df, crypto_data = load_and_scan_crypto()
            
        if not crypto_df.empty:
            styled_crypto_df = crypto_df.style.apply(highlight_good_entry, subset=['signal', 'recommendation'])
            st.dataframe(styled_crypto_df, use_container_width=True)
        else:
            st.warning("No data returned.")

    with tab2:
        st.header("Search Individual Ticker")
        
        # Smart Autocomplete
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
        
        # Session state for auto-run and persistence
        if "last_ticker" not in st.session_state:
            st.session_state.last_ticker = None
            
        ticker_changed = (search_ticker and search_ticker != st.session_state.last_ticker)
            
        if search_ticker and (analyze_clicked or ticker_changed):
            st.session_state.last_ticker = search_ticker
            with st.spinner("Fetching and analyzing..."):
                is_crypto = search_ticker.endswith("-USD")
                t, d1d, d1h, d15m = fetch_ticker_data_sync(search_ticker, fetch_15m=is_crypto)
                
                if 'market_data' in locals() and "SPY" in market_data:
                    spy_1d = market_data["SPY"]["1d"]
                else:
                    _, spy_1d, _, _ = fetch_ticker_data_sync("SPY")
                    
                if is_crypto:
                    _, btc_1d, _, _ = fetch_ticker_data_sync("BTC-USD")
                
                if d1d is not None and d1h is not None and spy_1d is not None:
                    if is_crypto and d15m is not None and btc_1d is not None:
                        res = analyze_crypto_asset(search_ticker, d1d, d1h, d15m, btc_1d)
                        header = f"MTF Institutional Crypto Analysis for {search_ticker}"
                    else:
                        res = analyze_asset(search_ticker, d1d, d1h, spy_1d)
                        header = f"Institutional Equity Analysis for {search_ticker}"
                        
                    df_1h_ind = calculate_indicators(d1h)
                    st.session_state.tab2_result = (header, res, df_1h_ind)
                else:
                    st.error("Failed to fetch data for ticker. Ensure it's a valid Yahoo Finance ticker (e.g., TSLA, BTC-USD).")
                    if "tab2_result" in st.session_state:
                        del st.session_state.tab2_result

        # Render the result if it exists and matches the current ticker
        if "tab2_result" in st.session_state and search_ticker == st.session_state.last_ticker and search_ticker:
            header, res, df_1h_ind = st.session_state.tab2_result
            st.subheader(header)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Recommendation", res["recommendation"])
            col2.metric("Signal", res["signal"])
            col3.metric("Predicted Upside", res["upside"])
            
            st.markdown("---")
            col4, col5, col6 = st.columns(3)
            col4.metric("Conviction Score", f"{res['score']}%")
            col5.metric("1D Trend", res["trend_1d"])
            col6.metric("1H Divergence", res["div_1h"])
            
            st.info(f"**Reason:** {res['reason']}")
            st.plotly_chart(plot_chart(df_1h_ind, search_ticker, "1H"), use_container_width=True)

if __name__ == "__main__":
    main()
