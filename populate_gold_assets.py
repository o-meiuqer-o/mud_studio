import pandas as pd
import os
import asyncio
from playwright.async_api import async_playwright

async def main():
    file_path = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    df = pd.read_excel(file_path)
    
    os.makedirs(r'd:\portfolio\thumbnails', exist_ok=True)
    
    # Identify items that have scores but generic/missing data
    mask = (df['Relevance Score'] > 0)
    targets = df[mask]
    
    if targets.empty:
        print("No gold items need asset population.")
        return

    print(f"Updating metadata for {len(targets)} gold items...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        
        for idx in targets.index:
            url = targets.loc[idx, 'URL']
            print(f"  -> Processing {url}")
            try:
                await page.goto(url, timeout=30000, wait_until="networkidle")
                
                # Update Description if it's currently generic or empty
                current_desc = str(df.loc[idx, 'Description'])
                if not current_desc or "creative Design Thinking project" in current_desc:
                    desc = await page.evaluate("() => document.querySelector('meta[name=\"description\"]')?.content || ''")
                    if not desc:
                        # Grab first paragraph as backup
                        desc = await page.evaluate("() => document.querySelector('p')?.innerText.slice(0, 200) || ''")
                    
                    if desc:
                        df.loc[idx, 'Description'] = desc
                
                # Ensure Screenshot exists
                thumb_name = f"site_{idx}.jpg"
                thumb_path = os.path.join(r'd:\portfolio\thumbnails', thumb_name)
                if not os.path.exists(thumb_path):
                    await page.screenshot(path=thumb_path, type="jpeg", quality=60)
                
                df.loc[idx, 'Screenshot'] = f"thumbnails/{thumb_name}"
                df.to_excel(file_path, index=False)
            except Exception as e:
                print(f"Error on {url}: {e}")
                
        await browser.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
