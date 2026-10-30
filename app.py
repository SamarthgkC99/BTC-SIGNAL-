import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"
COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "ignore"
]

st.set_page_config(page_title="BTC Momentum-Level Study", layout="wide")
st.title("BTC Momentum-Level Historical Study")
st.caption("Educational research only • No orders • No trade recommendations • Public historical market data")

with st.sidebar:
    st.header("Study settings")
    interval = st.selectbox("Candle timeframe", ["5m", "15m", "1h"], index=0)
    bars = st.slider("Historical candles", min_value=200, max_value=1000, value=500, step=100)
    atr_period = st.slider("ATR period", 5, 50, 14)
    impulse_atr = st.slider("Impulse body ≥ ATR ×", 0.5, 3.0, 1.2, 0.1)
    wick_body_ratio = st.slider("Rejection wick/body ratio ≥", 1.0, 4.0, 1.5, 0.1)
    close_edge_pct = st.slider("Strong close near candle edge (%)", 50, 95, 70, 5)
    min_spacing_atr = st.slider("Custom nearby-level filter: min spacing (ATR)", 0.25, 5.0, 1.0, 0.25)
    forward_bars = st.slider("Bars to observe after event", 3, 24, 6)
    auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=True)
    refresh = st.button("Fetch fresh data now", type="primary")
    if auto_refresh:
        st_autorefresh(interval=30_000, key="btc_market_auto_refresh")

