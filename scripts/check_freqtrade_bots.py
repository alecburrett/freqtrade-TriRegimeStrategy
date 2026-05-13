#!/usr/bin/env python3
import sqlite3
import glob
import os

print("🤖 **Freqtrade Daily Dry-Run Update** 🤖\n")

dbs = glob.glob(os.path.join(os.getenv('FREQTRADE_DIR', '/home/alec/freqtrade'), 'user_data/trades_*.sqlite'))
for db in sorted(dbs):
    bot = db.split('trades_')[1].split('.sqlite')[0]
    if bot.lower() in ['sample', 'v3']:
        continue
        
    try:
        # Use timeout to prevent hanging if DB is locked by the bot
        conn = sqlite3.connect(db, timeout=5.0)
        c = conn.cursor()
        
        # Overall Stats
        c.execute('''
            SELECT 
                COUNT(*), 
                SUM(close_profit_abs),
                SUM(CASE WHEN close_profit_abs > 0 THEN 1 ELSE 0 END)
            FROM trades 
            WHERE is_open=0
        ''')
        row = c.fetchone()
        closed = row[0] if row and row[0] else 0
        profit = row[1] if row and row[1] else 0.0
        wins = row[2] if row and row[2] else 0
        win_rate = (wins / closed * 100) if closed > 0 else 0.0
        
        # Open trades
        c.execute('SELECT count(*) FROM trades WHERE is_open=1')
        row = c.fetchone()
        open_t = row[0] if row else 0
        
        # Best and Worst Pairs
        best_pair, worst_pair = "N/A", "N/A"
        if closed > 0:
            c.execute('SELECT pair, SUM(close_profit_abs) as p FROM trades WHERE is_open=0 GROUP BY pair ORDER BY p DESC LIMIT 1')
            b_row = c.fetchone()
            if b_row: best_pair = f"{b_row[0]} ({b_row[1]:+.2f} USDT)"
            
            c.execute('SELECT pair, SUM(close_profit_abs) as p FROM trades WHERE is_open=0 GROUP BY pair ORDER BY p ASC LIMIT 1')
            w_row = c.fetchone()
            if w_row: worst_pair = f"{w_row[0]} ({w_row[1]:+.2f} USDT)"
        
        emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
        print(f"{emoji} **{bot.upper()}**")
        print(f"├─ Profit: {profit:+.2f} USDT")
        print(f"├─ Trades: {closed} closed (Win Rate: {win_rate:.1f}%) | {open_t} open")
        if closed > 0:
            print(f"├─ Best: {best_pair}")
            print(f"└─ Worst: {worst_pair}")
        else:
            print(f"└─ No closed trades yet.")
        print()
        
    except Exception as e:
        print(f"⚠️ **{bot.upper()}**: Could not read database ({e})\n")