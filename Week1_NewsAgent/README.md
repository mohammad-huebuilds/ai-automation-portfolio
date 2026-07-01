# AI News Agent

A Python automation system that scrapes live tech news, processes it through an LLM, and outputs either a formatted daily digest or ready-to-post social media content.

## What It Does

- Scrapes live posts from Hacker News (no RSS dependency)
- Mode 1 — Digest: summarizes each story and scores it for relevance, outputs a clean Markdown report
- Mode 2 — Content: picks the single most "viral" story, then generates a LinkedIn post, a tweet, and an Instagram caption + hashtags for it
- All LLM output is structured JSON, parsed and validated before use

## Tech Stack

Python · Groq API (Llama 3.1) · BeautifulSoup4 · Requests

## How to Run

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env  # add your GROQ_API_KEY
python main.py --mode digest
python main.py --mode content
\`\`\`

## Project Structure

\`\`\`
main.py          - CLI entry point
scraper.py       - Hacker News scraping logic
llm.py           - All LLM calls and JSON parsing
formatter.py     - Markdown and JSON output formatting
\`\`\`

## Sample Output

See \`sample_output/\` for real generated examples.

## What This Demonstrates

API integration, prompt engineering for reliable structured output, web scraping, and chaining multiple LLM calls into a single pipeline (fetch → analyze → generate). This is the foundational pattern used in the more complex automation systems in this repo's later folders.