@st.cache_data(ttl=20, show_spinner=False)
def fetch_klines(interval: str, limit: int):
    """Try public providers in order; normalize candles to one common schema."""
    errors = []
    headers = {"User-Agent": "BTC-Momentum-Level-Study/1.1", "Accept": "application/json"}

    # 1) Binance public Spot API host chain (same BTC/USDT market).
    for base in BINANCE_BASES:
        try:
            response = requests.get(
                f"{base}/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
                timeout=8, headers=headers,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, list) or not raw:
                raise ValueError("empty or unexpected response")
            df = pd.DataFrame(raw, columns=COLUMNS)
            for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
            df = _clean_candles(df)
            if len(df) >= 50:
                return df, f"Binance Spot ({base})", "USDT", errors
            raise ValueError(f"only {len(df)} usable candles")
        except Exception as exc:
            errors.append(f"Binance {base}: {type(exc).__name__}: {exc}")

    # 2) Coinbase public BTC-USD candles. This is a different quote market (USD),
    # and its REST endpoint returns at most 300 candles per request.
    try:
        seconds = {"5m": 300, "15m": 900, "1h": 3600}[interval]
        response = requests.get(
            COINBASE_CANDLES, params={"granularity": seconds},
            timeout=10, headers=headers,
        )
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, list) or not raw:
            raise ValueError("empty or unexpected response")
        # Coinbase order: [time, low, high, open, close, volume], newest first.
        cb = pd.DataFrame(raw, columns=["epoch", "low", "high", "open", "close", "volume"])
        cb["open_time"] = pd.to_datetime(pd.to_numeric(cb["epoch"]), unit="s", utc=True)
        cb["close_time"] = cb["open_time"] + pd.to_timedelta(seconds - 1, unit="s")
        cb["quote_volume"] = np.nan
        cb["trades"] = np.nan
        cb["taker_buy_base"] = np.nan
        cb["taker_buy_quote"] = np.nan
        cb["ignore"] = np.nan
        for col in ["open", "high", "low", "close", "volume"]:
            cb[col] = pd.to_numeric(cb[col], errors="coerce")
        cb = _clean_candles(cb[COLUMNS])
        if len(cb) >= 50:
            return cb.tail(limit).reset_index(drop=True), "Coinbase Exchange", "USD", errors
        raise ValueError(f"only {len(cb)} usable candles")
    except Exception as exc:
        errors.append(f"Coinbase: {type(exc).__name__}: {exc}")

    # 3) Kraken public OHLC. Also BTC/USD, so never silently label it USDT.
    try:
        response = requests.get(
            KRAKEN_OHLC, params={"pair": "XBTUSD", "interval": {"5m": 5, "15m": 15, "1h": 60}[interval]},
            timeout=10, headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise ValueError("; ".join(payload["error"]))
        result = payload.get("result", {})
        pair_key = next((k for k in result if k != "last"), None)
        raw = result.get(pair_key, []) if pair_key else []
        if not raw:
            raise ValueError("empty or unexpected response")
        # Kraken order: [time, open, high, low, close, vwap, volume, count].
        kr = pd.DataFrame(raw, columns=["epoch", "open", "high", "low", "close", "vwap", "volume", "trades"])
        kr["open_time"] = pd.to_datetime(pd.to_numeric(kr["epoch"]), unit="s", utc=True)
        kr["close_time"] = kr["open_time"] + pd.to_timedelta({"5m": 5, "15m": 15, "1h": 60}[interval] * 60 - 1, unit="s")
        kr["quote_volume"] = np.nan
        kr["taker_buy_base"] = np.nan
        kr["taker_buy_quote"] = np.nan
        kr["ignore"] = np.nan
        for col in ["open", "high", "low", "close", "volume"]:
            kr[col] = pd.to_numeric(kr[col], errors="coerce")
        kr = _clean_candles(kr[COLUMNS])
        if len(kr) >= 50:
            return kr.tail(limit).reset_index(drop=True), "Kraken Spot", "USD", errors
        raise ValueError(f"only {len(kr)} usable candles")
    except Exception as exc:
        errors.append(f"Kraken: {type(exc).__name__}: {exc}")

    raise RuntimeError("All public candle providers failed. Details: " + " | ".join(errors[-10:]))

def _clean_candles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open_time", "open", "high", "low", "close", "volume"])
    df = df.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    return df

if refresh:
    fetch_klines.clear()

try:
    with st.spinner("Loading public BTC candles with API fallback…"):
        df, data_source, quote_currency, provider_errors = fetch_klines(interval, bars)
except Exception as exc:
    st.error(f"Could not load public data: {exc}")
    st.info("Check your connection. The app tried several public candle endpoints and displays the failure details above.")
    st.stop()

# Keep the in-progress candle visible on the chart, but exclude it from calculations.
chart_df = df.copy()
now = pd.Timestamp.now(tz="UTC")
last_open = df["open_time"].iloc[-1]
interval_minutes = {"5m": 5, "15m": 15, "1h": 60}[interval]
last_candle_may_be_open = now < last_open + pd.Timedelta(minutes=interval_minutes)
if last_candle_may_be_open:
    df = df.iloc[:-1].copy().reset_index(drop=True)

if len(df) < 50:
    st.warning("Not enough fully closed candles after excluding the current candle.")
    st.stop()

# Volatility and candle measurements.
prev_close = df["close"].shift(1)
tr = pd.concat([
    df["high"] - df["low"],
    (df["high"] - prev_close).abs(),
    (df["low"] - prev_close).abs()
], axis=1).max(axis=1)
df["atr"] = tr.rolling(atr_period, min_periods=atr_period).mean()
df["body"] = (df["close"] - df["open"]).abs()
df["range"] = (df["high"] - df["low"]).replace(0, np.nan)
df["body_frac"] = df["body"] / df["range"]
df["close_position"] = (df["close"] - df["low"]) / df["range"]
df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]

# Provisional operational definition of an impulse:
# candle body is large relative to ATR. "Origin" is approximated as the candle open.
df["impulse"] = df["atr"].notna() & (df["body"] >= impulse_atr * df["atr"])
df["direction"] = np.where(df["close"] > df["open"], "Bullish",
                    np.where(df["close"] < df["open"], "Bearish", "Neutral"))

