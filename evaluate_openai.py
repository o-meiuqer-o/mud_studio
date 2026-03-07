import pandas as pd
import time
import asyncio
from playwright.async_api import async_playwright
import os
import json
import urllib.parse
from PIL import Image
import io
import base64
from openai import AsyncOpenAI

# OPENAI API
OPENAI_KEY = "PLEASE_SET_YOUR_API_KEY_HERE"
MODEL = "gpt-4o-mini"
client = AsyncOpenAI(api_key=OPENAI_KEY)

async def extract_site_deep(page, base_url, max_pages=6):
    parsed_base = urllib.parse.urlparse(base_url)
    base_path = parsed_base.path
    
    paths = base_path.strip('/').split('/')
    if len(paths) >= 2 and paths[0] == 'view':
        base_path = f"/view/{paths[1]}"
        
    pages_to_visit = [base_url]
    visited = set()
    extracted_data = [] 
    metadata = {"title": "", "description": ""}
    
    while pages_to_visit and len(visited) < max_pages:
        current_url = pages_to_visit.pop(0)
        clean_url = current_url.split('#')[0].split('?')[0]
        if clean_url in visited: continue
            
        visited.add(clean_url)
        print(f"    -> Crawling: {current_url}", flush=True)
        
        try:
            await page.goto(current_url, timeout=30000, wait_until="networkidle")
            
            # Extract basic metadata from home page
            if len(visited) == 1:
                metadata["title"] = await page.title()
                metadata["description"] = await page.evaluate("() => document.querySelector('meta[name=\"description\"]')?.content || ''")

            text = await page.evaluate("() => document.body.innerText")
            screenshot_bytes = await page.screenshot(full_page=True, type="jpeg", quality=40)
            
            extracted_data.append((current_url, text, screenshot_bytes))
            
            hrefs = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
            for href in hrefs:
                if not href: continue
                href_clean = href.split('#')[0].split('?')[0]
                if href_clean not in visited:
                    parsed_href = urllib.parse.urlparse(href_clean)
                    if parsed_href.netloc == parsed_base.netloc and parsed_href.path.startswith(base_path):
                        pages_to_visit.append(href_clean)
        except Exception as e:
            print(f"    -> Crawl Error {current_url}: {e}", flush=True)
            
    return extracted_data, metadata

async def evaluate_openai(extracted_data):
    if not extracted_data:
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0, "summary": "No data found.", "criticism": "Website could not be accessed."}
        
    prompt = """
You are an expert design thinking evaluator. Evaluate this student portfolio website based on 5 parameters.
You have been provided with the text content AND full-page screenshots of multiple pages.
Score each parameter strictly from 1 to 10 (1-lowest, 10-highest). 
Return 0 only if NO evidence is found for that category.

1. Relevance of the problem
2. Process documentation
3. Ideation (Brainstorming, mind maps, sketches)
4. Solution explorations
5. Prototype (Physical/digital mockups)

Also, provide a 1-sentence inspiring summary of the project.
Finally, provide a sharp, constructive criticism about the project's shortcomings or what it lacks.

Respond ONLY in valid JSON format:
{"relevance": N, "process": N, "ideation": N, "solution": N, "prototype": N, "summary": "...", "criticism": "..."}
"""
    
    openai_contents = [{"type": "text", "text": prompt}]

    for _, text, img_bytes in extracted_data:
        openai_contents.append({"type": "text", "text": f"Text Content:\n{text[:2000]}"})
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((1024, 2000))
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=70)
            img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            openai_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })
        except: pass

    for attempt in range(5): # Up to 5 retries
        try:
            print(f"      Attempt {attempt+1}: [OPENAI] with [{MODEL}]...", flush=True)
            
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": openai_contents}],
                temperature=0.0
            )
            result_text = response.choices[0].message.content.strip()
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "{" in result_text:
                 result_text = result_text[result_text.find("{"):result_text.rfind("}")+1]
            
            data = json.loads(result_text)
            res = {k: int(data.get(k, 0)) for k in ["relevance", "process", "ideation", "solution", "prototype"]}
            res["summary"] = data.get("summary", "A creative Design Thinking project.")
            res["criticism"] = data.get("criticism", "")
            return res
            
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate limit" in err or "quota" in err:
                print(f"      [429] Limit hit. Sleeping for 20s...", flush=True)
                await asyncio.sleep(20)
            else:
                print(f"      Error: {e}", flush=True)
                await asyncio.sleep(5)
                
    print("!!! FAILED: Exhausted all retries.", flush=True)
    return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0, "summary": "Evaluation failed.", "criticism": "Failed due to API limits/errors."}

