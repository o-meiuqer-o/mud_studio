import pandas as pd
import glob
import re
import requests
from concurrent.futures import ThreadPoolExecutor

files = glob.glob(r'd:\portfolio\*.xlsx')
urls = set()

def extract_urls(text):
    if pd.isna(text):
        return []
    text = str(text)
    # simple url regex
    return re.findall(r'(https?://[^\s]+)', text)

for f in files:
    try:
        df = pd.read_excel(f)
        for col in df.columns:
            if 'link' in col.lower() or 'website' in col.lower():
                for val in df[col]:
                    for u in extract_urls(val):
                        urls.add(u)
    except Exception as e:
        print(f"Error reading {f}: {e}")

urls_list = list(urls)
print(f"Total unique URLs found: {len(urls_list)}")

def check_url(url):
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        return url, r.status_code
    except Exception as e:
        return url, str(e)

print("Checking URLs for broken status...")
results = []
with ThreadPoolExecutor(max_workers=20) as executor:
    for res in executor.map(check_url, urls_list):
        results.append(res)

broken = [r for r in results if r[1] != 200]
working = [r for r in results if r[1] == 200]

print(f"Working URLs: {len(working)}")
print(f"Broken URLs/Errors: {len(broken)}")

import json
with open('d:\\portfolio\\url_check_results.json', 'w') as out:
    json.dump({'working': working, 'broken': broken}, out)
