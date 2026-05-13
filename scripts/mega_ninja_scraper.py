import urllib.request
import re
import os
import time
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://strat.ninja/strats.php"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

print("📡 Fetching strat.ninja database...")
try:
    response = urllib.request.urlopen(req, context=ctx)
    html = response.read().decode('utf-8')
except Exception as e:
    print(f"Failed to fetch {url}: {e}")
    exit(1)

# Extract raw github blob links
links = re.findall(r'href="(https://github.com/[^"]+\.py)"', html)
print(f"🎯 Found {len(links)} strategy links!")

out_dir = "/home/alec/freqtrade/user_data/strategies/mega_test"
os.makedirs(out_dir, exist_ok=True)

success = 0
for link in set(links):  # use set() to remove duplicates
    # Convert github blob to rawusercontent for direct download
    raw_url = link.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
    file_name = raw_url.split('/')[-1]
    out_path = os.path.join(out_dir, file_name)
    
    # Don't overwrite if it already exists (e.g. from the aggregator)
    if os.path.exists(out_path):
        continue
        
    try:
        urllib.request.urlretrieve(raw_url, out_path)
        success += 1
        time.sleep(0.2) # be nice to github
    except Exception as e:
        print(f"Failed to download {file_name}: {e}")
        
print(f"✅ Downloaded {success} NEW strategies into {out_dir}")