async def main():
    source_file = r'd:\portfolio\Link_Check_Results.xlsx'
    evaluated_file = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    
    # Check if evaluated exists to resume, otherwise start from scratch
    if os.path.exists(evaluated_file):
        df = pd.read_excel(evaluated_file)
        # If user wants a complete redo, we could wipe the scores, but it's safer to just overwrite if they don't have the new 'Criticism' column
        if 'Criticism' not in df.columns:
            # Complete redo requested: Reset scores and description
            print("Restarting evaluation with OpenAI and adding Criticism column...")
            df = pd.read_excel(source_file)
            for col in ['Relevance Score', 'Process Documentation Score', 'Ideation Score', 'Solution Explorations Score', 'Prototype Score']:
                df[col] = pd.NA
    else:
        df = pd.read_excel(source_file)
    
    # Initialize columns if they don't exist
    for col in ['Description', 'Screenshot', 'Criticism']:
        if col not in df.columns:
            df[col] = ""
    
    os.makedirs(r'd:\portfolio\thumbnails', exist_ok=True)
    
    working_df = df[df['Status'] == 'Working'].copy()
    print(f"Starting NEW evaluation with OpenAI ({len(working_df)} sites to check)...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            score = df.loc[idx, 'Relevance Score']
            criticism = df.loc[idx, 'Criticism']
            
            # Check if already processed in this new run (has score AND criticism)
            if pd.notna(score) and str(score).strip() != "" and str(criticism).strip() != "":
                 continue

            print(f"\n[OpenAI Eval] ({idx+1}/{len(df)}): {url}", flush=True)
            extracted_data, metadata = await extract_site_deep(page, url, max_pages=6)
            
            if not extracted_data:
                print(f"    -> Warning: No data extracted for {url}", flush=True)
                continue

            # Save Thumbnail 
            _, _, home_img_bytes = extracted_data[0]
            thumb_name = f"site_{idx}.jpg"
            thumb_path = os.path.join(r'd:\portfolio\thumbnails', thumb_name)
            with open(thumb_path, 'wb') as f:
                f.write(home_img_bytes)
            
            df.loc[idx, 'Screenshot'] = f"thumbnails/{thumb_name}"

            # Evaluate with OpenAI
            scores = await evaluate_openai(extracted_data)
            
            # Map back to Excel columns
            cols = {
                'relevance': 'Relevance Score',
                'process': 'Process Documentation Score',
                'ideation': 'Ideation Score',
                'solution': 'Solution Explorations Score',
                'prototype': 'Prototype Score'
            }
            for key, col in cols.items():
                df.loc[idx, col] = scores[key]
            
            df.loc[idx, 'Criticism'] = scores.get("criticism", "")
            
            ai_summary = scores.get("summary", "")
            if ai_summary and "failed" not in ai_summary.lower():
                df.loc[idx, 'Description'] = ai_summary
            elif metadata["description"]:
                df.loc[idx, 'Description'] = metadata["description"]

            # Set Title if generic
            current_title = str(df.loc[idx, 'Title/Team'])
            if current_title.lower() in ['nan', 'untitled', 'home']:
                if metadata["title"] and metadata["title"].lower() not in ['home', 'untitled']:
                    df.loc[idx, 'Title/Team'] = metadata["title"]
            
            # Safe Save
            for _ in range(5):
                try:
                    df.to_excel(evaluated_file, index=False)
                    score_val = sum([scores.get(k,0) for k in ['relevance', 'process', 'ideation', 'solution', 'prototype']])
                    print(f"    DEBUG: Row {idx} updated. Total: {score_val}", flush=True)
                    break
                except PermissionError:
                    print("Waiting for Excel to close...", flush=True)
                    await asyncio.sleep(5)
            
            # Trigger Leaderboard Export
            try:
                os.system("python export_leaderboard.py")
            except: pass

        await browser.close()
    
    print("\nDONE: All websites evaluated with OpenAI!")

if __name__ == "__main__":
    asyncio.run(main())
