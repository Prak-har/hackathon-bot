import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load your secure API keys
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
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
            
        params['timestamp'] = str(int(time.time() * 1000))
        query_string, signature = self._generate_signature(params)
        
        headers = {
            'RST-API-KEY': self.api_key,
            'MSG-SIGNATURE': signature
        }
        
        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            res = requests.post(url, headers=headers, data=query_string)
        else:
            res = requests.get(f"{url}?{query_string}", headers=headers)
            
        return res.json()

def main():
    print("🚀 Starting Team110-Profit Pulse Bot...")
    client = RoostooClient()
    
    PAIR = 'BTC/USD'
    TRADE_QTY = 0.5 
    prices = []     
    in_position = False 

    # Verify the connection works
    balance = client.dispatch('GET', '/v3/balance')
    print(f"✅ Connected! Balance data received.")

    while True:
        try:
            ticker = client.dispatch('GET', '/v3/ticker', {'pair': PAIR})
            current_price = float(ticker['Data'][PAIR]['LastPrice'])
            prices.append(current_price)
            
            if len(prices) > 15:
                prices.pop(0)
                
            print(f"[{time.strftime('%H:%M:%S')}] {PAIR}: ${current_price:.2f} | Gathering: {len(prices)}/15 mins")

            if len(prices) == 15:
                fast_sma = sum(prices[-5:]) / 5   
                slow_sma = sum(prices) / 15       
                
                if fast_sma > slow_sma and not in_position:
                    print("📈 UPWARD MOMENTUM! Executing BUY.")
                    client.dispatch('POST', '/v3/place_order', {
                        'pair': PAIR, 'side': 'BUY', 'type': 'MARKET', 'quantity': str(TRADE_QTY)
                    })
                    in_position = True
                    
                elif fast_sma < slow_sma and in_position:
                    print("📉 DOWNWARD MOMENTUM! Executing SELL.")
                    client.dispatch('POST', '/v3/place_order', {
                        'pair': PAIR, 'side': 'SELL', 'type': 'MARKET', 'quantity': str(TRADE_QTY)
                    })
                    in_position = False

        except Exception as e:
            print(f"⚠️ Error: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    main()