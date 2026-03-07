from google import genai

client = genai.Client(api_key="AIzaSyDEekI9WnmhfEeEudg5oH7r4IHA5d_jWbs")
try:
    for m in client.models.list():
        print(m.name)
except Exception as e:
    print(e)
