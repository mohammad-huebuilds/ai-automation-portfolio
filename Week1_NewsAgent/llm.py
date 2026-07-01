import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

def call_llm(prompt, model="llama-3.1-8b-instant"):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def safe_json_parse(raw_text, fallback=None):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"JSON parse failed. Raw output:\n{raw_text}\n")
        return fallback if fallback is not None else {}

def summarize_article(title, snippet):
    prompt = f"""
You are a news analyst. Given this article title and snippet, return ONLY valid JSON with no extra text.

Title: {title}
Snippet: {snippet}

Return exactly this structure:
{{
    "title": "the original title",
    "summary": "one clear sentence explaining what this article is about",
    "score": a number from 1 to 10 based on how important or interesting this news is
}}

Return ONLY the JSON object. No intro text, no explanation, nothing else.
"""
    raw = call_llm(prompt)
    return safe_json_parse(raw, fallback={"title": title, "summary": "Could not parse.", "score": 0})

def pick_best_story(articles):
    articles_text = ""
    for i, article in enumerate(articles):
        articles_text += f"{i+1}. Title: {article['title']}\n   Snippet: {article.get('summary', '')}\n\n"

    prompt = f"""
You are a social media strategist. Here are these news articles:

{articles_text}

Pick the ONE article with the highest viral potential on social media.
Return ONLY valid JSON, no extra text:

{{
    "chosen_index": the number of the article you picked,
    "title": "the article title",
    "reason": "one sentence explaining exactly why this story has the most viral potential"
}}
"""
    raw = call_llm(prompt)
    result = safe_json_parse(raw, fallback={"chosen_index": 1, "title": articles[0]["title"], "reason": "Fallback due to parse error."})
    
    try:
        index = result["chosen_index"] - 1
        result["link"] = articles[index]["link"]
    except (KeyError, IndexError):
        result["link"] = articles[0]["link"]
    
    return result

def generate_social_posts(story):
    prompt = f"""
You are a social media copywriter. Based on this news story, write social media posts.

Story: {story['title']}
Why it's interesting: {story['reason']}

Return ONLY valid JSON, no extra text:

{{
    "linkedin": "a 3-4 sentence professional post that adds insight, ending with a question",
    "twitter": "a punchy tweet STRICTLY under 250 characters, no hashtags",
    "instagram_caption": "a caption with a hook sentence and 2-3 sentences of context",
    "instagram_hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]
}}
"""
    raw = call_llm(prompt)
    return safe_json_parse(raw, fallback={
        "linkedin": "Could not generate.",
        "twitter": "Could not generate.",
        "instagram_caption": "Could not generate.",
        "instagram_hashtags": ["#error"]
    })