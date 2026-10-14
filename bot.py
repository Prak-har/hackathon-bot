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
        if params is None: params = {}
        params['timestamp'] = str(int(time.time() * 1000))
        query_string, signature = self._generate_signature(params)
        
        # Added Custom User-Agent to bypass Cloudflare / 403 errors
        headers = {
            'RST-API-KEY': self.api_key,
            'MSG-SIGNATURE': signature,
            'User-Agent': 'Quant-Bot-Team110/2.0'
        }
        
        url = f"{self.base_url}{endpoint}"
        try:
            if method == 'POST':
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                res = requests.post(url, headers=headers, data=query_string, timeout=10)
            else:
                res = requests.get(f"{url}?{query_string}", headers=headers, timeout=10)
            
            # Catch raw HTML error pages before JSON crashes
            if res.status_code != 200:
                return {'Success': False, 'ErrMsg': f"HTTP {res.status_code}: {res.text}"}
            
            return res.json()
        except requests.exceptions.RequestException as e:
            return {'Success': False, 'ErrMsg': f"Network Blocked: {str(e)}"}
        except ValueError:
            return {'Success': False, 'ErrMsg': "Exchange returned invalid data (Not JSON)"}

def calculate_ema(data, period):
    if len(data) < period: return data[-1]
    multiplier = 2 / (period + 1)
    ema = sum(data[:period]) / period
    for price in data[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_zscore(series, window):
    if len(series) < window: return 0.0
    recent = series[-window:]
    mean = sum(recent) / window
    variance = sum((x - mean) ** 2 for x in recent) / (window - 1)
    std_dev = math.sqrt(variance)
    return 0.0 if std_dev == 0 else (series[-1] - mean) / std_dev

def main():
    print("🚀 Initializing Multi-Layer Institutional Quant Bot...")
    client = RoostooClient()

    PAIR_A = 'BTC/USD'
    PAIR_B = 'ETH/USD'
    
    # STRATEGY TUNING
    Z_WINDOW = 30           # 30-min rolling window for Stat Arb
    EMA_PERIOD = 15         # 15-min Trend regime filter
    TRADE_SIZE_USD = 5000.0 # Standard trade size
    
    history_A = []
    history_B = []
    ratio_history = []
    
    # Portfolio Trackers
    pos_A = 0.0 
    pos_B = 0.0 

    print("Checking Server Connect...")
    balance = client.dispatch('GET', '/v3/balance')
    if balance.get('Success'):
        print("✅ Exchange Authenticated Successfully!")
    else:
        print(f"⚠️ Boot Warning: {balance.get('ErrMsg', 'Check API Keys')}")

    while True:
        try:
            # --- LAYER 0: DATA INGESTION ---
            tickers = client.dispatch('GET', '/v3/ticker')
            if not tickers.get('Success', False):
                print(f"⚠️ API Error (Retrying): {tickers.get('ErrMsg')}")
                time.sleep(10)
                continue

            btc_last = float(tickers['Data'][PAIR_A]['LastPrice'])
            btc_bid  = float(tickers['Data'][PAIR_A]['MaxBid'])
            btc_ask  = float(tickers['Data'][PAIR_A]['MinAsk'])
            
            eth_last = float(tickers['Data'][PAIR_B]['LastPrice'])
            eth_bid  = float(tickers['Data'][PAIR_B]['MaxBid'])
            eth_ask  = float(tickers['Data'][PAIR_B]['MinAsk'])

            history_A.append(btc_last)
            history_B.append(eth_last)
            ratio_history.append(eth_last / btc_last)

            # Cap array size for memory efficiency
            if len(history_A) > 60:
                history_A.pop(0)
                history_B.pop(0)
                ratio_history.pop(0)

            if len(ratio_history) < Z_WINDOW:
                print(f"[{time.strftime('%H:%M:%S')}] Bootstrapping arrays... ({len(ratio_history)}/{Z_WINDOW})")
                time.sleep(60)
                continue

            # --- SIGNAL GENERATION ---
            z_score = calculate_zscore(ratio_history, Z_WINDOW)
            
            # LAYER 2: Liquidity Imbalance (Spread Check)
            btc_spread = (btc_ask - btc_bid) / btc_last
            eth_spread = (eth_ask - eth_bid) / eth_last
            liquidity_safe = btc_spread < 0.0025 and eth_spread < 0.0025 # Avoid trading if spread > 0.25%

            # LAYER 3: Momentum Regime (EMA)
            btc_ema = calculate_ema(history_A, EMA_PERIOD)
            eth_ema = calculate_ema(history_B, EMA_PERIOD)
            btc_trend_up = btc_last > (btc_ema * 0.999) # Small buffer
            eth_trend_up = eth_last > (eth_ema * 0.999)

            print(f"[{time.strftime('%H:%M:%S')}] Z-Score: {z_score:+.2f} | BTC Spread: {btc_spread*100:.2f}% | ETH Spread: {eth_spread*100:.2f}%")

            # --- EXECUTION LOGIC ---
            
            # SIGNAL 1: ETH Overpriced / BTC Underpriced (Z > 1.8)
            if z_score > 1.8 and liquidity_safe and btc_trend_up:
                print(f"📉 SPREAD SIGNAL: ETH Overpriced / BTC Underpriced.")
                
                if pos_B > 0: # Sell ETH (Simulated Short/Exit)
                    print(f"   -> Dumping ETH inventory...")
                    client.dispatch('POST', '/v3/place_order', {'pair': PAIR_B, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(pos_B)})
                    pos_B = 0.0
                
                if pos_A == 0: # Buy BTC
                    qty = round(TRADE_SIZE_USD / btc_last, 4)
                    print(f"   -> Buying {qty} BTC...")
                    res = client.dispatch('POST', '/v3/place_order', {'pair': PAIR_A, 'side': 'BUY', 'type': 'MARKET', 'quantity': str(qty)})
                    if res.get('Success'): pos_A = qty
                    else: print(f"   ❌ Buy Failed: {res.get('ErrMsg')}")

            # SIGNAL 2: BTC Overpriced / ETH Underpriced (Z < -1.8)
            elif z_score < -1.8 and liquidity_safe and eth_trend_up:
                print(f"📈 SPREAD SIGNAL: BTC Overpriced / ETH Underpriced.")
                
                if pos_A > 0: # Sell BTC (Simulated Short/Exit)
                    print(f"   -> Dumping BTC inventory...")
                    client.dispatch('POST', '/v3/place_order', {'pair': PAIR_A, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(pos_A)})
                    pos_A = 0.0
                
                if pos_B == 0: # Buy ETH
                    qty = round(TRADE_SIZE_USD / eth_last, 4)
                    print(f"   -> Buying {qty} ETH...")
                    res = client.dispatch('POST', '/v3/place_order', {'pair': PAIR_B, 'side': 'BUY', 'type': 'MARKET', 'quantity': str(qty)})
                    if res.get('Success'): pos_B = qty
                    else: print(f"   ❌ Buy Failed: {res.get('ErrMsg')}")

            # SIGNAL 3: Mean Reversion Lock Profit OR Stop-Loss
            elif (abs(z_score) < 0.3 or abs(z_score) > 3.5) and (pos_A > 0 or pos_B > 0):
                print(f"🎯 REBALANCING TRIGGERED. Clearing positions to USD.")
                if pos_A > 0:
                    client.dispatch('POST', '/v3/place_order', {'pair': PAIR_A, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(pos_A)})
                    pos_A = 0.0
                if pos_B > 0:
                    client.dispatch('POST', '/v3/place_order', {'pair': PAIR_B, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(pos_B)})
                    pos_B = 0.0

        except Exception as e:
            print(f"⚠️ Unknown Loop Error: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
