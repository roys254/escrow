import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEB3_PROVIDER = os.getenv("WEB3_PROVIDER")
    TRON_PROVIDER = os.getenv("TRON_PROVIDER")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    ESCROW_FEE = float(os.getenv("ESCROW_FEE", "0.5"))
    
    # YOUR WALLET ADDRESSES
    YOUR_WALLETS = {
        "BTC": os.getenv("TEST_BTC_ADDRESS", "114miezL41JAwNxap1PfXvHjrY1SDGCQfa"),
        "LTC": os.getenv("TEST_LTC_ADDRESS", "MP7qEBHjW5v935kJ9rEiBAmJrzcc3mbJMv"),
        "DOGE": os.getenv("TEST_DOGE_ADDRESS", "DDykxkXmfio1QajFSCVCSwfHm62RckHpEE"),
        "ETH": os.getenv("TEST_ETH_ADDRESS", "0x88b78a531d61d8806c1faa7b159a0b357499644f"),
        "USDT": os.getenv("TEST_USDT_ADDRESS", "TWpz2jjsSbNCZAed7zZEZp3zUNydGcNZEY")
    }
    
    MIN_AMOUNTS = {
        "BTC": 0.0001,
        "ETH": 0.005,
        "LTC": 0.01,
        "DOGE": 10,
        "USDT": 10
    }