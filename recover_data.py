import pandas as pd
import json
import os

def recover_scores():
    json_path = r'd:\portfolio\top_portfolios.json'
    excel_path = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    
    if not os.path.exists(json_path) or not os.path.exists(excel_path):
        print("Required files missing for recovery.")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)
    
    df = pd.read_excel(excel_path)
    
    # Map from JSON to Excel
    count = 0
    for item in data:
        url = item['URL']
        # Try exact match first
        matching_rows = df[df['URL'] == url]
        if matching_rows.empty:
            # Try strip and lowercase
            matching_rows = df[df['URL'].str.strip() == url.strip()]
            
        if not matching_rows.empty:
            idx = matching_rows.index[0]
            val = item.get('Total Score', 1.0)
            df.loc[idx, 'Relevance Score'] = val
            print(f"Matched {url} -> {val}")
            count += 1
        else:
            print(f"No match for {url}")

    df.to_excel(excel_path, index=False)
    print(f"Successfully saved {count} recovered items.")

if __name__ == "__main__":
    recover_scores()