# Candidate momentum-origin levels, with configurable distance filter.
raw_levels = []
for i, row in df.iterrows():
    if bool(row["impulse"]) and pd.notna(row["atr"]):
        raw_levels.append({
            "index": int(i),
            "time": row["open_time"],
            "price": float(row["open"]),
            "direction": row["direction"],
            "atr": float(row["atr"]),
            "body": float(row["body"]),
        })

levels = []
for candidate in raw_levels:
    min_distance = min_spacing_atr * candidate["atr"]
    if not levels or all(abs(candidate["price"] - level["price"]) >= min_distance
                         for level in levels):
        levels.append(candidate)

# For each level, count later touches and study candle behaviour.
events = []
for level_no, level in enumerate(levels, start=1):
    li = level["index"]
    lvl = level["price"]
    for i in range(li + 1, len(df)):
        row = df.iloc[i]
        atr = row["atr"]
        if pd.isna(atr):
            continue
        # A touch means the candle range intersects the level.
        if row["low"] <= lvl <= row["high"]:
            body = max(float(row["body"]), 1e-12)
            bullish_rejection = (
                row["lower_wick"] / body >= wick_body_ratio
                and row["close"] > row["open"]
                and row["close_position"] >= 0.5
            )
            bearish_rejection = (
                row["upper_wick"] / body >= wick_body_ratio
                and row["close"] < row["open"]
                and row["close_position"] <= 0.5
            )
            edge = close_edge_pct / 100.0
            strong_bull_break = (
                row["close"] > lvl
                and row["open"] < lvl
                and row["body"] >= impulse_atr * atr
                and row["close_position"] >= edge
            )
            strong_bear_break = (
                row["close"] < lvl
                and row["open"] > lvl
                and row["body"] >= impulse_atr * atr
                and row["close_position"] <= (1 - edge)
            )
            if bullish_rejection:
                label = "Bullish rejection (candidate)"
            elif bearish_rejection:
                label = "Bearish rejection (candidate)"
            elif strong_bull_break:
                label = "Strong close above level (candidate)"
            elif strong_bear_break:
                label = "Strong close below level (candidate)"
            else:
                label = "Touch / no defined pattern"

            end_i = min(i + forward_bars, len(df) - 1)
            future = df.iloc[i + 1:end_i + 1]
            if len(future):
                # Descriptive forward movement only, not a trade return.
                forward_close_change_pct = (
                    (float(future["close"].iloc[-1]) / float(row["close"])) - 1
                ) * 100
                future_high_excursion_pct = (
                    (float(future["high"].max()) / float(row["close"])) - 1
                ) * 100
                future_low_excursion_pct = (
                    (float(future["low"].min()) / float(row["close"])) - 1
                ) * 100
            else:
                forward_close_change_pct = np.nan
                future_high_excursion_pct = np.nan
                future_low_excursion_pct = np.nan

            events.append({
                "level_id": level_no,
                "level_time": level["time"],
                "level_price": lvl,
                "origin_direction": level["direction"],
                "event_time": row["open_time"],
                "event_price": float(row["close"]),
                "pattern": label,
                "forward_close_change_pct": forward_close_change_pct,
                "future_high_excursion_pct": future_high_excursion_pct,
                "future_low_excursion_pct": future_low_excursion_pct,
            })
            # Avoid counting consecutive bars at the same level as repeated independent events.
            # Continue scanning after a short cooldown.
            break

events_df = pd.DataFrame(events)

latest = df.iloc[-1]
m1, m2, m3 = st.columns(3)
m1.metric("Last closed candle (UTC)", latest["open_time"].strftime("%Y-%m-%d %H:%M"))
m2.metric(f"Last closed candle close ({quote_currency})", f'{latest["close"]:,.2f}')
m3.metric("Candidate momentum levels", f"{len(levels)}")

