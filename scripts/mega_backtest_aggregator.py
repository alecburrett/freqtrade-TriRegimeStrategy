#!/usr/bin/env python3
import os
import shutil
import glob
from pathlib import Path

# Paths
BASE_DIR = os.getenv('FREQTRADE_DIR', '/home/alec/freqtrade')
STRATEGIES_DIR = os.path.join(BASE_DIR, 'user_data/strategies')
MEGA_TEST_DIR = os.path.join(STRATEGIES_DIR, 'mega_test')

# Source directories to scan
SOURCES = [
    os.path.join(STRATEGIES_DIR, 'freqtrade-strategies'),
    os.path.join(STRATEGIES_DIR, 'NostalgiaForInfinity'),
    os.path.expanduser('~/ninja.strat'),
    os.path.expanduser('~/freqtrade-ninja')  # Adding common aliases
]

def aggregate_strategies():
    os.makedirs(MEGA_TEST_DIR, exist_ok=True)
    
    count = 0
    for source in SOURCES:
        if not os.path.exists(source):
            print(f"⚠️ Source not found: {source}")
            continue
            
        print(f"🔍 Scanning {source}...")
        
        # Search recursively for .py files
        for py_file in Path(source).rglob('*.py'):
            if py_file.name == '__init__.py':
                continue
                
            dest_file = os.path.join(MEGA_TEST_DIR, py_file.name)
            
            # Avoid overwriting with older versions, or handle duplicates
            # For simplicity, we just copy it over, optionally appending a suffix if collision occurs
            if os.path.exists(dest_file):
                # Try to deduplicate by appending parent folder name
                base_name = py_file.stem
                parent_name = py_file.parent.name
                dest_file = os.path.join(MEGA_TEST_DIR, f"{base_name}_{parent_name}.py")
            
            try:
                shutil.copy2(py_file, dest_file)
                count += 1
            except Exception as e:
                print(f"❌ Failed to copy {py_file.name}: {e}")
                
    print(f"✅ Aggregation complete! Copied {count} strategies to {MEGA_TEST_DIR}")

if __name__ == '__main__':
    aggregate_strategies()
