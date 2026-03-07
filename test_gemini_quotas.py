import asyncio
from google import genai

GEMINI_API_KEY = "api key"
client = genai.Client(api_key=GEMINI_API_KEY)

async def main():
    try:
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Explain how AI works in a few words",
            config=genai.types.GenerateContentConfig(temperature=0.0)
        )
        print("Success:", response.text)
        
        # Next, try `gemini-flash-latest`
        response2 = await client.aio.models.generate_content(
            model="gemini-flash-latest",
            contents="Explain how AI works in a few words",
            config=genai.types.GenerateContentConfig(temperature=0.0)
        )
        print("Success2:", response2.text)
    except Exception as e:
        print("Error:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
