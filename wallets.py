import requests
from config import Config

class WalletManager:
    def __init__(self):
        self.usdt_contract = "TWpz2jjsSbNCZAed7zZEZp3zUNydGcNZEY"
    
    def check_balance(self, currency):
        address = Config.YOUR_WALLETS.get(currency)
        if not address:
            return 0
        
        try:
            if currency == "BTC":
                # Using blockchain.info API
                url = f"https://blockchain.info/q/addressbalance/{address}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    return int(response.text) / 100_000_000
                return 0
            
            elif currency == "LTC":
                # Using blockchair API
                url = f"https://api.blockchair.com/litecoin/dashboards/address/{address}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data") and address in data["data"]:
                        return data["data"][address].get("balance", 0) / 100_000_000
                return 0
            
            elif currency == "DOGE":
                # Using blockchair API
                url = f"https://api.blockchair.com/dogecoin/dashboards/address/{address}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data") and address in data["data"]:
                        return data["data"][address].get("balance", 0) / 100_000_000
                return 0
            
            elif currency == "ETH":
                # Using Etherscan API (no web3 needed)
                url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "1":
                        return int(data.get("result", 0)) / 10**18
                return 0
            
            elif currency == "USDT":
                # Using TronGrid API
                url = f"https://api.trongrid.io/v1/accounts/{address}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        account_data = data["data"][0]
                        if "trc20" in account_data:
                            for token in account_data["trc20"]:
                                if self.usdt_contract in token:
                                    return int(token[self.usdt_contract]) / 1_000_000
                return 0
            
            return 0
            
        except Exception as e:
            print(f"Error checking {currency}: {e}")
            return 0
    
    def validate_address(self, currency, address):
        if currency == "BTC":
            return len(address) >= 26 and len(address) <= 34 and address.startswith(('1', '3', 'bc1'))
        elif currency == "LTC":
            return len(address) >= 26 and len(address) <= 34 and address.startswith(('L', 'M', 'ltc1'))
        elif currency == "DOGE":
            return len(address) >= 26 and len(address) <= 34 and address.startswith('D')
        elif currency == "ETH":
            return address.startswith('0x') and len(address) == 42
        elif currency == "USDT":
            return address.startswith('T') and len(address) == 34
        return False