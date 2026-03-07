import pandas as pd
import glob
import re
import requests
import os
from concurrent.futures import ThreadPoolExecutor

files = glob.glob(r'd:\portfolio\*.xlsx')

def extract_urls(text):
    if pd.isna(text):
        return []
    text = str(text)
    return re.findall(r'(https?://[^\s]+)', text)

def check_url(url):
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            return "Working"
        else:
            return f"Broken ({r.status_code})"
    except Exception as e:
        return "Broken (Error)"

all_data = []

# Collect all entries that contain a URL
for f in files:
    try:
        df = pd.read_excel(f)
        for idx, row in df.iterrows():
            project_info = ""
            for col in ['Team Name', 'Project Title', 'Name']:
                # Find column that matches partially
                matched_cols = [c for c in df.columns if col.lower() in c.lower()]
                if matched_cols:
                    val = row[matched_cols[0]]
                    if pd.notna(val):
                        project_info = str(val)
                        break
            
            # Find the url columns
            url_cols = [c for c in df.columns if 'link' in c.lower() or 'website' in c.lower()]
            for uc in url_cols:
                urls = extract_urls(row[uc])
                for u in urls:
                    all_data.append({
                        'File': os.path.basename(f),
                        'Title/Team': project_info,
                        'URL': u
                    })
    except Exception as e:
        print(f"Error reading {f}: {e}")

df_results = pd.DataFrame(all_data).drop_duplicates(subset=['URL'])
urls_list = df_results['URL'].tolist()

print(f"Checking {len(urls_list)} URLs...")
with ThreadPoolExecutor(max_workers=20) as executor:
    statuses = list(executor.map(check_url, urls_list))

df_results['Status'] = statuses
df_results['Relevance Score'] = ""
df_results['Process Documentation Score'] = ""
df_results['Ideation Score'] = ""
df_results['Solution Explorations Score'] = ""
df_results['Prototype Score'] = ""

output_file = r'd:\portfolio\Link_Check_Results.xlsx'
df_results.to_excel(output_file, index=False)
print(f"Saved results to {output_file}")
