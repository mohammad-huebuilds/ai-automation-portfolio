import os
import re
import json
import time
import random
import litellm
import requests
import urllib.parse
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
INSTAGRAM_PROFILE_ID = os.getenv("BUFFER_INSTAGRAM_PROFILE_ID")

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.4,
    api_key=os.getenv("GROQ_API_KEY")
)

# ─────────────────────────────────────────────
# OPTIMIZED IMAGE GENERATION
# ─────────────────────────────────────────────
def generate_image(prompt: str, topic: str, max_retries: int = 3) -> tuple[str | None, str | None]:
    """
    Generate an image with Pollinations.ai, save it locally, 
    and return both the local filename and the public image URL.
    """
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 1000000)
    
    # Enhanced parameters for unique, detailed rendering
    public_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1080&height=1080&nologo=true&model=flux"
        f"&enhance=true&seed={seed}"
    )
    
    print(f"\nGenerating image using custom agent prompt...")
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries} (timeout: 60s)...")
            response = requests.get(public_url, timeout=60)
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type:
                    print(f"Non-image response received. Retrying...")
                    time.sleep(5)
                    continue
                
                # Save locally for visual reference
                safe_topic = topic[:30].replace(' ', '_').replace('/', '_')
                filename = f"ig_image_{safe_topic}_{int(time.time())}.png"
                
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                size_kb = len(response.content) / 1024
                print(f"Image saved locally: {filename} ({size_kb:.0f}KB)")
                return filename, public_url
            else:
                print(f"HTTP {response.status_code}. Waiting 5s...")
                time.sleep(5)
                
        except requests.exceptions.Timeout:
            print(f"Timeout. Waiting 3s before retry...")
            time.sleep(3)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)
    
    return None, None

