import pandas as pd
import os

def final_recovery():
    excel_path = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    
    if not os.path.exists(excel_path):
        print("Excel missing.")
        return

    df = pd.read_excel(excel_path)
    
    # Gold Records (From earlier stable turn)
    gold_data = [
        {"url": "https://sites.google.com/view/autisticartists/home", "scores": [9, 8, 8, 7, 7]},
        {"url": "https://sites.google.com/view/ateamwithoutname/home?authuser=0", "scores": [7, 6, 7, 6, 8]},
        {"url": "https://sites.google.com/view/elite-8/home", "scores": [8, 7, 7, 6, 5]},
        {"url": "https://sites.google.com/view/red-hurricane/home", "scores": [7, 8, 6, 4, 6]},
        {"url": "https://sites.google.com/view/swishwish/home", "scores": [8, 5, 6, 5, 4]},
        {"url": "https://sites.google.com/view/no-food-waste/home", "scores": [8, 6, 7, 4, 2]},
        {"url": "https://sites.google.com/view/teamflash/home", "scores": [7, 3, 2, 3, 3]},
        {"url": "https://sites.google.com/view/siuuuuuuuuuuuuuuuuuuuuuuuuuuu/home", "scores": [7, 3, 2, 3, 4]},
        {"url": "https://sites.google.com/view/dtl-unstoppable/home", "scores": [5, 3, 2, 2, 1]},
        {"url": "https://sites.google.com/view/touristexploitation/home", "scores": [3, 2, 1, 1, 1]},
        {"url": "https://sites.google.com/view/adjustable--chair", "scores": [1, 1, 1, 1, 1]},
        {"url": "https://sites.google.com/view/ascensionmessfix/home", "scores": [1, 1, 1, 1, 1]},
        {"url": "https://sites.google.com/aiesec.net/vervoer/home", "scores": [1, 1, 1, 1, 1]},
        {"url": "https://sites.google.com/view/octowash/home", "scores": [1, 1, 1, 1, 1]}
    ]

    cols = ['Relevance Score', 'Process Documentation Score', 'Ideation Score', 'Solution Explorations Score', 'Prototype Score']
    
    for item in gold_data:
        mask = df['URL'].str.strip() == item['url'].strip()
        if any(mask):
            idx = df[mask].index[0]
            for i, col in enumerate(cols):
                df.loc[idx, col] = item['scores'][i]
            print(f"Restored {item['url']}")

    df.to_excel(excel_path, index=False)
    print("Gold Recovery Complete.")

if __name__ == "__main__":
    final_recovery()
