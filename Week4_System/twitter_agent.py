import os
import re
import json
import litellm
import tweepy
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from ddgs import DDGS
from datetime import datetime

load_dotenv()

# ─────────────────────────────────────────────
# LITELLM + CREWAI GROQ PATCH
# Required every time we use CrewAI with Groq
# ─────────────────────────────────────────────
litellm.drop_params = True
original_completion = litellm.completion

def strip_cache_breakpoint(*args, **kwargs):
    if 'messages' in kwargs:
        for msg in kwargs['messages']:
            if isinstance(msg, dict) and 'cache_breakpoint' in msg:
                del msg['cache_breakpoint']
    return original_completion(*args, **kwargs)

litellm.completion = strip_cache_breakpoint

# ─────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────
llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.4,
    # Slightly higher temperature for social content
    # — we want some personality and variation
    api_key=os.getenv("GROQ_API_KEY")
)

# ─────────────────────────────────────────────
# X CLIENT
# ─────────────────────────────────────────────
x_client = tweepy.Client(
    consumer_key=os.getenv("X_API_KEY"),
    consumer_secret=os.getenv("X_API_SECRET"),
    access_token=os.getenv("X_ACCESS_TOKEN"),
    access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET")
)

# ─────────────────────────────────────────────
# TOOL
# ─────────────────────────────────────────────
@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web for current information about any topic.
    Input should be a clear, specific search query of 3-6 words."""
    try:
        query = re.sub(r'[^\w\s\-]', '', query)
        query = ' '.join(query.split())
        if len(query) < 3:
            return "Query too short."
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=5):
                title = r.get('title', '')
                body = r.get('body', '')[:300]
                results.append(f"- {title}: {body}")
            return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"

# ─────────────────────────────────────────────
# AGENTS
# ─────────────────────────────────────────────
researcher = Agent(
    role="Research Analyst",
    goal="Find the most interesting current angle on the given topic for a tech-savvy X audience",
    backstory="""You are a research analyst who specializes in finding the 
    surprising, counterintuitive, or underreported angle on tech topics. 
    You search the web for current information and identify what would 
    genuinely interest people who follow AI and automation content.""",
    tools=[web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

thread_writer = Agent(
    role="X Thread Writer",
    goal="Write a compelling 5-tweet thread that educates and engages a tech audience",
    backstory="""You are a writer who specializes in X threads about technology 
    and AI. Your threads consistently perform well because you lead with something 
    surprising, build tension across tweets, and end with a clear takeaway. 
    You write like a smart person sharing something they genuinely find interesting, 
    not like a brand trying to go viral. Each tweet stands alone but flows 
    naturally into the next.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# ─────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────
def create_tasks(topic: str):
    
    research_task = Task(
        description=f"""Research this topic and find the most interesting angle for an X thread: {topic}
        
        Use web search to find:
        - The current state of this topic
        - One surprising or counterintuitive fact
        - A specific example or data point
        - Why this matters to people building or using AI tools
        
        Write a brief research summary of 150-200 words.""",
        
        expected_output="A 150-200 word research summary with a surprising angle and specific facts.",
        agent=researcher
    )
    
    thread_task = Task(
        description=f"""Write a 5-tweet X thread about: {topic}
        
        Use the research summary provided.
        
        STRICT RULES FOR EACH TWEET:
        - Maximum 260 characters each (leave room for thread numbering)
        - No hashtags anywhere in the thread
        - No emojis unless one genuinely adds meaning
        
        THREAD STRUCTURE:
        Tweet 1 (Hook): Start with the most surprising fact or a statement 
        that makes someone stop scrolling. Do NOT start with 'I'. 
        Do NOT ask a question. Make a bold, specific claim.
        
        Tweet 2 (Context): Explain why this matters. Give background.
        
        Tweet 3 (Depth): The interesting detail — the thing most people don't know.
        
        Tweet 4 (Example): A concrete real-world example or application.
        
        Tweet 5 (Takeaway): What the reader should do or think differently 
        about. End with one specific question.
        
        Return ONLY valid JSON, no extra text:
        {{
            "tweet_1": "hook tweet text",
            "tweet_2": "context tweet text", 
            "tweet_3": "depth tweet text",
            "tweet_4": "example tweet text",
            "tweet_5": "takeaway tweet text"
        }}""",
        
        expected_output='A JSON object with exactly 5 keys: tweet_1 through tweet_5. Each under 260 characters. No hashtags.',
        agent=thread_writer
    )
    
    return [research_task, thread_task]

# ─────────────────────────────────────────────
# PARSE THREAD FROM CREW OUTPUT
# ─────────────────────────────────────────────
def parse_thread(raw_output: str) -> list[str]:
    """Extract the 5 tweets from the crew's JSON output."""
    try:
        cleaned = raw_output.strip()
        
        # Strip markdown code blocks if present
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        
        data = json.loads(cleaned)
        
        tweets = [
            data.get("tweet_1", ""),
            data.get("tweet_2", ""),
            data.get("tweet_3", ""),
            data.get("tweet_4", ""),
            data.get("tweet_5", "")
        ]
        
        # Filter out any empty strings
        tweets = [t for t in tweets if t.strip()]
        
        return tweets
        
    except json.JSONDecodeError:
        print("JSON parse failed. Attempting to extract tweets from raw text...")
        # Fallback: split by newlines and take non-empty lines
        lines = [l.strip() for l in raw_output.split('\n') if l.strip()]
        return lines[:5]

