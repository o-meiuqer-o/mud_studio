import pandas as pd
import json
import os

def export_leaderboard():
    file_path = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    if not os.path.exists(file_path):
        file_path = r'd:\portfolio\Link_Check_Results.xlsx'
    
    if not os.path.exists(file_path):
        print("No source file found!")
        return

    df = pd.read_excel(file_path)
    # Total score calculation
    score_cols = ['Relevance Score', 'Process Documentation Score', 'Ideation Score', 'Solution Explorations Score', 'Prototype Score']
    
    # Convert to numeric, handle errors
    for col in score_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if all(col in df.columns for col in score_cols):
        df['Total Score'] = df[score_cols].sum(axis=1)
    else:
        df['Total Score'] = 0
    
    # Sort by Total Score
    hq_df = df.sort_values(by='Total Score', ascending=False)
    
    # Filter for HQ only (Total Score > 25 as per user request)
    showcase_df = hq_df[hq_df['Total Score'] > 25]
    
    # If nothing is above 25, we show nothing (empty gallery) to maintain strict quality
    if showcase_df.empty:
        print("No portfolios met the >25 score threshold.")
        top_entries = []
    else:
        # Ensure relevant columns exist
        cols_to_include = ['File', 'Title/Team', 'URL', 'Status', 'Total Score', 'Description', 'Screenshot']
        for col in cols_to_include:
            if col not in showcase_df.columns:
                showcase_df[col] = "A creative Design Thinking project." if col == 'Description' else ""
                
        top_entries = showcase_df[cols_to_include].head(30).to_dict(orient='records')
    
    # Save as JSON for the website
    with open(r'd:\portfolio\top_portfolios.json', 'w') as f:
        json.dump(top_entries, f, indent=4)
    
    # Also save as a JS variable for easy loading via <script> tag
    with open(r'd:\portfolio\top_portfolios.js', 'w') as f:
        f.write(f"const topPortfolios = {json.dumps(top_entries, indent=4)};")

    print(f"Exported {len(top_entries)} portfolios to gallery.")

if __name__ == "__main__":
    export_leaderboard()
