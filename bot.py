import requests
import yaml
import sqlite3
import threading
import time
from datetime import datetime

class Database:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                address TEXT PRIMARY KEY,
                name TEXT,
                symbol TEXT,
                market_cap REAL,
                volume REAL,
                liquidity REAL,
                price_usd REAL,
                price_change_24h REAL,
                pair_created_at INTEGER,
                status TEXT,
                listed_on_cex INTEGER,
                dev_address TEXT,
                last_updated INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                pattern_type TEXT,
                detected_at INTEGER,
                details TEXT,
                FOREIGN KEY (token_address) REFERENCES tokens (address)
            )
        ''')
        self.conn.commit()

    def insert_or_update_token(self, token):
        self.cursor.execute('''
            INSERT OR REPLACE INTO tokens (
                address, name, symbol, market_cap, volume, liquidity,
                price_usd, price_change_24h, pair_created_at, status,
                listed_on_cex, dev_address, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            token['address'], token.get('name'), token.get('symbol'),
            token.get('market_cap', 0), token.get('volume', 0),
            token.get('liquidity', 0), token.get('price_usd', 0),
            token.get('price_change_24h', 0), token.get('pair_created_at', 0),
            token.get('status', 'unknown'), token.get('listed_on_cex', 0),
            token.get('dev_address'), int(datetime.now().timestamp())
        ))
        self.conn.commit()

    def insert_pattern(self, token_address, pattern_type, details):
        self.cursor.execute('''
            INSERT INTO patterns (token_address, pattern_type, detected_at, details)
            VALUES (?, ?, ?, ?)
        ''', (
            token_address, pattern_type, int(datetime.now().timestamp()), details
        ))
        self.conn.commit()

    def fetch_all_coins(self):
        self.cursor.execute('SELECT * FROM tokens')
        return self.cursor.fetchall()

    def fetch_patterns(self):
        self.cursor.execute('SELECT * FROM patterns')
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()

class Blacklist:
    def __init__(self, config_path):
        self.config_path = config_path
        self.lock = threading.Lock()
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            blacklist_config = config.get('blacklist', {})
            self.blacklisted_coins = blacklist_config.get('coins', []) or []
            self.blacklisted_devs = blacklist_config.get('devs', []) or []
            print(f"Loaded {len(self.blacklisted_coins)} blacklisted coins and {len(self.blacklisted_devs)} blacklisted devs.")
        except FileNotFoundError:
            print(f"Error: Config file {config_path} not found.")
            self.blacklisted_coins = []
            self.blacklisted_devs = []
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            self.blacklisted_coins = []
            self.blacklisted_devs = []

    def is_coin_blacklisted(self, address):
        if not address:
            return False
        return address.lower() in [addr.lower() for addr in self.blacklisted_coins]

    def is_dev_blacklisted(self, dev_address):
        if not dev_address:
            return False
        return dev_address.lower() in [addr.lower() for addr in self.blacklisted_devs]

    def add_coin_to_blacklist(self, address, reason):
        with self.lock:
            if address.lower() not in [addr.lower() for addr in self.blacklisted_coins]:
                self.blacklisted_coins.append(address)
                print(f"Added {address} to blacklist: {reason}")
                self._update_config()
            else:
                print(f"Coin {address} already blacklisted.")

    def _update_config(self):
        tryirsi
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
            config['blacklist']['coins'] = self.blacklisted_coins
            with open(self.config_path, 'w') as file:
                yaml.safe_dump(config, file, default_flow_style=False)
            print(f"Updated config.yaml with new blacklist.")
        except Exception as e:
            print(f"Error updating config.yaml: {e}")

