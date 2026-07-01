import argparse
from datetime import datetime
from scraper import scrape_hacker_news
from llm import summarize_article, pick_best_story, generate_social_posts
from formatter import build_markdown, save_markdown, save_json

def run_digest(topic="tech"):
    print(f"Fetching headlines...\n")
    articles = scrape_hacker_news(limit=5)

    results = []
    for article in articles:
        print(f"Processing: {article['title']}")
        result = summarize_article(article["title"], article.get("summary", ""))
        result["link"] = article["link"]
        results.append(result)

    markdown = build_markdown(topic, results)
    date_str = datetime.now().strftime("%Y-%m-%d")
    save_markdown(markdown, f"digest_{date_str}.md")

def run_content_pipeline(topic="tech"):
    print(f"Fetching headlines...\n")
    articles = scrape_hacker_news(limit=5)

    print("Picking the best story...\n")
    best_story = pick_best_story(articles)
    print(f"Chosen: {best_story['title']}\nReason: {best_story['reason']}\n")

    print("Generating social posts...\n")
    posts = generate_social_posts(best_story)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "chosen_story": best_story,
        "social_posts": posts
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    save_json(output, f"content_ideas_{date_str}.json")

    print(f"\nLINKEDIN:\n{posts.get('linkedin')}\n")
    print(f"TWITTER:\n{posts.get('twitter')}\n")
    print(f"INSTAGRAM:\n{posts.get('instagram_caption')}")
    print(" ".join(posts.get("instagram_hashtags", [])))

def main():
    parser = argparse.ArgumentParser(description="AI News Agent - digest and content pipeline")
    parser.add_argument("--mode", type=str, default="digest", choices=["digest", "content"],
                        help="digest = markdown news summary | content = social media post generator")
    parser.add_argument("--topic", type=str, default="tech")
    args = parser.parse_args()

    if args.mode == "digest":
        run_digest(args.topic)
    else:
        run_content_pipeline(args.topic)

if __name__ == "__main__":
    main()