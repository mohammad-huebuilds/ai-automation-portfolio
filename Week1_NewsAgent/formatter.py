import json
from datetime import datetime

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

def save_markdown(content, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Saved: {filename}")

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {filename}")