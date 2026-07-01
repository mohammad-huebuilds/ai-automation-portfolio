import os
from openai import OpenAI
from dotenv import load_dotenv
import sys

load_dotenv()

# We add base_url to redirect the OpenAI library to Groq's free servers
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

topic = sys.argv[1] if len(sys.argv) > 1 else "artificial intelligence"

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",  # This is a powerful, free, and incredibly fast model
    messages=[
        {
            "role": "system",
            "content": "You are a clear, concise writer. When given a topic, write exactly 3 paragraphs about it. Each paragraph should be 3-4 sentences. Be informative and engaging."
        },
        {
            "role": "user",
            "content": f"Write 3 paragraphs about: {topic}"
        }
    ]
)

print(response.choices[0].message.content)