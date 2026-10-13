import os
import time
import math
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

class RoostooClient:
    def __init__(self):
        self.base_url = "https://mock-api.roostoo.com"
        self.api_key = os.getenv("ROOSTOO_API_KEY")
        self.api_secret = os.getenv("ROOSTOO_API_SECRET")

    def _generate_signature(self, params):
        sorted_params = dict(sorted(params.items()))
        query_string = urlencode(sorted_params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return query_string, signature

    def dispatch(self, method, endpoint, params=None):
        if params is None:
            params = {}
        params['timestamp'] = str(int(time.time() * 1000))
        query_string, signature = self._generate_signature(params)
        
        headers = {
            'RST-API-KEY': self.api_key,
            'MSG-SIGNATURE': signature
        }
        
        url = f"{self.base_url}{endpoint}"
        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            res = requests.post(url, headers=headers, data=query_string)
        else:
            res = requests.get(f"{url}?{query_string}", headers=headers)
            
        return res.json()

# --- STATISTICAL MATH HELPERS ---

def calculate_zscore(series):
    """Calculates mean, standard deviation, and Z-score of the latest value."""
    n = len(series)
    if n < 10:
        return 0.0, 0.0, 0.0
    
    mean = sum(series) / n
    variance = sum((x - mean) ** 2 for x in series) / (n - 1)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return mean, 0.0, 0.0
        
    z_score = (series[-1] - mean) / std_dev
    return mean, std_dev, z_score

# --- STATISTICAL ARBITRAGE ENGINE ---

def main():
    print("🚀 Initializing Team110-Profit Pulse Statistical Arbitrage Engine...")
    client = RoostooClient()

    PAIR_A = 'BTC/USD'
    PAIR_B = 'ETH/USD'
    LOOKBACK_PERIOD = 30  # 30-minute rolling window
    TRADE_ALLOCATION_USD = 5000.0  # Size per trade in USD
    
    ratio_history = []
    current_position = "NONE"  # Can be "LONG_ETH", "LONG_BTC", or "NONE"
    active_qty = 0.0

    # Test initial connectivity
    balance = client.dispatch('GET', '/v3/balance')
    usd_free = balance.get('Wallet', {}).get('USD', {}).get('Free', '0')
    print(f"✅ Exchange Connected. Available USD: ${float(usd_free):,.2f}")

    while True:
        try:
            # 1. Ingest market tickers simultaneously
            tickers = client.dispatch('GET', '/v3/ticker')
            btc_price = float(tickers['Data'][PAIR_A]['LastPrice'])
            eth_price = float(tickers['Data'][PAIR_B]['LastPrice'])

            # 2. Compute synthetic spread ratio (ETH / BTC)
            ratio = eth_price / btc_price
            ratio_history.append(ratio)
            
            if len(ratio_history) > LOOKBACK_PERIOD:
                ratio_history.pop(0)

            print(f"[{time.strftime('%H:%M:%S')}] BTC: ${btc_price:,.2f} | ETH: ${eth_price:,.2f} | Ratio: {ratio:.6f} ({len(ratio_history)}/{LOOKBACK_PERIOD}m)")

            # 3. Evaluate Statistical Arbitrage once rolling window is warm
            if len(ratio_history) >= LOOKBACK_PERIOD:
                mean, std, z = calculate_zscore(ratio_history)
                print(f"   -> Rolling μ: {mean:.6f} | σ: {std:.6f} | Z-Score: {z:+.2f} | Position: {current_position}")

                # ENTRY 1: ETH is statistically oversold relative to BTC (Z < -1.8)
                if z < -1.8 and current_position == "NONE":
                    target_qty = round(TRADE_ALLOCATION_USD / eth_price, 4)
                    print(f"📉 SPREAD DIVERGENCE: ETH Underpriced (Z={z:.2f}). Buying {target_qty} ETH...")
                    order = client.dispatch('POST', '/v3/place_order', {
                        'pair': PAIR_B, 'side': 'BUY', 'type': 'MARKET', 'quantity': str(target_qty)
                    })
                    if order.get('Success', False):
                        current_position = "LONG_ETH"
                        active_qty = target_qty

                # ENTRY 2: ETH is statistically overvalued relative to BTC (Z > +1.8)
                elif z > 1.8 and current_position == "NONE":
                    target_qty = round(TRADE_ALLOCATION_USD / btc_price, 4)
                    print(f"📈 SPREAD DIVERGENCE: BTC Underpriced (Z={z:.2f}). Buying {target_qty} BTC...")
                    order = client.dispatch('POST', '/v3/place_order', {
                        'pair': PAIR_A, 'side': 'BUY', 'type': 'MARKET', 'quantity': str(target_qty)
                    })
                    if order.get('Success', False):
                        current_position = "LONG_BTC"
                        active_qty = target_qty

                # EXIT 1: Mean Reversion Target Reached (|Z| <= 0.3)
                elif abs(z) <= 0.3 and current_position != "NONE":
                    print(f"🎯 MEAN REVERSION ACHIEVED (Z={z:.2f}). Closing position to USD...")
                    pair_to_sell = PAIR_B if current_position == "LONG_ETH" else PAIR_A
                    client.dispatch('POST', '/v3/place_order', {
                        'pair': pair_to_sell, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(active_qty)
                    })
                    current_position = "NONE"
                    active_qty = 0.0

                # EXIT 2: Stop-Loss Circuit Breaker (|Z| >= 3.2 - Structural Break)
                elif abs(z) >= 3.2 and current_position != "NONE":
                    print(f"🚨 SPREAD BREAKDOWN DETECTED (Z={z:.2f}). Executing Stop-Loss Exit...")
                    pair_to_sell = PAIR_B if current_position == "LONG_ETH" else PAIR_A
                    client.dispatch('POST', '/v3/place_order', {
                        'pair': pair_to_sell, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(active_qty)
                    })
                    current_position = "NONE"
                    active_qty = 0.0

        except Exception as e:
            print(f"⚠️ Polling loop error: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