# ─────────────────────────────────────────────
# VALIDATE TWEETS
# Before posting, check each tweet is within limits
# ─────────────────────────────────────────────
def validate_tweets(tweets: list[str]) -> tuple[bool, list[str]]:
    """
    Check all tweets are under 280 characters.
    Returns (all_valid, list_of_issues).
    """
    issues = []
    for i, tweet in enumerate(tweets, 1):
        if len(tweet) > 280:
            issues.append(f"Tweet {i} is {len(tweet)} characters (limit: 280)")
    
    return len(issues) == 0, issues

# ─────────────────────────────────────────────
# POST THE THREAD
# Posts tweet 1, then replies to it for tweets 2-5
# This creates the thread structure on X
# ─────────────────────────────────────────────
def post_thread(tweets: list[str], dry_run: bool = False) -> list[str]:
    """
    Post a thread to X.
    dry_run=True prints the tweets without posting — for testing.
    Returns list of tweet URLs.
    """
    if dry_run:
        print("\n[DRY RUN] Thread preview — not posting:")
        print("=" * 60)
        for i, tweet in enumerate(tweets, 1):
            print(f"\nTweet {i} ({len(tweet)} chars):")
            print(tweet)
            print("-" * 40)
        return []
    
    posted_ids = []
    posted_urls = []
    
    try:
        for i, tweet in enumerate(tweets, 1):
            print(f"\nPosting tweet {i}/5 ({len(tweet)} chars)...")
            
            if i == 1:
                # First tweet — no reply_to
                response = x_client.create_tweet(text=tweet)
            else:
                # Subsequent tweets — reply to the previous one
                # This is what creates the thread structure
                response = x_client.create_tweet(
                    text=tweet,
                    in_reply_to_tweet_id=posted_ids[-1]
                )
            
            tweet_id = response.data['id']
            posted_ids.append(tweet_id)
            tweet_url = f"https://x.com/i/web/status/{tweet_id}"
            posted_urls.append(tweet_url)
            
            print(f"Posted: {tweet_url}")
            
            # Wait between tweets to avoid rate limiting
            # and to let X register the reply relationship correctly
            if i < len(tweets):
                print("Waiting 2 seconds before next tweet...")
                time.sleep(2)
        
        print(f"\nThread posted successfully. {len(tweets)} tweets.")
        print(f"View thread: {posted_urls[0]}")
        return posted_urls
        
    except tweepy.TweepyException as e:
        print(f"\nPosting failed at tweet {len(posted_ids) + 1}: {e}")
        if posted_ids:
            print(f"Successfully posted {len(posted_ids)} tweets before failure.")
            print(f"Partial thread at: {posted_urls[0]}")
        return posted_urls

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_twitter_agent(topic: str, dry_run: bool = False):
    print(f"\nX Thread Agent")
    print(f"Topic: '{topic}'")
    print(f"Mode: {'DRY RUN (no posting)' if dry_run else 'LIVE (will post)'}")
    print("=" * 60)
    
    # Step 1: Run the crew
    tasks = create_tasks(topic)
    crew = Crew(
        agents=[researcher, thread_writer],
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    raw_output = str(result).strip()
    
    # Step 2: Parse the tweets
    print("\nParsing thread output...")
    tweets = parse_thread(raw_output)
    
    if not tweets:
        print("No tweets could be parsed from the output.")
        return
    
    print(f"\nParsed {len(tweets)} tweets.")
    
    # Step 3: Validate
    all_valid, issues = validate_tweets(tweets)
    
    if not all_valid:
        print("\nValidation issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nTweets with issues will be truncated to 280 chars before posting.")
        tweets = [t[:277] + "..." if len(t) > 280 else t for t in tweets]
    
    # Step 4: Save to file
    output = {
        "topic": topic,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tweets": tweets,
        "character_counts": [len(t) for t in tweets]
    }
    
    filename = f"thread_{topic[:30].replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nThread saved to: {filename}")
    
    # Step 5: Post or dry run
    urls = post_thread(tweets, dry_run=dry_run)
    
    if urls:
        output["posted_urls"] = urls
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nPosted URLs saved to: {filename}")
    
    return output

if __name__ == "__main__":
    import sys
    
    topic = "How AI agents are changing the way developers build software in 2026"
    
    # Run in dry_run mode first to preview without posting
    # Change to dry_run=False when you're ready to actually post
    dry_run = "--live" not in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode. Use --live flag to actually post.")
        print("Example: python twitter_agent.py --live\n")
    
    run_twitter_agent(topic, dry_run=dry_run)