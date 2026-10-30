BTC/USDT Momentum-Level Historical Study
=========================================

Purpose
-------
A non-executing educational Streamlit app to inspect BTC/USDT historical 5-minute
candles, identify candidate momentum-origin levels, and describe what happened
after price first returned to a level.

Data
----
The app uses Binance's public Spot klines endpoint:
https://data-api.binance.vision/api/v3/klines

Binance documents this market-data-only host as not requiring an API key:
https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md

This is a public endpoint, not a promise of uninterrupted availability. The app
does not connect to an account, request credentials, or place orders.

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
- A current, unfinished candle is excluded.
- A successful HTTP response does not independently authenticate the quality of
  a market-data provider.
- Do not add account or trading credentials to this project.
