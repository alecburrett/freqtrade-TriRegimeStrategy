#!/usr/bin/env python3
import os
import subprocess

BASE_DIR = os.getenv('FREQTRADE_DIR', '/home/alec/freqtrade')
os.chdir(BASE_DIR)

print("⏳ Starting Massive 90-Day Data Download for Mega-Backtest...")
print("This will pull 1m, 5m, 15m, 1h, and 1d data for all pairs in the edge whitelist.")
print("Depending on the Binance API rate limits, this could take 10-20 minutes.")

# Using edge_backtest_config which has the big broad whitelist of 30+ pairs
cmd = [
    "docker", "compose", "run", "--rm", "freqtrade-triregime", "download-data",
    "--config", "user_data/edge_backtest_config.json",
    "-t", "1m", "5m", "15m", "1h", "1d",
    "--timerange", "20260212-20260513"
]

try:
    # Run the process and stream output to the terminal so we can see progress
    subprocess.run(cmd, check=True)
    print("✅ Massive Data Download Complete!")
except subprocess.CalledProcessError as e:
    print(f"❌ Data download failed with exit code {e.returncode}")
    exit(1)
except KeyboardInterrupt:
    print("\n🛑 Download interrupted by user.")
    exit(1)
