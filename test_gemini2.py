import asyncio
from google import genai

GEMINI_API_KEY = "AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs"
client = genai.Client(api_key=GEMINI_API_KEY)

async def main():
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents="Explain how AI works in a few words",
            config=genai.types.GenerateContentConfig(temperature=0.0)
        )
        print("Success:", response.text)
    except Exception as e:
        print("Error:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
