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
# API RESOURCES
import base64

GEMINI_KEYS = [
    "AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs",
    "AIzaSyDPsYVX1FxB8-oJwuypZyl6Nlux_62qyCM",
    "AIzaSyAAu_z0QAT4F2jFbL8IXTkq9ILL24S4XMQ"
]
GEMINI_MODELS = [
    'gemini-flash-latest',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite'
]

OPENAI_KEYS = [
    "PLEASE_SET_YOUR_API_KEY_HERE"
]

ALL_RESOURCES = []
for k in GEMINI_KEYS:
    for m in GEMINI_MODELS:
        ALL_RESOURCES.append(("gemini", k, m))

for k in OPENAI_KEYS:
    for m in ["gpt-4o-mini", "gpt-4o"]:
        ALL_RESOURCES.append(("openai", k, m))

# Quota Tracking
model_last_used = {(api, key, model): 0 for api, key, model in ALL_RESOURCES}
current_resource_idx = 0

def get_next_resource():
    global current_resource_idx
    res = ALL_RESOURCES[current_resource_idx]
    current_resource_idx = (current_resource_idx + 1) % len(ALL_RESOURCES)
    return res

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

async def evaluate_with_rotation(extracted_data):
    if not extracted_data:
        return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0, "summary": "No data found."}
        
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

Respond ONLY in valid JSON: {"relevance": N, "process": N, "ideation": N, "solution": N, "prototype": N, "summary": "..."}
"""
    from openai import AsyncOpenAI

    # Gemini Payload
    gemini_contents = [prompt]
    # OpenAI Payload
    openai_contents = [{"type": "text", "text": prompt}]

    for _, text, img_bytes in extracted_data:
        gemini_contents.append(f"Text Content:\n{text[:2000]}")
        openai_contents.append({"type": "text", "text": f"Text Content:\n{text[:2000]}"})
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((1024, 2000))
            gemini_contents.append(img)
            
            # OpenAI requires base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=70)
            img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            openai_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })
        except: pass

    max_attempts = len(ALL_RESOURCES) * 2
    
    for attempt in range(max_attempts):
        api, key, model = get_next_resource()
        
        now = time.time()
        last_used = model_last_used.get((api, key, model), 0)
        gap = now - last_used
        if gap < 15: 
            await asyncio.sleep(15 - gap)

        try:
            print(f"      Attempt {attempt+1}: [{api.upper()} Key {key[:6]}...] with [{model}]...", flush=True)
            
            if api == "gemini":
                client = genai.Client(api_key=key)
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=gemini_contents,
                    config=genai.types.GenerateContentConfig(temperature=0.0)
                )
                result_text = response.text.strip()
            elif api == "openai":
                client = AsyncOpenAI(api_key=key)
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": openai_contents}],
                    temperature=0.0
                )
                result_text = response.choices[0].message.content.strip()
            
            model_last_used[(api, key, model)] = time.time()
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "{" in result_text:
                 result_text = result_text[result_text.find("{"):result_text.rfind("}")+1]
            
            data = json.loads(result_text)
            res = {k: int(data.get(k, 0)) for k in ["relevance", "process", "ideation", "solution", "prototype"]}
            res["summary"] = data.get("summary", "A creative Design Thinking project.")
            return res
            
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "resource_exhausted" in err or "rate_limit" in err:
                print(f"      [429] Limit hit for {model}. Rotating...", flush=True)
                await asyncio.sleep(10)
            else:
                print(f"      Error ({model}): {e}", flush=True)
                await asyncio.sleep(5)
                
    print("!!! FAILED: Exhausted all resources. 'Power Nap' for 60s to refill quota...", flush=True)
    await asyncio.sleep(60)
    return {"relevance": 0, "process": 0, "ideation": 0, "solution": 0, "prototype": 0, "summary": "Evaluation failed."}

async def main():
    evaluated_file = r'd:\portfolio\Link_Check_Results_Evaluated.xlsx'
    df = pd.read_excel(evaluated_file)
    
    # Initialize columns if they don't exist
    for col in ['Description', 'Screenshot']:
        if col not in df.columns:
            df[col] = ""
    
    os.makedirs(r'd:\portfolio\thumbnails', exist_ok=True)
    
    working_df = df[df['Status'] == 'Working'].copy()
    print(f"Starting HQ evaluation with Smart Rotation ({len(ALL_RESOURCES)} API resource combinations)...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        for idx in working_df.index:
            url = working_df.loc[idx, 'URL']
            score = df.loc[idx, 'Relevance Score']
            
            # HQ Check: Re-evaluate if empty, NaN, OR 0.0 (prev failure)
            if pd.notna(score) and str(score).strip() != "":
                if float(score) > 0:
                     continue
                
                # If score is 0, check if it was a valid evaluation (it has a real summary)
                desc = str(df.loc[idx, 'Description'])
                if float(score) == 0.0 and desc and desc != "nan" and desc != "Evaluation failed." and desc != "A creative Design Thinking project.":
                     continue

            print(f"\n[HQ Check] Evaluating ({idx+1}/{len(df)}): {url}", flush=True)
            extracted_data, metadata = await extract_site_deep(page, url, max_pages=6)
            
            if not extracted_data:
                print(f"    -> Warning: No data extracted for {url}", flush=True)
                continue

            # Save Thumbnail (First image in extracted_data is the home page)
            _, _, home_img_bytes = extracted_data[0]
            thumb_name = f"site_{idx}.jpg"
            thumb_path = os.path.join(r'd:\portfolio\thumbnails', thumb_name)
            with open(thumb_path, 'wb') as f:
                f.write(home_img_bytes)
            
            df.loc[idx, 'Screenshot'] = f"thumbnails/{thumb_name}"

            scores = await evaluate_with_rotation(extracted_data)
            
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
            
            # Set description: AI Summary if available, else meta-description
            ai_summary = scores.get("summary", "")
            if ai_summary and "failed" not in ai_summary.lower():
                df.loc[idx, 'Description'] = ai_summary
            elif metadata["description"]:
                df.loc[idx, 'Description'] = metadata["description"]

            # Set Title if generic
            current_title = str(df.loc[idx, 'Title/Team'])
            if ("Unnamed" in current_title or len(current_title) < 3) and metadata["title"]:
                df.loc[idx, 'Title/Team'] = metadata["title"][:100]

            print(f"    DEBUG: Updated Row {idx} Relevance -> {df.loc[idx, 'Relevance Score']}", flush=True)

            # Safe Save
            for _ in range(5):
                try:
                    df.to_excel(evaluated_file, index=False)
                    print(f"    DEBUG: File saved successfully to {evaluated_file}", flush=True)
                    # Trigger leaderboard update
                    import subprocess
                    subprocess.run(["python", "export_leaderboard.py"], capture_output=True)
                    break
                except PermissionError:
                    print("Waiting for Excel to close...", flush=True)
                    await asyncio.sleep(5)
            
            print(f"  -> HQ Result: {scores}", flush=True)
            await asyncio.sleep(5) 

        await browser.close()
    print("Full Evaluation Complete!")

if __name__ == "__main__":
    asyncio.run(main())
