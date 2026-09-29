import uvicorn
import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import config

def main():
    print(f"==================================================")
    print(f"  ElderAlpha AI - Day Trading Helper Assistant    ")
    print(f"  Codifying Andrew Elder's Day Trading Guide      ")
    print(f"==================================================")
    print(f"  [+] Starting Web Dashboard on http://{config.host}:{config.port}")
    print(f"  [+] Default Forex: EUR/USD, GBP/USD, USD/JPY")
    print(f"  [+] Default Crypto: BTC/USD, ETH/USD, SOL/USD")
    print(f"  [+] PyTorch Movement Learning & Calibrator: Active")
    print(f"  [+] Press Ctrl+C to stop server.\n")

    uvicorn.run("ui.app:app", host=config.host, port=config.port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
