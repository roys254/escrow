import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Validate token
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set!")
    
    BOT_TOKEN = BOT_TOKEN.strip()
    
    if ' ' in BOT_TOKEN:
        raise ValueError("BOT_TOKEN contains spaces!")
    
    if '"' in BOT_TOKEN or "'" in BOT_TOKEN:
        raise ValueError("BOT_TOKEN contains quotes!")
    
    if '\n' in BOT_TOKEN:
        raise ValueError("BOT_TOKEN contains newline!")
    
    WEB3_PROVIDER = os.getenv("WEB3_PROVIDER")
    TRON_PROVIDER = os.getenv("TRON_PROVIDER")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    ESCROW_FEE = float(os.getenv("ESCROW_FEE", "0.5"))
    
    # YOUR UPDATED WALLET ADDRESSES
    YOUR_WALLETS = {
        "BTC": "bc1qsykztwjclsx5nnhyqpjsgrwlc829svkkcm87t6",
        "ETH": "0xc82dfc44d5Db5592e781c7F97991ac41B3838b4D",
        "LTC": "ltc1qwqk3c8j9z3rj90jv852xzt4v0qw84y4zl2s5nf",
        "DOGE": "DERdiK2MKh3CzYovnUDvSRMupR7KQx2KT3",
        "USDT": "TGWcht1TyUwMz7hS42coWwm1YBAP597SJU"
    }
    
    MIN_AMOUNTS = {
        "BTC": 0.0001,
        "ETH": 0.005,
        "LTC": 0.01,
        "DOGE": 10,
        "USDT": 10
    }

# At the bottom of config.py
print("=" * 50)
print("🔍 CONFIGURATION LOADED:")
print(f"BOT_TOKEN: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
print("WALLET ADDRESSES:")
for currency, address in YOUR_WALLETS.items():
    print(f"  {currency}: {address}")
print("=" * 50)