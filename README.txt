BTC/USDT Momentum-Level Historical Study
=========================================

Purpose
-------
A non-executing educational Streamlit app to inspect BTC/USDT historical 5-minute
candles, identify candidate momentum-origin levels, and describe what happened
after price first returned to a level.

Data
----
The app tries public candle providers in this order:
1. Binance Spot BTC/USDT host fallback chain (`data-api.binance.vision`, `api.binance.com`,
   `api-gcp.binance.com`, and `api1` through `api4.binance.com`).
2. Coinbase Exchange public BTC-USD candles.
3. Kraken public BTC/USD OHLC.

Binance market-data-only documentation:
https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
Coinbase candles documentation:
https://api.exchange.coinbase.com/products/BTC-USD/candles
Kraken OHLC documentation:
https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/

No API key is needed. The app displays which provider succeeded and the quote
currency. Coinbase/Kraken fallback data is BTC/USD, not BTC/USDT, so the currency
is labelled honestly and prices may differ slightly between exchanges. The app
does not connect to an account, request credentials, or place orders.

The app can auto-refresh every 30 seconds. It shows the in-progress candle on
the chart as provisional, but excludes that candle from the historical calculations
until the candle interval has closed. A manual refresh button is also available.

Important provisional assumptions
---------------------------------
1. "Impulse" is approximated as candle body >= selected ATR multiple.
2. "Impulse origin" is provisionally the impulse candle's open.
3. Nearby levels are filtered using a configurable minimum ATR spacing.
4. Rejection candles use configurable wick/body and close-location conditions.
5. Breakout candidates require a strong body, a close beyond the level, and a
   close near the candle edge.
6. After a level's first later touch, the app records forward price movement over
   a chosen horizon. This is not a trading return and does not prove profitability.

These definitions are starting assumptions because "origin of a momentum move"
and the user's custom nearby-level filter still need exact definitions.

Run on Windows 11
-----------------
1. Open Command Prompt in this folder.
2. Create/activate a virtual environment if desired:
     python -m venv .venv
     .venv\Scripts\activate
3. Install requirements:
     python -m pip install -r requirements.txt
4. Run:
     streamlit run app.py

If your current project already has an active virtual environment, install the
requirements there. No API key is needed for this public market-data endpoint.

Safety and limitations
----------------------
- Historical study only; no buy/sell recommendations or order execution.
- Does not include fees, slippage, funding, or realistic fill simulation.
- A current, unfinished candle is shown as provisional but excluded from calculations.
- A successful HTTP response does not independently authenticate the quality of
  a market-data provider.
- Do not add account or trading credentials to this project.
