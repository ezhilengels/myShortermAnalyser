
import yfinance as yf

stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "BHARTIARTL.NS", "ITC.NS", "ASIANPAINT.NS"]
for s in stocks:
    info = yf.Ticker(s).info
    print(f"{s}: Sector='{info.get('sector')}', Industry='{info.get('industry')}', PE={info.get('trailingPE')}")
