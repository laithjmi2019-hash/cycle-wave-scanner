import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_fetcher import get_market_data, fetch_ticker_data_sync
from analyzer import analyze_asset, calculate_indicators

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
    
    tab1, tab2 = st.tabs(["Top 100 Scanner", "Search & Analyze"])
    
    with tab1:
        st.header("Top 100 US Equities Scanner")
        st.markdown("**Strict Confluence Requirements:** 1D Trend UP + Bullish Divergence + Liquidity Tap (FVG/Pin Bar/Engulfing)")
        with st.spinner("Fetching data asynchronously (Zero Lookahead)..."):
            scan_df, market_data = load_and_scan_market()
            
        if not scan_df.empty:
            # Highlight 'Good Entry' specifically
            def highlight_good_entry(s):
                return ['background-color: #d4edda; color: #155724; font-weight: bold;' if v == 'Good Entry' else '' for v in s]
            
            styled_df = scan_df.style.apply(highlight_good_entry, subset=['signal'])
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.warning("No data returned.")

    with tab2:
        st.header("Search Individual Ticker")
        search_ticker = st.text_input("Enter Ticker (e.g. NVDA, TSLA):", "NVDA").upper()
        if st.button("Analyze"):
            with st.spinner("Fetching and analyzing..."):
                t, d1d, d1h = fetch_ticker_data_sync(search_ticker)
                
                if 'market_data' in locals() and "SPY" in market_data:
                    spy_1d = market_data["SPY"]["1d"]
                else:
                    _, spy_1d, _ = fetch_ticker_data_sync("SPY")
                
                if d1d is not None and d1h is not None and spy_1d is not None:
                    res = analyze_asset(search_ticker, d1d, d1h, spy_1d)
                    
                    st.subheader(f"Institutional Analysis for {search_ticker}")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Signal", res["signal"])
                    col2.metric("Conviction Score", f"{res['score']}%")
                    col3.metric("1D Trend", res["trend_1d"])
                    col4.metric("1H Divergence", res["div_1h"])
                    
                    st.info(f"**Reason:** {res['reason']}")
                    
                    df_1h_ind = calculate_indicators(d1h)
                    st.plotly_chart(plot_chart(df_1h_ind, search_ticker, "1H"), use_container_width=True)
                else:
                    st.error("Failed to fetch data for ticker.")

if __name__ == "__main__":
    main()
