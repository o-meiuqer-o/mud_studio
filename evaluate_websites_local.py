import pandas as pd
import time
import asyncio
from playwright.async_api import async_playwright
import ollama
import os
import json
import urllib.parse
from PIL import Image
import io
import re

# Model used for local evaluation
# llama3.2-vision:11b is the high-quality multimodal model
MODEL_NAME = 'llama3.2-vision:11b'

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
            screenshot_bytes = await page.screenshot(full_page=True, type="jpeg", quality=40)
            
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

async def evaluate_deep_content_local(extracted_data):
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
    
    # Llama 3.2 Vision uses a messages format
    # We'll combine the content from all pages. 
    # For now, we take the primary page and up to 3 subpages to avoid overwhelming the model context
    
    combined_text = prompt + "\n\nWebsite Content:\n"
    images = []
    
    for url, text, img_bytes in extracted_data[:4]: # Limit to 4 images/pages total for local speed
         combined_text += f"\n--- URL: {url} ---\n{text[:2000]}\n"
         images.append(img_bytes)

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': combined_text,
                'images': images
            }]
        )
        
        result_text = response['message']['content'].strip()
        
        # Clean up JSON if model adds markdown blocks
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
        print(f"      -> Error in Local LLM evaluation: {e}", flush=True)
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0}

async def main():
    # Use Evaluated file if it exists to resume progress
    evaluated_file = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    input_file = r'd:\portfolio\Link_Check_Results.xlsx'
    
    if os.path.exists(evaluated_file):
        print(f"Resuming from {evaluated_file}...", flush=True)
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
    
    print(f"Starting FULL LOCAL evaluation using Ollama ({MODEL_NAME})...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            
            relevance = working_df.loc[idx, 'Relevance Score']
            # Re-evaluate it if it's empty, NaN, or 0
            if pd.notna(relevance) and str(relevance).strip() != "" and float(relevance) > 0:
                 print(f"Skipping ({idx+1}/{len(working_df)}) - Already evaluated: {url}", flush=True)
                 continue

            print(f"\nEvaluating Locally ({idx+1}/{len(working_df)}): {url}", flush=True)
            
            extracted_data = await extract_site_deep(page, url, max_pages=6)
            scores = await evaluate_deep_content_local(extracted_data)
            
            # Update the main dataframe
            for col_name, score_val in scores.items():
                col_display = col_name.capitalize() + " Score"
                if "Relevance" in col_display: col_display = "Relevance Score"
                elif "Process" in col_display: col_display = "Process Documentation Score"
                elif "Ideation" in col_display: col_display = "Ideation Score"
                elif "Solution" in col_display: col_display = "Solution Explorations Score"
                elif "Prototype" in col_display: col_display = "Prototype Score"
                
                df.loc[idx, col_display] = score_val
            
            saved = False
            while not saved:
                try:
                    df.to_excel(evaluated_file, index=False)
                    saved = True
                except PermissionError:
                    print("Permission denied when saving. Please close the 'Link_Check_Results_Evaluated.xlsx' file! Retrying in 5 seconds...", flush=True)
                    await asyncio.sleep(5)
            
            print(f"  -> Local Scores: {scores}", flush=True)

        await browser.close()
    
    print(r"Done! Saved to d:\portfolio\Link_Check_Results_Evaluated.xlsx", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
