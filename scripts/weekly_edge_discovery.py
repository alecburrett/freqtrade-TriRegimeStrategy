#!/usr/bin/env python3
import os, json, subprocess, datetime, glob

FREQTRADE_DIR = os.getenv('FREQTRADE_DIR', '/home/alec/freqtrade')
os.chdir(FREQTRADE_DIR)

broad_coins = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", 
    "AVAX/USDT", "SHIB/USDT", "DOT/USDT", "LINK/USDT", "TRX/USDT", "MATIC/USDT", 
    "NEAR/USDT", "UNI/USDT", "LTC/USDT", "APT/USDT", "SUI/USDT", "OP/USDT", 
    "ARB/USDT", "FIL/USDT", "INJ/USDT", "RNDR/USDT", "FET/USDT", "TON/USDT", 
    "PEPE/USDT", "ONDO/USDT", "TAO/USDT", "PAXG/USDT", "WIF/USDT", "BCH/USDT"
]

print("🔍 **Weekly Edge Discovery Completed**\n")

# 1. Create temp config
try:
    with open("user_data/config_triregime.json", "r") as f:
        temp_config = json.load(f)
    temp_config["pairlists"] = [{"method": "StaticPairList"}]
    temp_config["exchange"]["pair_whitelist"] = broad_coins
    with open("user_data/edge_backtest_config.json", "w") as f:
        json.dump(temp_config, f)
except Exception as e:
    print(f"❌ Failed to setup config: {e}")
    exit(1)

# 2. Download Data
result = subprocess.run([
    "docker", "compose", "run", "--rm", "freqtrade-triregime", "download-data", 
    "--config", "user_data/edge_backtest_config.json", "--days", "30", "-t", "15m", "1h"
], capture_output=True)
if result.returncode != 0:
    print(f"❌ Failed to download data: {result.stderr.decode()}")
    exit(1)

# 3. Run Backtest
start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y%m%d")
subprocess.run([
    "docker", "compose", "run", "--rm", "freqtrade-triregime", "backtesting", 
    "--strategy", "TriRegimeStrategy", "--config", "user_data/edge_backtest_config.json", 
    "--timerange", f"{start_date}-"
], capture_output=True)

# 4. Parse Results
results_files = glob.glob("user_data/backtest_results/*meta.json")
if not results_files:
    print("❌ Failed to find backtest results.")
    exit(1)
    
latest_file = max(results_files, key=os.path.getctime)
with open(latest_file, "r") as f:
    bt_data = json.load(f)
    
strategy_stats = bt_data["strategy"]["TriRegimeStrategy"]["results_per_pair"]

valid_pairs = []
for p in strategy_stats:
    if p["key"] == "TOTAL": continue
    trades = p["trades"]
    if trades < 3: continue
    win_rate = (p["wins"] / trades) * 100 if trades > 0 else 0
    profit = p["profit_total_abs"]
    if win_rate > 50 and profit > 0:
        valid_pairs.append({"pair": p["key"], "profit": profit, "win_rate": win_rate, "trades": trades})

valid_pairs.sort(key=lambda x: x["profit"], reverse=True)
top_10 = valid_pairs[:10]
top_10_pairs = [x["pair"] for x in top_10]

if len(top_10) == 0:
    print("⚠️ No pairs met the edge criteria this week. Keeping existing whitelist.")
    exit(0)

# Ensure BTC/ETH are present for AI correlation features
if "BTC/USDT" not in top_10_pairs: top_10_pairs.append("BTC/USDT")
if "ETH/USDT" not in top_10_pairs: top_10_pairs.append("ETH/USDT")

# 5. Inject into configs (Updating both TriRegime bots for maximum synergy)
for config_file in ["user_data/config_triregime_ai.json", "user_data/config_triregime.json"]:
    try:
        with open(config_file, "r") as f:
            cfg = json.load(f)
        cfg["pairlists"] = [{"method": "StaticPairList"}]
        cfg["exchange"]["pair_whitelist"] = top_10_pairs
        with open(config_file, "w") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"❌ Failed to update config: {e}")

# 6. Restart Bots
subprocess.run(["docker", "restart", "freqtrade-triregime", "freqtrade-triregime-ai"], capture_output=True)

# 7. Report
print("✅ **New Pairs Locked In & Bots Restarted:**")
for p in top_10:
    print(f"├─ {p['pair']}: +{p['profit']:.2f} USDT ({p['win_rate']:.1f}% WR)")
print(f"└─ (Total tracked pairs: {len(top_10_pairs)})\n")
print("_The AI model will auto-download 5m data and retrain on these new pairs._")