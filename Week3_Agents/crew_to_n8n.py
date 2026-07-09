import os
import re
import json
import litellm
import requests
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from ddgs import DDGS
from datetime import datetime

load_dotenv()

# ─────────────────────────────────────────────
# LITELLM PATCH — same as always with CrewAI
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
# CONFIGURATION
# ─────────────────────────────────────────────
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/content-crew-output"

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.3,
    api_key=os.getenv("GROQ_API_KEY")
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
research_analyst = Agent(
    role="Research Analyst",
    goal="Find accurate, specific, and interesting information about the given topic",
    backstory="""You are a senior research analyst who finds concrete facts 
    and surprising angles. You always search the web for current information 
    and never make up statistics.""",
    tools=[web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

content_writer = Agent(
    role="Content Writer",
    goal="Write a compelling LinkedIn article and a sharp X post based on the research",
    backstory="""You are a content writer specializing in LinkedIn and X posts 
    for tech professionals. You write like a real person, not a marketing 
    department. You produce both a long LinkedIn article and a short X post.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

editor = Agent(
    role="Senior Editor",
    goal="Polish the content and return a clean JSON object with the final article and X post",
    backstory="""You are an editor who polishes writing and structures final 
    output cleanly. You remove robotic phrases and return content in the 
    exact JSON format requested — nothing else.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# ─────────────────────────────────────────────
# TASKS
# The editor task asks for JSON output —
# this makes it easy to parse and send to n8n
# ─────────────────────────────────────────────
def create_tasks(topic: str):
    
    research_task = Task(
        description=f"""Research this topic thoroughly: {topic}
        
        Use web search to find current facts, statistics, and examples.
        Write a research brief of 200-300 words covering:
        - Overview of the topic
        - Two specific facts or data points
        - One real-world example
        - One surprising insight""",
        
        expected_output="A research brief of 200-300 words with facts and examples.",
        agent=research_analyst
    )
    
    writing_task = Task(
        description=f"""Using the research brief, write two pieces of content about: {topic}
        
        PIECE 1 — LinkedIn Article (400-500 words):
        - Conversational first-person tone
        - Strong opening hook (not a question, not starting with 'I')
        - Short paragraphs, max 3 sentences each
        - End with a specific question to readers
        - No hashtags, no emojis
        
        PIECE 2 — X Post (under 240 characters):
        - One sharp, specific take on the topic
        - No hashtags
        - Sounds like a smart person talking, not a brand
        
        Write both pieces clearly labeled.""",
        
        expected_output="Two clearly labeled pieces: a LinkedIn article and an X post.",
        agent=content_writer
    )
    
    editing_task = Task(
        description="""Polish the content you received and return it as JSON.

        Fix any robotic phrases in the LinkedIn article.
        Verify the X post is under 240 characters — trim if needed.
        
        Return ONLY this JSON structure, nothing else:
        {
            "article": "the full polished LinkedIn article here",
            "x_post": "the polished X post here"
        }
        
        No explanation, no markdown code blocks, just the raw JSON.""",
        
        expected_output='A JSON object with exactly two keys: "article" and "x_post".',
        agent=editor
    )
    
    return [research_task, writing_task, editing_task]

# ─────────────────────────────────────────────
# SEND TO N8N
# ─────────────────────────────────────────────
def send_to_n8n(payload: dict) -> bool:
    """POST the crew output to the n8n webhook.
    Returns True if successful, False if not."""
    try:
        print(f"\nSending to n8n webhook...")
        
        response = requests.post(
            N8N_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=15
        )
        
        if response.status_code == 200:
            print(f"n8n received the payload successfully.")
            return True
        else:
            print(f"n8n returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("Could not connect to n8n. Make sure n8n is running on localhost:5678")
        return False
    except Exception as e:
        print(f"Failed to send to n8n: {e}")
        return False

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_and_deliver(topic: str):
    print(f"\nStarting crew for: '{topic}'")
    print("=" * 60)
    
    tasks = create_tasks(topic)
    
    crew = Crew(
        agents=[research_analyst, content_writer, editor],
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    raw_output = str(result).strip()
    
    print("\n" + "=" * 60)
    print("CREW OUTPUT:")
    print(raw_output)
    
    # Parse the JSON the editor returned
    try:
        # Sometimes the model wraps JSON in markdown code blocks
        # Strip those out if present
        cleaned = raw_output
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        
        content = json.loads(cleaned)
        article = content.get("article", "")
        x_post = content.get("x_post", "")
        
    except json.JSONDecodeError:
        print("\nJSON parse failed — using raw output as article.")
        article = raw_output
        x_post = ""
    
    # Build the payload for n8n
    payload = {
        "topic": topic,
        "article": article,
        "x_post": x_post,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    # Save locally regardless of n8n success
    filename = f"crew_output_{topic[:30].replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nOutput saved locally to: {filename}")
    
    # Send to n8n
    success = send_to_n8n(payload)
    
    if success:
        print("\nFull pipeline complete:")
        print("  ✅ Crew generated content")
        print("  ✅ Sent to n8n")
        print("  ✅ n8n will update Notion, Sheets, and Slack")
    else:
        print("\nCrew succeeded but n8n delivery failed.")
        print("Content saved locally — check n8n is running and try again.")
    
    return payload

if __name__ == "__main__":
    run_and_deliver("How to land your first AI automation client")