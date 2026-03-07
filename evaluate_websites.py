import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import google.generativeai as genai
import os
import time
import json

# PLACE YOUR FREE GEMINI API KEY HERE
# Get it for free at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = "AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs"

genai.configure(api_key=GEMINI_API_KEY)

# Using Gemini 2.5 Flash as it is fast and has a good free tier
model = genai.GenerativeModel('gemini-2.5-flash')

async def extract_text(page, url):
    try:
        # Increase timeout just in case it's a slow website
        await page.goto(url, timeout=45000, wait_until="networkidle")
        
        # Try to expand any "Read more" or evaluate text properly if it's a Google Site
        text = await page.evaluate("() => document.body.innerText")
        return text
    except Exception as e:
        print(f"Error extracting {url}: {e}")
        return ""

async def evaluate_content(text):
    if not text or len(text.strip()) < 50:
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}
    
    prompt = f"""
You are an expert design thinking evaluator. Evaluate the following website content based on 5 parameters.
Score each parameter strictly from 1 to 10 (1 being lowest, 10 being highest).
If the website lacks information for a category, score it 0 or 1.

1. Relevance of the problem
2. Process documentation
3. Ideation
4. Solution and its explorations
5. Prototype

Website Content:
{text[:25000]}

Respond ONLY in valid JSON format with the keys: "relevance", "process", "ideation", "solution", "prototype".
Do not include any Markdown or formatting, ONLY parseable JSON.
Example: {{"relevance": 8, "process": 7, "ideation": 9, "solution": 6, "prototype": 8}}
"""
    try:
        # We need to run synchronous Gemini call in a thread or just await loop.run_in_executor
        response = await asyncio.to_thread(
            model.generate_content, 
            prompt,
            # Force JSON format if possible, or temperature 0
            generation_config={"temperature": 0.0}
        )
        result_text = response.text.strip()
        # Clean up any potential markdown formatting the LLM might return
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()

        data = json.loads(result_text)
        return {
            "relevance": int(data.get("relevance", 0)),
            "process": int(data.get("process", 0)),
            "ideation": int(data.get("ideation", 0)),
            "solution": int(data.get("solution", 0)),
            "prototype": int(data.get("prototype", 0))
        }
    except Exception as e:
        print(f"Error in LLM evaluation: {e}")
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}

async def main():
    if GEMINI_API_KEY == "YOUR-FREE-GEMINI-API-KEY-HERE":
        print("Please set your Gemini API key in the script before running!")
        print("You can get one for FREE at: https://aistudio.google.com/app/apikey")
        return

    input_file = r'd:\portfolio\Link_Check_Results.xlsx'
    df = pd.read_excel(input_file)
    
    # We only process Working URLs that haven't been evaluated yet
    working_df = df[df['Status'] == 'Working'].copy()
    
    # Make sure score columns exist
    score_cols = ['Relevance Score', 'Process Documentation Score', 'Ideation Score', 'Solution Explorations Score', 'Prototype Score']
    for col in score_cols:
         if col not in working_df.columns:
              working_df[col] = ""

    print(f"Starting evaluation of {len(working_df)} working websites...")
    
    async with async_playwright() as p:
        # Launching headless browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            
            # Skip if already evaluated
            if pd.notna(working_df.loc[idx, 'Relevance Score']) and str(working_df.loc[idx, 'Relevance Score']).strip() != "":
                 print(f"Skipping ({idx+1}/{len(working_df)}) - Already Evaluated: {url}")
                 continue

            print(f"Evaluating ({idx+1}/{len(working_df)}): {url}")
            
            text = await extract_text(page, url)
            scores = await evaluate_content(text)
            
            working_df.loc[idx, 'Relevance Score'] = scores['relevance']
            working_df.loc[idx, 'Process Documentation Score'] = scores['process']
            working_df.loc[idx, 'Ideation Score'] = scores['ideation']
            working_df.loc[idx, 'Solution Explorations Score'] = scores['solution']
            working_df.loc[idx, 'Prototype Score'] = scores['prototype']
            
            # Save incrementally so that if it crashes we don't lose progress
            saved = False
            while not saved:
                try:
                    working_df.to_excel(r'd:\portfolio\Link_Check_Results_Evaluated.xlsx', index=False)
                    saved = True
                except PermissionError:
                    print("Permission denied when saving. Please close the 'Link_Check_Results_Evaluated.xlsx' file! Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            
            # small delay to prevent rate limits on the free tier (15 requests per minute usually)
            print(f"  -> Scores: {scores}")
            await asyncio.sleep(4) # Wait 4 seconds to comply with typical free API rate limits

        await browser.close()
    
    print("Done! Saved to d:\\portfolio\\Link_Check_Results_Evaluated.xlsx")

if __name__ == "__main__":
    asyncio.run(main())
