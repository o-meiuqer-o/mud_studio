import asyncio
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key='PLEASE_SET_YOUR_API_KEY_HERE')

async def test():
    try:
        response = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': 'hi'}]
        )
        print("Success:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(test())