# ─────────────────────────────────────────────
# FIXED BUFFER GRAPHQL INSTAGRAM METHOD
# ─────────────────────────────────────────────
def schedule_instagram_post(
    caption: str,
    image_url: str,
    dry_run: bool = False
) -> dict:
    """
    Schedule an Instagram post via modern Buffer GraphQL API.
    Bypasses file uploads by passing a hosted public media URL directly.
    """
    if dry_run:
        print("\n[DRY RUN] Would schedule this Instagram post:")
        print("=" * 60)
        print(f"Public Image URL: {image_url}")
        print(f"\nCaption:\n{caption}")
        print("=" * 60)
        return {
            "success": True,
            "dry_run": True,
            "image_url": image_url
        }
    
    print("\nScheduling on Buffer using direct media URL routing...")
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    mutation = """
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
    
    # Modern Buffer Schema explicitly defining required platform metadata
    variables = {
        "input": {
            "channelId": INSTAGRAM_PROFILE_ID,
            "text": caption,
            "assets": [
                {
                    "image": {
                        "url": image_url
                    }
                }
            ],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            # FIX: Meta API requires the type defined explicitly within lowercase constraints
            "metadata": {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True
                }
            }
        }
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": mutation, "variables": variables}
        )
        result = response.json()
        data = result.get("data", {}).get("createPost", {})
        
        if "post" in data:
            post_id = data["post"]["id"]
            scheduled_at = data["post"].get("dueAt", "unknown")
            print(f"Instagram post scheduled! ID: {post_id}")
            print(f"Scheduled for: {scheduled_at}")
            return {
                "success": True,
                "buffer_id": post_id,
                "scheduled_at": scheduled_at
            }
        else:
            error = data.get("message", str(result))
            print(f"Scheduling failed: {error}")
            return schedule_text_only_fallback(caption)
            
    except Exception as e:
        print(f"Buffer API error: {e}")
        return {"success": False, "error": str(e)}

def schedule_text_only_fallback(caption: str) -> dict:
    """Fallback if image processing fails — schedule caption only."""
    print("Using text-only fallback...")
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id dueAt }
        }
        ... on MutationError { message }
      }
    }
    """
    variables = {
        "input": {
            "channelId": INSTAGRAM_PROFILE_ID,
            "text": caption,
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    }
    try:
        response = requests.post(url, headers=headers, json={"query": mutation, "variables": variables})
        result = response.json()
        data = result.get("data", {}).get("createPost", {})
        if "post" in data:
            return {"success": True, "fallback": True, "buffer_id": data["post"]["id"]}
        return {"success": False, "error": str(data)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─────────────────────────────────────────────
# TOOLS & AGENTS
# ─────────────────────────────────────────────
@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web for current information."""
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

researcher = Agent(
    role="Research Analyst",
    goal="Find the most visually interesting and shareable angle on this topic for Instagram",
    backstory="""You research topics for social media content creators. 
    Look for angles that translate well to visual setups — striking metaphors, 
    stark contrasts, or concepts that instantly halt scrolling workflows.""",
    tools=[web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

visual_director = Agent(
    role="Visual Director",
    goal="Write a precise image generation prompt that creates a professional, eye-catching photographic scene or high-end 3D render about tech and AI",
    backstory="""You design content for high-tier tech brands. You strictly avoid 
    abstract corporate fluff or empty text graphics. You visualize concrete, tangible hardware, 
    sleek physical environments, or high-definition physical-spatial technology elements using 
    vivid, crisp neon accent highlights against cinematic dark studio backgrounds.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

caption_writer = Agent(
    role="Instagram Caption Writer",
    goal="Write an Instagram caption that works alongside a visual post — hooks immediately, delivers value, ends with engagement",
    backstory="""You write short, punchy tech captions with a killer 
    hook on line 1, 2-3 value lines, and a clean array of maximum 5 targeted hashtags.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# ─────────────────────────────────────────────
# TASKS & PARSING
# ─────────────────────────────────────────────
def create_tasks(topic: str):
    research_task = Task(
        description=f"Research this topic for an Instagram post: {topic}\nFind a visual metaphor and a unique hook. Max 100 words.",
        expected_output="A brief containing one surprising fact, a visual concept, and its tech-audience relevance.",
        agent=researcher
    )
    
    # FIX: Rewritten to completely ban abstract phrases and force concrete visual descriptors
    visual_task = Task(
        description=f"""Analyze this topic: '{topic}'. Write a precise image generation prompt.
        
        CRUCIAL RULES:
        - Do NOT use abstract phrases like 'concept architecture', 'metaphor representing', or 'the idea of'.
        - Describe a concrete, physical photographic scene or a precise 3D isometric layout.
        - Describe actual objects: e.g., an automated robotic arm, a glowing network interface block, a hyper-detailed server deck, or sleek neon lines.
        - Explicitly state: crisp dark mode setting, cinematic dramatic lighting, and specific neon highlights (electric blue, cyan, or deep violet).
        - End the prompt with: architectural studio photography style, highly detailed ray-traced render, 4K.
        
        Keep it to 40-60 words total. Return ONLY the raw image prompt text, no headers, no labels.""",
        expected_output="A 40-60 word concrete image generation prompt text only.",
        agent=visual_director
    )
    
    caption_task = Task(
        description=f"Write an Instagram caption for: {topic}.\nLine 1 hook, 2-4 lines value, line 5 CTA. Max 5 hashtags. Total 80-120 words. Return ONLY valid JSON: {{\n\"caption\": \"text\",\n\"hashtags\": [\"#tag\"]\n}}",
        expected_output="JSON block with caption and hashtags keys.",
        agent=caption_writer
    )
    return [research_task, visual_task, caption_task]

def parse_caption_output(raw: str) -> dict:
    try:
        cleaned = raw.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        data = json.loads(cleaned)
        return {"caption": data.get("caption", ""), "hashtags": data.get("hashtags", [])}
    except json.JSONDecodeError:
        print("JSON parse failed — defaulting to raw string text.")
        return {"caption": raw.strip(), "hashtags": []}

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_instagram_agent(topic: str, dry_run: bool = False):
    print(f"\nInstagram Agent Launcher")
    print(f"Topic: '{topic}'")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE — Buffer Sync'}")
    print("=" * 60)
    
    tasks = create_tasks(topic)
    crew = Crew(
        agents=[researcher, visual_director, caption_writer],
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    raw_output = str(result).strip()
    
    content = parse_caption_output(raw_output)
    caption = content["caption"]
    
    print("\n" + "=" * 60)
    print("GENERATED CAPTION:")
    print(caption)
    
    # FIX: Programmatically extract the custom prompt generated by your Visual Director task instead of using a hardcoded string template
    try:
        image_prompt = tasks[1].output.raw.strip()
        # Clean up accidental wrapping quotes if the LLM added them
        image_prompt = image_prompt.replace('"', '').replace("'", "")
        print(f"\nCaptured Visual Prompt from Agent:\n-> {image_prompt}")
    except Exception as e:
        print(f"Could not read custom task output context ({e}). Using a concrete baseline fallback.")
        image_prompt = (
            f"A clean minimalist isometric 3D render illustrating {topic}, "
            f"industrial server rack node, deep dark studio background, vivid electric blue and cyber cyan neon lighting, "
            f"high contrast tech product photography style, 4K resolution"
        )
    
    # Generate and save image, returning local reference and direct public URL
    image_file, public_img_url = generate_image(image_prompt, topic)
    
    if not public_img_url:
        print("\nImage processing failed. Transitioning to standard textual fallback.")
    
    # Schedule post via fixed GraphQL payload variable mapping
    if public_img_url:
        buffer_result = schedule_instagram_post(caption, public_img_url, dry_run=dry_run)
    else:
        if dry_run:
            buffer_result = {"success": True, "dry_run": True, "note": "Text post fallback mock"}
        else:
            buffer_result = schedule_text_only_fallback(caption)
            
    output = {
        "topic": topic,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "caption": caption,
        "hashtags": content["hashtags"],
        "image_file": image_file,
        "public_url": public_img_url,
        "buffer_result": buffer_result
    }
    
    filename = f"instagram_{topic[:30].replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved execution metrics to: {filename}")
    return output

if __name__ == "__main__":
    import sys
    topic = "How AI automation is changing the way small businesses operate"
    dry_run = "--live" not in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode. Use '--live' to process production posts.\n")
        
    run_instagram_agent(topic, dry_run=dry_run)