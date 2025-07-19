DYOR!!!
# DEXScreener Bot with ToxiSol Trading

A Python bot that analyzes tokens on DEXScreener, trades via ToxiSol Telegram bot, and sends buy/sell notifications. Only processes tokens marked "Good" by Rugcheck.xyz, blacklists tokens with bundle purchases or fake volume, and applies configurable filters.

## Setup
1. Install Python 3.8+.
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `config.yaml`:
   - Set `dexscreener.api_url` (https://docs.dexscreener.com).
   - Set `rugcheck.api_url` and `api_key` (https://api.rugcheck.xyz).
   - Set `telegram.bot_token` (from BotFather) and `chat_id` (from @getidsbot).
   - Set `telegram.toxisol_bot`, `wallet_address`, and `wallet_private_key` for ToxiSol.
   - Configure `filters`, `fake_volume`, `bundle`, and `blacklist`.
   - Adjust `analysis` intervals.
4. Run the bot: `python bot.py`

## Features
- Fetches tokens from DEXScreener API.
- Verifies tokens with Rugcheck.xyz; only processes "Good" tokens.
- Blacklists tokens with bundle purchases (≥5 wallets holding ≥2% supply).
- Detects fake volume using Pocket Universe API and heuristics.
- Applies filters (market cap, volume, liquidity, pair age).
- Detects rug pulls (>90% price drop), pumps (>500% price increase), new pairs (<24 hours).
- Trades new pairs/pumps via ToxiSol Telegram bot.
- Sends Telegram notifications for buy/sell actions.
- Stores data in SQLite (`dexscreener.db`).
- Analyzes patterns (top 10 tokens by market cap).

## Configuration
- **Rugcheck**: Set `api_key` and `chain` (e.g., `solana`).
- **Telegram**: Set `bot_token`, `chat_id`, `toxisol_bot`, `wallet_address`, `wallet_private_key`.
- **Bundle Detection**: Configure `max_wallets`, `min_percentage`, `time_window_seconds`.
- **Filters**: Adjust `min_market_cap`, `max_daily_volume`, etc.
- **Fake Volume**: Set `volume_liquidity_ratio`, `volume_spike_threshold`, etc.
- **Blacklists**: Add to `blacklist.coins` and `blacklist.devs`.

## Example Config
```yaml
telegram:
  bot_token: "your_telegram_bot_token"
  chat_id: "your_chat_id"
  toxisol_bot: "@ToxiSolBot"
  wallet_address: "your_solana_wallet_address"
  wallet_private_key: "your_wallet_private_key"
rugcheck:
  api_url: "https://api.rugcheck.xyz"
  api_key: "your_rugcheck_api_key"
  chain: "solana"
bundle:
  max_wallets: 5
  min_percentage: 2
  time_window_seconds: 60
filters:
  min_market_cap: 1000000
  max_daily_volume: 5000000
