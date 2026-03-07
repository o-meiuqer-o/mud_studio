import asyncio
import google.generativeai as genai
import json

GEMINI_API_KEY = "AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

async def main():
    try:
        response = await asyncio.to_thread(
            model.generate_content, 
            "Hello, testing rate limits.",
            generation_config={"temperature": 0.0}
        )
        print("Success!", response.text)
    except Exception as e:
        print("EXCEPTION RAISED:")
        print(type(e))
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
