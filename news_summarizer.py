import os
import json
import feedparser
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

RSS_FEEDS = {
    "tech": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "general": "https://feeds.bbci.co.uk/news/rss.xml"
}

def fetch_headlines(topic="tech"):
    url = RSS_FEEDS.get(topic, RSS_FEEDS["tech"])
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:5]:
        articles.append({
            "title": entry.title,
            "summary": entry.get("summary", "")[:300],
            "link": entry.link
        })
    return articles

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
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    raw = response.choices[0].message.content.strip()
    
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"JSON parse failed. Raw output was:\n{raw}\n")
        result = {
            "title": title,
            "summary": "Could not parse summary.",
            "score": 0
        }
    
    return result

def main():
    print("Fetching headlines...\n")
    articles = fetch_headlines("tech")
    
    results = []
    for article in articles:
        print(f"Processing: {article['title']}")
        result = summarize_article(article["title"], article["summary"])
        result["link"] = article["link"]
        results.append(result)
        print(json.dumps(result, indent=2))
        print("-" * 40)
    
    print(f"\nDone. Processed {len(results)} articles.")

if __name__ == "__main__":
    main()