class Filters:
    @staticmethod
    def apply_filters(token, filters):
        try:
            market_cap = token.get('market_cap', 0)
            volume = token.get('volume', 0)
            liquidity = token.get('liquidity', 0)
            pair_created_at = token.get('pair_created_at', 0)
            
            if not all(key in filters for key in ['min_market_cap', 'max_daily_volume', 'min_liquidity', 'max_age_hours']):
                raise ValueError("Missing required filter keys in config.")

            if market_cap < filters['min_market_cap']:
                return False, "Market cap too low"
            if volume > filters['max_daily_volume']:
                return False, "Volume too high"
            if liquidity < filters['min_liquidity']:
                return False, "Liquidity too low"
            
            return True, "Passed all filters"
        except Exception as e:
            return False, f"Filter error: {str(e)}"

    @staticmethod
    def detect_pump(token, filters):
        try:
            price_change = token.get('price_change_24h', 0)
            return price_change > filters['max_price_change'], f"Price change: {price_change}%"
        except KeyError:
            return False, "Missing max_price_change in filters"

    @staticmethod
    def detect_rug(token, filters):
        try:
            price_change = token.get('price_change_24h', 0)
            return price_change < filters['min_price_drop'], f"Price drop: {price_change}%"
        except KeyError:
            return False, "Missing min_price_drop in filters"

    @staticmethod
    def is_new_pair(token, filters):
        try:
            pair_created_at = token.get('pair_created_at', 0) / 1000
            current_time = datetime.now().timestamp()
            max_age_seconds = filters['max_age_hours'] * 3600
            return pair_created_at > current_time - max_age_seconds, f"Pair age: {(current_time - pair_created_at) / 3600:.2f} hours"
        except KeyError:
            return False, "Missing max_age_hours in filters"

class FakeVolumeDetector:
    def __init__(self, config):
        self.config = config.get('fake_volume', {})
        self.pocket_universe_api = config.get('dexscreener', {}).get('pocket_universe_api')
        self.pocket_universe_enabled = self.config.get('pocket_universe_enabled', False)
        self.volume_liquidity_ratio = self.config.get('volume_liquidity_ratio', 50)
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 1000)
        self.min_trades_for_spike = self.config.get('min_trades_for_spike', 10)

    def detect_fake_volume(self, token):
        try:
            volume = token.get('volume', 0)
            liquidity = token.get('liquidity', 0)
            trades = token.get('txns', {}).get('h24', {}).get('buys', 0) + token.get('txns', {}).get('h24', {}).get('sells', 0)
            address = token.get('address')

            if liquidity > 0 and volume / liquidity > self.volume_liquidity_ratio:
                return True, f"High volume-to-liquidity ratio: {volume/liquidity:.2f}x"

            historical_volume = token.get('volume_h6', 0)
            if historical_volume > 0 and volume / historical_volume * 100 > self.volume_spike_threshold and trades >= self.min_trades_for_spike:
                return True, f"Volume spike: {volume/historical_volume*100:.2f}% with {trades} trades"

            if self.pocket_universe_enabled:
                is_fake = self._check_pocket_universe(address, volume, trades)
                if is_fake:
                    return True, "Pocket Universe API flagged as fake volume"

            return False, "No fake volume detected"
        except Exception as e:
            return False, f"Error detecting fake volume: {str(e)}"

    def _check_pocket_universe(self, address, volume, trades):
        try:
            if not self.pocket_universe_api:
                return False
            response = requests.post(self.pocket_universe_api, json={
                'address': address,
                'volume_24h': volume,
                'trades_24h': trades
            })
            response.raise_for_status()
            data = response.json()
            return data.get('is_fake_volume', False)
        except requests.RequestException as e:
            print(f"Pocket Universe API error: {e}")
            return False

class Rugcheck:
    def __init__(self, config):
        self.api_url = config.get('rugcheck', {}).get('api_url')
        self.api_key = config.get('rugcheck', {}).get('api_key')
        self.chain = config.get('rugcheck', {}).get('chain', 'solana')
        self.bundle_config = config.get('bundle', {})
        self.max_wallets = self.bundle_config.get('max_wallets', 5)
        self.min_percentage = self.bundle_config.get('min_percentage', 2)
        self.time_window_seconds = self.bundle_config.get('time_window_seconds', 60)

    def check_token(self, address):
        try:
            if not self.api_url or not self.api_key:
                raise ValueError("Rugcheck API URL or key missing in config.")
            headers = {"X-API-KEY": self.api_key}
            url = f"{self.api_url}/tokens/scan/{self.chain}/{address}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            is_good = data.get('status') == "Good"
            details = data.get('details', 'No details provided')
            return is_good, details
        except requests.RequestException as e:
            print(f"Rugcheck API error for {address}: {e}")
            return False, f"API error: {str(e)}"
        except ValueError as e:
            print(f"Rugcheck config error: {e}")
            return False, str(e)

    def detect_bundle(self, token):
        try:
            address = token.get('address')
            transactions = token.get('txns', {}).get('recent', [])
            if not transactions:
                return False, "No transaction data available"

            wallet_holdings = {}
            current_time = datetime.now().timestamp()
            for tx in transactions:
                tx_time = tx.get('timestamp', 0) / 1000
                if current_time - tx_time > self.time_window_seconds:
                    continue
                wallet = tx.get('buyer_wallet')
                amount = tx.get('amount', 0)
                if wallet and amount:
                    wallet_holdings[wallet] = wallet_holdings.get(wallet, 0) + amount

            total_supply = token.get('total_supply', 1)
            significant_wallets = [
                wallet for wallet, amount in wallet_holdings.items()
                if (amount / total_supply * 100) >= self.min_percentage
            ]
            if len(significant_wallets) >= self.max_wallets:
                return True, f"Bundle detected: {len(significant_wallets)} wallets hold >= {self.min_percentage}% each"
            return False, "No bundle detected"
        except Exception as e:
            print(f"Bundle detection error for {address}: {e}")
            return False, f"Error: {str(e)}"

