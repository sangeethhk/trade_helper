# Contributing to ElderAlpha AI

Thank you for your interest in contributing to **ElderAlpha Trading Helper AI**! 🚀

Our goal is to build the most disciplined, mathematically sound, and psychologically hardened open-source algorithmic trading assistant, codifying the legendary strategies of **Andrew Elder: Day Trading Strategies (Book 2)**.

---

## 🛠️ How You Can Contribute

1. **New Strategies & Patterns:** Add new setups under `strategies/` (e.g. Volume Profile, VWAP Bounces, Elliott Wave impulses).
2. **Broker Adapters:** Connect real broker APIs (e.g. Interactive Brokers, MetaTrader 5, Binance, Bybit).
3. **Machine Learning Models:** Enhance `learning/movement_model.py` with Transformer or LSTM architectures.
4. **Economic News Feeds:** Add live webhook/API connectors to ForexFactory, DailyFX, or Bloomberg calendar feeds in `risk/news_manager.py`.

---

## 🧪 Development Workflow

1. **Fork the Repository:** Click the **Fork** button on GitHub.
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/trade_helper.git
   cd trade_helper
   ```
3. **Create a feature branch:**
   ```bash
   git checkout -b feature/amazing-new-strategy
   ```
4. **Install dependencies & run tests:**
   ```bash
   pip install -r requirements.txt
   python -m unittest discover tests
   ```
5. **Commit your changes:**
   ```bash
   git commit -m "feat: added VWAP mean reversion pattern"
   ```
6. **Push to your fork and submit a Pull Request (PR)!**

---

## 📜 Code of Conduct
- Be respectful and collaborative.
- Adhere to the core rule: **Never compromise on capital preservation.** All strategies must include explicit Stop Losses and minimum 2:1 Payout Ratios.
