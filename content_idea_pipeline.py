import os
import json
import feedparser
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

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

def pick_best_story(articles):
    articles_text = ""
    for i, article in enumerate(articles):
        articles_text += f"{i+1}. Title: {article['title']}\n   Snippet: {article['summary']}\n\n"

    prompt = f"""
You are a social media strategist. Here are 5 news articles:

{articles_text}

Pick the ONE article with the highest viral potential on social media.
Return ONLY valid JSON, no extra text:

{{
    "chosen_index": the number (1-5) of the article you picked,
    "title": "the article title",
    "link": "the article link",
    "reason": "one sentence explaining exactly why this story has the most viral potential"
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
        index = result["chosen_index"] - 1
        result["link"] = articles[index]["link"]
        return result
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Parse error in pick_best_story: {e}")
        print(f"Raw output: {raw}")
        return {
            "chosen_index": 1,
            "title": articles[0]["title"],
            "link": articles[0]["link"],
            "reason": "Fallback to first article due to parse error."
        }

def generate_social_posts(story):
    prompt = f"""
You are a social media copywriter. Based on this news story, write 3 social media posts.

Story: {story['title']}
Why it's interesting: {story['reason']}

Return ONLY valid JSON, no extra text:

{{
    "linkedin": "a 3-4 sentence professional post for LinkedIn that adds insight, not just restates the headline. End with a question to drive comments.",
    "twitter": "a punchy tweet under 280 characters. No hashtags. Just a sharp take on the story.",
    "instagram_caption": "a caption that starts with a hook sentence and explains the story in 2-3 sentences.",
    "instagram_hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"] (Make sure to include the '#' symbol)
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
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Parse error in generate_social_posts: {e}")
        print(f"Raw output: {raw}")
        return {
            "linkedin": "Could not generate LinkedIn post.",
            "twitter": "Could not generate tweet.",
            "instagram_caption": "Could not generate Instagram caption.",
            "instagram_hashtags": ["#error"]
        }

def main():
    topic = "tech"
    print(f"Fetching {topic} headlines...\n")
    articles = fetch_headlines(topic)

    print("Step 1: Picking the best story...\n")
    best_story = pick_best_story(articles)
    print(f"Chosen: {best_story['title']}")
    print(f"Reason: {best_story['reason']}\n")

    print("Step 2: Generating social media posts...\n")
    posts = generate_social_posts(best_story)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "chosen_story": best_story,
        "social_posts": posts
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"content_ideas_{date_str}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Rebuilding the clean display layout for Instagram printout
    ig_hashtags_string = " ".join(posts.get('instagram_hashtags', []))

    print("=" * 50)
    print(f"LINKEDIN:\n{posts.get('linkedin')}\n")
    print(f"TWITTER:\n{posts.get('twitter')}\n")
    print(f"INSTAGRAM:\n{posts.get('instagram_caption')}\n{ig_hashtags_string}\n")
    print("=" * 50)
    print(f"\nFull output saved to: {filename}")

if __name__ == "__main__":
    main()