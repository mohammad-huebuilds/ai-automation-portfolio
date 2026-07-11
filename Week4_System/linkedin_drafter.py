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
# LITELLM + CREWAI GROQ PATCH
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
BUFFER_TOKEN = os.getenv("BUFFER_TOKEN")
LINKEDIN_PROFILE_ID = os.getenv("BUFFER_LINKEDIN_PROFILE_ID")

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.4,
    api_key=os.getenv("GROQ_API_KEY")
)

# ─────────────────────────────────────────────
# BUFFER API FUNCTIONS (UPDATED FOR GRAPHQL)
# ─────────────────────────────────────────────
def schedule_linkedin_post(text: str, dry_run: bool = False) -> dict:
    """
    Send a post to Buffer using their modern GraphQL API.
    Bypasses the broken v1 REST proxy.
    """
    if dry_run:
        print("\n[DRY RUN] Would schedule this LinkedIn post:")
        print("=" * 60)
        print(text)
        print("=" * 60)
        print(f"Character count: {len(text)}")
        return {
            "success": True,
            "dry_run": True,
            "message": "Dry run — no actual scheduling done"
        }
    
    url = "https://api.buffer.com"
    
    # Using Buffer's modern GraphQL mutation structure
    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            dueAt
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """
    
    # We pass the variables exactly as the new API requires
    variables = {
        "input": {
            "channelId": LINKEDIN_PROFILE_ID,
            "text": text,
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BUFFER_TOKEN}"
    }
    
    try:
        response = requests.post(url, headers=headers, json={"query": query, "variables": variables})
        result = response.json()
        
        # Parse the GraphQL response
        data = result.get("data", {}).get("createPost", {})
        
        if "post" in data:
            post_id = data["post"]["id"]
            scheduled_at = data["post"].get("dueAt", "unknown")
            
            print(f"Scheduled successfully!")
            print(f"Buffer post ID: {post_id}")
            print(f"Scheduled for: {scheduled_at}")
            
            return {
                "success": True,
                "buffer_id": post_id,
                "scheduled_at": scheduled_at,
                "profile": "LinkedIn"
            }
        else:
            error_msg = data.get("message", str(result))
            print(f"Buffer scheduling failed: {error_msg}")
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        print(f"Buffer API error: {e}")
        return {"success": False, "error": str(e)}
    
def get_buffer_queue() -> list:
    """
    Check what's currently scheduled in your Buffer queue using GraphQL.
    """
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    query = """
    query GetPendingPosts($input: ChannelInput!) {
      channel(input: $input) {
        id
        queuedPosts {
          totalCount
          nodes {
            id
            text
          }
        }
      }
    }
    """
    
    variables = {
        "input": {
            "id": LINKEDIN_PROFILE_ID
        }
    }
    
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        
        if "errors" in data:
            return []
            
        posts = data.get("data", {}).get("channel", {}).get("queuedPosts", {}).get("nodes", [])
        return posts
    except Exception as e:
        print(f"Could not fetch queue: {e}")
        return []

# ─────────────────────────────────────────────
# TOOL
# ─────────────────────────────────────────────
@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web for current information.
    Input should be a clear search query of 3-6 words."""
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
    goal="Find specific, current facts about the topic that will make for a credible and insightful LinkedIn post",
    backstory="""You research topics for professional content creators. 
    You find the specific data points, real examples, and current 
    developments that make professional posts credible and worth reading. 
    You always verify information is current and specific, not vague.""",
    tools=[web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

linkedin_writer = Agent(
    role="LinkedIn Content Specialist",
    goal="Write a LinkedIn post that gets high engagement from a professional tech audience",
    backstory="""You specialize in LinkedIn content for tech professionals 
    and consultants. You understand that LinkedIn rewards posts that 
    share genuine professional insight, not promotional content. 
    Your posts perform well because they make readers feel smarter 
    after reading them. You know that LinkedIn's algorithm favors 
    posts that generate comments, so you always end with a question 
    that sparks real professional debate — not 'what do you think?' 
    but something specific that people have actual opinions about.""",
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
        description=f"""Research this topic for a LinkedIn post: {topic}
        
        Find:
        - One specific statistic or data point with context
        - One real company or person example
        - The professional angle — why does this matter to 
          LinkedIn's audience of builders, managers, and consultants
        - One common mistake or misconception professionals make 
          about this topic
        
        Keep the brief focused: 150 words maximum.""",
        
        expected_output="A focused 150-word research brief with one statistic, one example, and the professional angle.",
        agent=researcher
    )
    
    writing_task = Task(
        description=f"""Write a LinkedIn post about: {topic}
        
        Use the research brief provided.
        
        LinkedIn post guidelines:
        
        LENGTH: 150-250 words. LinkedIn rewards medium-length posts 
        that are easy to read on mobile.
        
        STRUCTURE:
        - Line 1: Hook — one specific, surprising statement. 
          Gets cut off in feed so it must make people click 'see more'
        - Lines 2-4: The insight. Use the research. Be specific.
        - Lines 5-7: The practical implication for professionals
        - Final line: A specific question that professionals 
          in this space would have a real opinion about
        
        FORMATTING:
        - Short paragraphs, one blank line between each
        - No bullet points (LinkedIn compresses them poorly on mobile)
        - No hashtags (they look spammy in 2026)
        - No emojis unless one genuinely adds meaning
        
        TONE:
        - First person, direct
        - Professional but not stiff
        - Sounds like a practitioner sharing what they've learned,
          not a thought leader performing expertise
        
        Return ONLY the post text, nothing else. 
        No labels, no 'Here is the post:', just the post itself.""",
        
        expected_output="A LinkedIn post of 150-250 words, properly structured, ending with a specific question. Post text only.",
        agent=linkedin_writer
    )
    
    return [research_task, writing_task]

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_linkedin_drafter(topic: str, dry_run: bool = False):
    print(f"\nLinkedIn Draft Agent")
    print(f"Topic: '{topic}'")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE — will schedule on Buffer'}")
    print("=" * 60)
    
    # Step 1: Run the crew
    tasks = create_tasks(topic)
    crew = Crew(
        agents=[researcher, linkedin_writer],
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    post_text = str(result).strip()
    
    print("\n" + "=" * 60)
    print("GENERATED POST:")
    print("=" * 60)
    print(post_text)
    print(f"\nCharacter count: {len(post_text)}")
    print(f"Word count: {len(post_text.split())}")
    
    # Step 2: Schedule via Buffer
    print("\nSending to Buffer...")
    buffer_result = schedule_linkedin_post(post_text, dry_run=dry_run)
    
    # Step 3: Check the queue to confirm
    if not dry_run and buffer_result.get("success"):
        print("\nChecking Buffer queue...")
        queue = get_buffer_queue()
        print(f"Posts currently in LinkedIn queue: {len(queue)}")
    
    # Step 4: Save locally
    output = {
        "topic": topic,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "post_text": post_text,
        "word_count": len(post_text.split()),
        "char_count": len(post_text),
        "buffer_result": buffer_result
    }
    
    filename = f"linkedin_{topic[:30].replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved to: {filename}")
    return output

if __name__ == "__main__":
    import sys
    
    topic = "Why most AI automation projects fail before they reach production"
    dry_run = "--live" not in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode.")
        print("Use --live flag to actually schedule on Buffer.\n")
    
    run_linkedin_drafter(topic, dry_run=dry_run)