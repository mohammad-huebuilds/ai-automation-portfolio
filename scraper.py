import requests
from bs4 import BeautifulSoup
import time

def scrape_hacker_news(limit=10):
    url = "https://news.ycombinator.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch Hacker News: {e}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    
    titles = soup.select(".titleline > a")
    
    articles = []
    for title_tag in titles[:limit]:
        title = title_tag.get_text()
        link = title_tag.get("href")
        
        if link and not link.startswith("http"):
            link = f"https://news.ycombinator.com/{link}"
        
        articles.append({
            "title": title,
            "summary": "",
            "link": link
        })
    
    return articles

def scrape_reddit(subreddit="MachineLearning", limit=10):
    url = f"https://www.reddit.com/r/{subreddit}/.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch Reddit: {e}")
        return []
    except ValueError as e:
        print(f"Failed to parse Reddit JSON: {e}")
        return []

    articles = []
    posts = data.get("data", {}).get("children", [])[:limit]
    
    for post in posts:
        post_data = post.get("data", {})
        articles.append({
            "title": post_data.get("title", ""),
            "summary": post_data.get("selftext", "")[:300],
            "link": f"https://reddit.com{post_data.get('permalink', '')}"
        })
        time.sleep(0.5)
    
    return articles

if __name__ == "__main__":
    print("Testing Hacker News scraper...\n")
    hn_articles = scrape_hacker_news(limit=10)
    for i, article in enumerate(hn_articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   {article['link']}\n")
    
    print(f"\nScraped {len(hn_articles)} articles from Hacker News.")