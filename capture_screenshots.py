import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

async def capture_screenshot(page, url, output_path):
    try:
        print(f"Capturing screenshot: {url}")
        # Use a reasonable timeout
        await page.goto(url, timeout=60000, wait_until="networkidle")
        # Wait a bit for images to load
        await asyncio.sleep(2)
        await page.screenshot(path=output_path, full_page=False)
        return True
    except Exception as e:
        print(f"Error capturing {url}: {e}")
        return False

async def main():
    file_path = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    if not os.path.exists(file_path):
        file_path = r'd:\portfolio\Link_Check_Results.xlsx'
    
    if not os.path.exists(file_path):
        print("No input file found!")
        return

    df = pd.read_excel(file_path)
    
    if 'Screenshot' not in df.columns:
        df['Screenshot'] = ""
    if 'Description' not in df.columns:
        df['Description'] = ""

    os.makedirs(r'd:\portfolio\thumbnails', exist_ok=True)
    
    working_df = df[df['Status'] == 'Working'].copy()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            img_name = f"site_{idx}.jpg"
            img_path = os.path.join(r'd:\portfolio\thumbnails', img_name)
            
            # Re-navigate to extract metadata even if screenshot exists
            try:
                await page.goto(url, timeout=30000, wait_until="networkidle")
                title = await page.title()
                desc = await page.evaluate("""() => {
                    const meta = document.querySelector('meta[name="description"]');
                    return meta ? meta.content : "";
                }""")
                
                # Check if current team name is generic and title is better
                current_name = str(df.loc[idx, 'Title/Team'])
                if pd.isna(current_name) or "Unnamed" in current_name or len(current_name) < 3:
                     if title: df.loc[idx, 'Title/Team'] = title[:100]
                
                if desc and (pd.isna(df.loc[idx, 'Description']) or len(str(df.loc[idx, 'Description'])) < 10):
                    df.loc[idx, 'Description'] = desc[:300]
            except:
                pass

            # If thumbnail exists and is not empty, skip screenshot but keep metadata
            if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:
                df.loc[idx, 'Screenshot'] = f"thumbnails/{img_name}"
            else:
                success = await capture_screenshot(page, url, img_path)
                if success:
                    df.loc[idx, 'Screenshot'] = f"thumbnails/{img_name}"
            
            # Save periodically
            df.to_excel(file_path, index=False)
        
        await browser.close()
    
    df.to_excel(file_path, index=False)
    print(f"Done! Screenshots and metadata updated in {file_path}.")

if __name__ == "__main__":
    asyncio.run(main())