class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_notification(self, message):
        try:
            response = requests.post(self.base_url, json={
                'chat_id': self.chat_id,
                'text': message
            })
            response.raise_for_status()
            print(f"Telegram notification sent: {message}")
        except requests.RequestException as e:
            print(f"Error sending Telegram notification: {e}")

class ToxiSolTrader:
    def __init__(self, bot_username, wallet_address, wallet_private_key):
        self.bot_username = bot_username
        self.wallet_address = wallet_address
        self.wallet_private_key = wallet_private_key

    def execute_trade(self, token_address, action, amount):
        # Placeholder: ToxiSol API/command integration
        try:
            # Simulate sending a command to ToxiSol bot (e.g., /buy or /sell)
            command = f"{self.bot_username} /{action.lower()} {token_address} {amount} {self.wallet_address}"
            print(f"Simulating ToxiSol trade: {command}")
            # In a real implementation, send this command via Telegram API or ToxiSol's API
            # Requires ToxiSol API documentation for actual integration
            return True, f"{action.capitalize()} executed for {token_address} ({amount} SOL)"
        except Exception as e:
            return False, f"Error executing {action} on ToxiSol: {str(e)}"

class DexscreenerBot:
    def __init__(self, config_path: str):
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
        except FileNotFoundError:
            raise Exception(f"Config file {config_path} not found.")
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing config file: {e}")

        required_sections = ['dexscreener', 'rugcheck', 'telegram', 'database', 'filters', 'fake_volume', 'bundle', 'blacklist', 'analysis']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")

        db_config = self.config['database']
        if db_config.get('type') != 'sqlite':
            raise ValueError("Only SQLite database is supported.")
        self.db = Database(db_config['name'])
        
        self.blacklist = Blacklist(config_path)
        self.fake_volume_detector = FakeVolumeDetector(self.config)
        self.rugcheck = Rugcheck(self.config)
        self.filters = self.config.get('filters', {})
        self.telegram = self.config.get('telegram', {})
        self.notifier = TelegramNotifier(self.telegram.get('bot_token'), self.telegram.get('chat_id'))
        self.trader = ToxiSolTrader(
            self.telegram.get('toxisol_bot'),
            self.telegram.get('wallet_address'),
            self.telegram.get('wallet_private_key')
        )
        
        self.api_url = self.config['dexscreener'].get('api_url')
        if not self.api_url:
            raise ValueError("Missing DEXScreener API URL in config.")
        
        self.analyze_interval = self.config['analysis'].get('analyze_interval', 3600)
        self.rug_check_interval = self.config['analysis'].get('rug_check_interval', 1800)

    def fetch_tokens(self) -> list:
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            return data.get('pairs', [])
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return []

    def check_cex_listing(self, token):
        return False  # Placeholder

    def determine_status(self, token):
        is_pump, pump_details = Filters.detect_pump(token, self.filters)
        if is_pump:
            return 'pumped', pump_details
        is_rug, rug_details = Filters.detect_rug(token, self.filters)
        if is_rug:
            return 'rugged', rug_details
        is_new, new_details = Filters.is_new_pair(token, self.filters)
        if is_new:
            return 'new_pair', new_details
        return 'stable', "No significant patterns detected"

    def process_tokens(self, tokens: list):
        for token in tokens:
            address = token.get('pairAddress')
            dev_address = token.get('dev_address')
            liquidity = token.get('liquidity', {}).get('usd', 0)
            price_change = token.get('priceChange', {}).get('h24', 0)
            market_cap = token.get('marketCap', 0)
            volume = token.get('volume', {}).get('h24', 0)
            total_supply = token.get('totalSupply', 1)

            token_data = {
                'address': address,
                'name': token.get('baseToken', {}).get('name'),
                'symbol': token.get('baseToken', {}).get('symbol'),
                'market_cap': market_cap,
                'volume': volume,
                'liquidity': liquidity,
                'price_usd': token.get('priceUsd', 0),
                'price_change_24h': price_change,
                'pair_created_at': token.get('pairCreatedAt', 0),
                'total_supply': total_supply,
                'status': None,
                'listed_on_cex': self.check_cex_listing(token),
                'dev_address': dev_address
            }

            # Check blacklists
            if self.blacklist.is_coin_blacklisted(address):
                print(f"Coin {token_data['name']} ({address}) is blacklisted.")
                continue
            if self.blacklist.is_dev_blacklisted(dev_address):
                print(f"Developer of {token_data['name']} ({dev_address}) is blacklisted.")
                continue

            # Check Rugcheck.xyz
            is_good, rugcheck_details = self.rugcheck.check_token(address)
            if not is_good:
                self.blacklist.add_coin_to_blacklist(address, f"Rugcheck failed: {rugcheck_details}")
                self.db.insert_pattern(address, 'rugcheck_failed', rugcheck_details)
                print(f"Coin {token_data['name']} ({address}) failed Rugcheck: {rugcheck_details}")
                continue

            # Check for bundle purchases
            is_bundle, bundle_details = self.rugcheck.detect_bundle(token_data)
            if is_bundle:
                self.blacklist.add_coin_to_blacklist(address, f"Bundle detected: {bundle_details}")
                self.db.insert_pattern(address, 'bundle_detected', bundle_details)
                print(f"Coin {token_data['name']} ({address}) blacklisted for bundle: {bundle_details}")
                continue

            # Check for fake volume
            is_fake, fake_reason = self.fake_volume_detector.detect_fake_volume(token_data)
            if is_fake:
                self.blacklist.add_coin_to_blacklist(address, fake_reason)
                self.db.insert_pattern(address, 'fake_volume', fake_reason)
                print(f"Coin {token_data['name']} ({address}) blacklisted for fake volume: {fake_reason}")
                continue

            # Apply filters
            passed_filters, filter_reason = Filters.apply_filters(token_data, self.filters)
            if not passed_filters:
                print(f"Coin {token_data['name']} ({address}) failed filters: {filter_reason}")
                continue

            # Determine status
            token_data['status'], status_details = self.determine_status(token_data)

            # Execute trade via ToxiSol for new pairs or pumps
            if token_data['status'] in ['new_pair', 'pumped']:
                success, trade_details = self.trader.execute_trade(address, 'buy', 0.1)  # Example: Buy 0.1 SOL
                if success:
                    self.notifier.send_notification(f"Buy executed for {token_data['name']} ({address}): {trade_details}")
                    self.db.insert_pattern(address, 'buy_executed', trade_details)
                else:
                    print(f"Trade failed: {trade_details}")

            # Save token data
            self.db.insert_or_update_token(token_data)

            # Log patterns
            if token_data['status'] in ['pumped', 'rugged', 'new_pair']:
                self.db.insert_pattern(address, token_data['status'], status_details)
                print(f"Pattern detected for {token_data['name']} ({address}): {token_data['status']} - {status_details}")

    def analyze_patterns(self):
        patterns = self.db.fetch_patterns()
        print("\nPattern Analysis:")
        if not patterns:
            print("No patterns detected yet.")
        for pattern in patterns:
            print(f"Token: {pattern[1]}, Type: {pattern[2]}, Details: {pattern[4]}, Detected: {datetime.fromtimestamp(pattern[3])}")

        coins = self.db.fetch_all_coins()
        top_coins = sorted(coins, key=lambda x: x[3], reverse=True)[:10]
        print("\nTop 10 Coins by Market Cap:")
        for coin in top_coins:
            print(f"{coin[1]} ({coin[2]}): Market Cap = ${coin[3]:,.2f}, Volume = ${coin[4]:,.2f}")

    def run(self):
        while True:
            print(f"Fetching tokens at {datetime.now()}")
            tokens = self.fetch_tokens()
            if tokens:
                self.process_tokens(tokens)
                self.analyze_patterns()
            else:
                print("No tokens fetched. Check API or network.")
            print(f"Sleeping for {self.analyze_interval} seconds...\n")
            time.sleep(self.analyze_interval)

    def __del__(self):
        self.db.close()

if __name__ == "__main__":
    try:
        bot = DexscreenerBot(config_path='config.yaml')
        bot.run()
    except KeyboardInterrupt:
        print("Shutting down bot...")
    except Exception as e:
        print(f"Fatal error: {e}")
