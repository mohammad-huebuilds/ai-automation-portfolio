import os
import json
import time
import smtplib
import schedule
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"title": title, "summary": "Could not parse summary.", "score": 0}

    return result

def build_markdown(topic, articles_data):
    today = datetime.now().strftime("%B %d, %Y")
    lines = [f"# Daily News Digest — {topic.upper()}", f"*Generated on {today}*", "", "---", ""]

    for item in articles_data:
        score = item.get("score", 0)
        lines.append(f"## {item['title']}")
        lines.append(f"**Summary:** {item['summary']}")
        lines.append(f"**Relevance Score:** {score}/10")
        lines.append(f"**Read more:** [{item['link']}]({item['link']})")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)

def send_email(subject, body_markdown):
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg["Subject"] = subject

    msg.attach(MIMEText(body_markdown, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def run_digest():
    topic = "tech"
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running digest for topic: {topic}")

    articles = fetch_headlines(topic)
    results = []
    for article in articles:
        result = summarize_article(article["title"], article["summary"])
        result["link"] = article["link"]
        results.append(result)

    markdown = build_markdown(topic, results)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"digest_{date_str}_{topic}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Digest saved to: {filename}")

    subject = f"Your {topic.upper()} Digest — {datetime.now().strftime('%B %d, %Y')}"
    send_email(subject, markdown)

if __name__ == "__main__":
    print("Scheduler started. Digest will run daily at 08:00.")
    print("Running once now for testing purposes...\n")
    
    run_digest()

    schedule.every().day.at("08:00").do(run_digest)

    while True:
        schedule.run_pending()
        time.sleep(60)