import pandas as pd
import time
import asyncio
from playwright.async_api import async_playwright
from google import genai
import os
import json
import urllib.parse
from PIL import Image
import io
import re

# API KEYS - Add more keys here to speed up rotation
API_KEYS = [
    "AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs",
    "AIzaSyDPsYVX1FxB8-oJwuypZyl6Nlux_62qyCM"
]

# Track the last use time for each key for the cooldown
key_last_used = {key: 0 for key in API_KEYS}
current_key_idx = 0

def get_next_client():
    global current_key_idx
    key = API_KEYS[current_key_idx]
    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
    return genai.Client(api_key=key), key

# Using Gemini 1.5 Flash (Stable) for the high 1,500 RPD quota
model_name = 'gemini-flash-latest'

async def extract_site_deep(page, base_url, max_pages=6):
    parsed_base = urllib.parse.urlparse(base_url)
    base_path = parsed_base.path
    
    paths = base_path.strip('/').split('/')
    if len(paths) >= 2 and paths[0] == 'view':
        base_path = f"/view/{paths[1]}"
        
    pages_to_visit = [base_url]
    visited = set()
    
    extracted_data = [] 
    
    while pages_to_visit and len(visited) < max_pages:
        current_url = pages_to_visit.pop(0)
        
        clean_url = current_url.split('#')[0].split('?')[0]
        if clean_url in visited:
            continue
            
        visited.add(clean_url)
        print(f"    -> Crawling: {current_url}", flush=True)
        
        try:
            await page.goto(current_url, timeout=30000, wait_until="networkidle")
            text = await page.evaluate("() => document.body.innerText")
            screenshot_bytes = await page.screenshot(full_page=True, type="jpeg", quality=50)
            
            extracted_data.append((current_url, text, screenshot_bytes))
            
            hrefs = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
            for href in hrefs:
                if not href:
                    continue
                href_clean = href.split('#')[0].split('?')[0]
                if href_clean not in visited and href_clean not in [p.split('#')[0].split('?')[0] for p in pages_to_visit]:
                    parsed_href = urllib.parse.urlparse(href_clean)
                    if parsed_href.netloc == parsed_base.netloc and parsed_href.path.startswith(base_path):
                        pages_to_visit.append(href_clean)
        except Exception as e:
            print(f"    -> Error extracting {current_url}: {e}", flush=True)
            
    return extracted_data

async def evaluate_deep_content(extracted_data):
    if not extracted_data:
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}
        
    prompt = """
You are an expert design thinking evaluator. Evaluate this student portfolio website based on 5 parameters.
You have been provided with the text content AND full-page screenshots of multiple pages from their website to evaluate their complete design process.
Look closely at the screenshots: images of prototypes, sketches, empathy maps, and diagrams are crucial for high scores.
Score each parameter strictly from 1 to 10 (1 being lowest, 10 being highest).

1. Relevance of the problem (Did they identify a clear, meaningful problem?)
2. Process documentation (Did they document their journey clearly across the pages?)
3. Ideation (Evidence of brainstorming, mind maps, sketches, multiple ideas)
4. Solution and its explorations (Depth of exploring the final solution)
5. Prototype (Visual evidence of wireframes, physical models, or final mockups shown in pictures or text)

Respond ONLY in valid JSON format with the keys: "relevance", "process", "ideation", "solution", "prototype".
Do not include any Markdown or formatting, ONLY parseable JSON.
Example: {"relevance": 8, "process": 7, "ideation": 9, "solution": 6, "prototype": 8}
"""
    
    contents_list = [prompt]
    
    for url, text, img_bytes in extracted_data:
        contents_list.append(f"--- Page URL: {url} ---")
        contents_list.append(f"Text Content:\n{text[:3000]}") 
        try:
            img = Image.open(io.BytesIO(img_bytes))
            # Optimization: 1.5 Flash handles images well, but we keep them reasonable
            img.thumbnail((1024, 4000))
            contents_list.append(img)
        except Exception:
             pass

    max_retries = 3
    for attempt in range(max_retries):
        client, key = get_next_client()
        
        # User requested 20s cooldown per key to be absolutely safe
        now = time.time()
        time_since_last = now - key_last_used[key]
        if time_since_last < 20:
            wait_time = 20 - time_since_last
            print(f"      [Key {key[:8]}...] Cooldown: Waiting {wait_time:.1f}s...", flush=True)
            await asyncio.sleep(wait_time)
            
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents_list,
                config=genai.types.GenerateContentConfig(temperature=0.0)
            )
            key_last_used[key] = time.time() # Update last used time
            
            result_text = response.text.strip()
            # Clean up JSON formatting
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            return {
                "relevance": int(data.get("relevance", 0)),
                "process": int(data.get("process", 0)),
                "ideation": int(data.get("ideation", 0)),
                "solution": int(data.get("solution", 0)),
                "prototype": int(data.get("prototype", 0))
            }
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str:
                delay = 30 # Conservative delay
                print(f"      [Key {key[:8]}...] Rate limited. Waiting {delay}s...", flush=True)
                await asyncio.sleep(delay)
            else:
                print(f"      [Key {key[:8]}...] Error in LLM evaluation: {e}", flush=True)
                if attempt == max_retries - 1:
                    return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}
                await asyncio.sleep(5)
                
    return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}

async def main():
    evaluated_file = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    input_file = r'd:\portfolio\Link_Check_Results.xlsx'
    
    if os.path.exists(evaluated_file):
        print(f"Resuming progress from {evaluated_file}...", flush=True)
        df = pd.read_excel(evaluated_file)
    else:
        print(f"Starting new evaluation from {input_file}...", flush=True)
        df = pd.read_excel(input_file)
    
    # Ensure score columns exist
    score_cols = ['Relevance Score', 'Process Documentation Score', 'Ideation Score', 'Solution Explorations Score', 'Prototype Score']
    for col in score_cols:
         if col not in df.columns:
              df[col] = ""

    working_df = df[df['Status'] == 'Working'].copy()
    
    print(f"Starting evaluation using ({model_name})...", flush=True)
    print(f"Using {len(API_KEYS)} API key(s) in rotation.", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            
            relevance = df.loc[idx, 'Relevance Score']
            # Re-evaluate if empty or 0
            if pd.notna(relevance) and str(relevance).strip() != "" and float(relevance) > 0:
                 print(f"Skipping ({idx+1}/{len(working_df)}) - Already evaluated: {url}", flush=True)
                 continue

            print(f"\nEvaluating Portfolio ({idx+1}/{len(working_df)}): {url}", flush=True)
            
            extracted_data = await extract_site_deep(page, url, max_pages=6)
            scores = await evaluate_deep_content(extracted_data)
            
            # Update values
            df.loc[idx, 'Relevance Score'] = scores['relevance']
            df.loc[idx, 'Process Documentation Score'] = scores['process']
            df.loc[idx, 'Ideation Score'] = scores['ideation']
            df.loc[idx, 'Solution Explorations Score'] = scores['solution']
            df.loc[idx, 'Prototype Score'] = scores['prototype']
            
            saved = False
            while not saved:
                try:
                    df.to_excel(evaluated_file, index=False)
                    saved = True
                except PermissionError:
                    print("Permission denied when saving. Please close 'Link_Check_Results_Evaluated.xlsx'! Retrying in 5 seconds...", flush=True)
                    await asyncio.sleep(5)
            
            print(f"  -> Scores: {scores}", flush=True)
            # Short wait between crawls
            await asyncio.sleep(2) 

        await browser.close()
    
    print(r"Done! Final file: d:\portfolio\Link_Check_Results_Evaluated.xlsx", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