if last_candle_may_be_open:
    live = chart_df.iloc[-1]
    st.info(
        f"A candle is currently forming (shown on the chart but excluded from calculations). "
        f"Open time: {live['open_time'].strftime('%Y-%m-%d %H:%M:%S UTC')} • "
        f"Open {live['open']:,.2f} / High {live['high']:,.2f} / "
        f"Low {live['low']:,.2f} / Latest close {live['close']:,.2f} {quote_currency}. "
        "The displayed close is provisional until the interval ends."
    )

st.caption(f"Active data source: {data_source} • Quote currency: {quote_currency} • Auto-refresh: {'on (30s)' if auto_refresh else 'off'}")
if provider_errors:
    with st.expander("API fallback diagnostics"):
        st.caption("Earlier endpoints in the fallback chain failed; the successful provider is shown above.")
        for item in provider_errors:
            st.text(item)

st.subheader("Historical price and candidate momentum-origin levels")
fig = go.Figure(data=[go.Candlestick(
    x=chart_df["open_time"], open=chart_df["open"], high=chart_df["high"],
    low=chart_df["low"], close=chart_df["close"], name=f"BTC/{quote_currency}"
)])
for n, level in enumerate(levels):
    fig.add_hline(
        y=level["price"], line_dash="dot", opacity=0.45,
        annotation_text=f"L{n+1} {level['direction']}",
        annotation_position="right"
    )
if not events_df.empty:
    for _, ev in events_df.iterrows():
        fig.add_trace(go.Scatter(
            x=[ev["event_time"]], y=[ev["event_price"]],
            mode="markers", marker={"size": 8},
            name=ev["pattern"], hovertemplate=(
                "%{x}<br>Price: %{y:.2f}<br>" + ev["pattern"] + "<extra></extra>"
            )
        ))
fig.update_layout(
    height=650, xaxis_rangeslider_visible=False,
    xaxis_title="Time (UTC)", yaxis_title=f"Price ({quote_currency})",
    legend_orientation="h"
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Method definition used in this prototype")
st.markdown("""
- **Impulse candle:** body size is at least the selected multiple of ATR.
- **Momentum origin:** approximated as the impulse candle's open. This is a placeholder definition, not yet confirmed as your intended origin.
- **Nearby-level filter:** keep a candidate only when it is at least the selected ATR distance from existing levels.
- **Rejection candle:** lower/upper wick relative to body, candle direction, and close location meet the selected thresholds.
- **Breakout candidate:** candle crosses the level, closes beyond it, has a large body relative to ATR, and closes near the candle edge.
- **Evaluation:** after the first later touch of each level, measure subsequent price excursions over the chosen number of bars. These are descriptive measurements, not simulated profit or validated trade results.
""")

st.subheader("Historical event study")
if events_df.empty:
    st.warning("No level-touch events met the current definitions in this sample. Try a wider level-spacing filter or a lower impulse threshold for research.")
else:
    st.dataframe(events_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download event-study CSV",
        data=events_df.to_csv(index=False).encode("utf-8"),
        file_name="btc_momentum_level_events.csv",
        mime="text/csv"
    )
    st.subheader("Descriptive outcomes by observed pattern")
    summary = events_df.groupby("pattern", dropna=False).agg(
        events=("pattern", "count"),
        avg_forward_close_change_pct=("forward_close_change_pct", "mean"),
        median_forward_close_change_pct=("forward_close_change_pct", "median"),
        avg_future_high_excursion_pct=("future_high_excursion_pct", "mean"),
        avg_future_low_excursion_pct=("future_low_excursion_pct", "mean"),
    ).reset_index()
    st.dataframe(summary.round(4), use_container_width=True, hide_index=True)

st.warning(
    "Research prototype only. It does not generate buy/sell instructions, place orders, "
    "or prove an edge. Fees, slippage, funding, survivorship/selection effects, and "
    "out-of-sample validation are not included. Public endpoint availability and terms may change."
)
st.caption("Public market-data only; no API key is required. Fallbacks may switch from BTC/USDT to BTC/USD, which is clearly labelled because exchange prices and quote currencies can differ.")
