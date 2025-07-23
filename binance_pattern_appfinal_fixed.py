
import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.distance import cosine
import time
import requests

# --- TELEGRAM SETTINGS ---
TELEGRAM_TOKEN = '7882466490:AAGj4sIE1ExqNX4nmTa9esw2WReXmVuo6Qk'
TELEGRAM_CHAT_ID = '5522699433'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

# --- BINANCE SETUP ---
exchange = ccxt.binance()

def fetch_ohlcv(symbol, timeframe='3d', limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        st.error(f"Failed to fetch data for {symbol}: {e}")
        return None

def normalize_series(series):
    return (series - np.mean(series)) / np.std(series)

def detect_reversal_pattern(df):
    if len(df) < 3:
        return False
    c = df['close'].values
    if c[-3] > c[-2] < c[-1] and c[-1] > c[-3]:
        return True  # Possible double bottom or reversal
    return False

def compare_with_reference(ref_series, other_series):
    return 1 - cosine(ref_series, other_series)

# --- UI ---
st.set_page_config(page_title="Binance Pattern Matcher", layout="wide")
st.title("🔍 Binance Pattern Matcher")
st.markdown("Find USDT pairs with **similar patterns** to a reference pair.")

# --- USER CONTROLS ---
timeframe = st.selectbox("Select Timeframe", ['3d', '1d', '4h'])
reference_pair = st.text_input("Reference Pair (e.g. BAKE/USDT)", "BAKE/USDT").upper()
top_n = st.slider("Top Matches to Show", 1, 20, 5)

if st.button("🔍 Scan Now"):
    ref_data = fetch_ohlcv(reference_pair, timeframe)
    if ref_data is not None:
        st.success(f"Fetched {len(ref_data)} candles for {reference_pair}")
        ref_series = normalize_series(ref_data['close'].values[-30:])

        markets = exchange.load_markets()
        usdt_pairs = [s for s in markets if s.endswith("/USDT") and s != reference_pair]

        results = []
        with st.spinner("Scanning market..."):
            for symbol in usdt_pairs:
                df = fetch_ohlcv(symbol, timeframe)
                if df is None or len(df) < 30:
                    continue
                series = normalize_series(df['close'].values[-30:])
                similarity = compare_with_reference(ref_series, series)
                is_reversal = detect_reversal_pattern(df)
                results.append({
                    'pair': symbol,
                    'similarity': similarity,
                    'reversal': is_reversal
                })
            df_result = pd.DataFrame(results).sort_values(by='similarity', ascending=False).head(top_n)

        st.dataframe(df_result)

        for _, row in df_result.iterrows():
            msg = (
                f"📈 *Match Found*\n"
                f"Pair: {row['pair']}\n"
                f"Similarity: {row['similarity']:.3f}\n"
                f"Reversal Pattern: {'✅' if row['reversal'] else '❌'}\n"
                f"Timeframe: {timeframe}"
            )
            send_telegram_alert(msg)

        st.success("✅ Telegram alerts sent.")
