import os
import re
import json
import litellm
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from ddgs import DDGS

load_dotenv()

# ─────────────────────────────────────────────
# LITELLM + CREWAI GROQ COMPATIBILITY FIX
# Same patch as Day 17 — required for CrewAI + Groq
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
# LLM INITIALIZATION
# ─────────────────────────────────────────────
llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.3,
    api_key=os.getenv("GROQ_API_KEY")
)

# ─────────────────────────────────────────────
# MEMORY SYSTEM
# A simple JSON file that stores every topic
# the crew has already written about
# Before running, we check this file
# After running, we add the new topic to it
# ─────────────────────────────────────────────
MEMORY_FILE = "crew_memory.json"

def load_memory() -> dict:
    """Load the memory file. If it doesn't exist, create an empty one."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    # First run — no memory yet
    return {"completed_topics": [], "total_articles_written": 0}

def save_memory(memory: dict):
    """Save updated memory back to the JSON file."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def topic_already_written(topic: str, memory: dict) -> bool:
    """Check if this exact topic has been written about before.
    Case-insensitive comparison to catch near-duplicates."""
    topic_lower = topic.lower().strip()
    completed = [t.lower().strip() for t in memory["completed_topics"]]
    return topic_lower in completed

def mark_topic_complete(topic: str, memory: dict) -> dict:
    """Add a topic to memory and increment the counter."""
    memory["completed_topics"].append(topic)
    memory["total_articles_written"] += 1
    memory["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return memory

# ─────────────────────────────────────────────
# GOOGLE SHEETS INTEGRATION
# Reads the next queued topic and updates
# the row status after processing
# ─────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheets_client():
    """Create an authenticated Google Sheets client."""
    creds = Credentials.from_service_account_file(
        "google_credentials.json",
        scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_next_queued_topic(sheet_name="Content Queue") -> dict | None:
    """
    Find the first row in the Content Queue sheet where
    Status equals 'Queued'. Returns the row data and
    its row number, or None if nothing is queued.
    """
    try:
        client = get_sheets_client()
        sheet = client.open(sheet_name).sheet1
        
        # Get all rows as a list of dictionaries
        # gspread uses the first row as column headers automatically
        all_rows = sheet.get_all_records()
        
        for index, row in enumerate(all_rows):
            if row.get("Status", "").strip() == "Queued":
                # index is 0-based but sheet rows are 1-based
                # Plus 1 for the header row = index + 2
                return {
                    "topic": row.get("Topic", ""),
                    "platform": row.get("Platform", "both"),
                    "row_number": index + 2
                }
        
        return None  # Nothing queued
        
    except Exception as e:
        print(f"Google Sheets error: {e}")
        return None

def update_row_status(row_number: int, status: str, article: str = "", sheet_name="Content Queue"):
    """
    Update the Status column for a specific row.
    Optionally write the generated article into the LinkedIn Draft column.
    """
    try:
        client = get_sheets_client()
        sheet = client.open(sheet_name).sheet1
        
        # Get the header row to find column positions
        headers = sheet.row_values(1)
        
        # Find the Status column index (1-based for gspread)
        status_col = headers.index("Status") + 1
        sheet.update_cell(row_number, status_col, status)
        
        # If we have an article, write it to the LinkedIn Draft column
        if article and "LinkedIn Draft" in headers:
            linkedin_col = headers.index("LinkedIn Draft") + 1
            sheet.update_cell(row_number, linkedin_col, article)
        
        # Update the Created At timestamp
        if "Created At" in headers:
            created_col = headers.index("Created At") + 1
            sheet.update_cell(row_number, created_col, datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        print(f"Sheet row {row_number} updated to: {status}")
        
    except Exception as e:
        print(f"Failed to update sheet: {e}")

# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────
@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web for current information about any topic.
    Use this to find recent news, facts, statistics, and examples.
    Input should be a clear, specific search query of 3-6 words."""
    try:
        query = re.sub(r'[^\w\s\-]', '', query)
        query = ' '.join(query.split())
        
        if len(query) < 3:
            return "Query too short. Please be more specific."
        
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=5):
                title = r.get('title', '')
                body = r.get('body', '')[:300]
                results.append(f"- {title}: {body}")
            
            if results:
                return "\n".join(results)
            else:
                return "No results found. Try a different search query."
                
    except Exception as e:
        return f"Search error: {str(e)}"

# ─────────────────────────────────────────────
# AGENTS
# Same three agents as Day 17 — no changes needed
# ─────────────────────────────────────────────
research_analyst = Agent(
    role="Research Analyst",
    goal="Find accurate, specific, and interesting information about the given topic that will make for compelling content",
    backstory="""You are a senior research analyst who spent 10 years at a 
    technology research firm. You have a talent for finding the specific 
    facts and angles that make a topic genuinely interesting rather than 
    generic. You always look for the surprising statistic, the counterintuitive 
    finding, or the real-world example that makes abstract topics concrete.
    You never make up facts — if you can't find something specific, you say so.""",
    tools=[web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

content_writer = Agent(
    role="Content Writer",
    goal="Write a compelling LinkedIn article that sounds like a knowledgeable human wrote it, not a marketing department",
    backstory="""You are a freelance writer who specializes in technology and 
    business content for LinkedIn. Your articles consistently get strong 
    engagement because you write like a real person sharing genuine insights, 
    not like a brand publishing marketing content. You never use phrases like 
    'In today's fast-paced world' or 'It's more important than ever'. 
    You make complex topics accessible without dumbing them down.""",
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

editor = Agent(
    role="Senior Editor",
    goal="Polish the article to be genuinely excellent — tightening language, strengthening the opening, and ensuring it sounds authentically human throughout",
    backstory="""You are a senior editor with 15 years of experience at 
    technology publications. You have an excellent ear for when writing 
    sounds robotic, generic, or over-polished. Your edits make articles 
    sharper and more human, not longer and more formal. You cut ruthlessly 
    and add only when something is genuinely missing. You pay special 
    attention to the opening line — if it doesn't make you want to keep 
    reading, you rewrite it.""",
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
        description=f"""Research the following topic thoroughly: {topic}
        
        Use the web search tool to find:
        1. Current state of this topic in 2025/2026
        2. At least two specific statistics or data points
        3. One real-world example or case study
        4. The most common misconception people have about this topic
        5. One surprising or counterintuitive angle
        
        Compile everything into a structured research brief.""",
        
        expected_output="""A structured research brief containing:
        - Topic overview (3-4 sentences)
        - 2-3 specific facts with sources noted
        - One concrete real-world example
        - The main misconception about this topic
        - One surprising angle or insight
        Total length: 300-400 words""",
        
        agent=research_analyst
    )
    
    writing_task = Task(
        description=f"""Using the research brief provided, write a LinkedIn article about: {topic}
        
        Requirements:
        - Length: 400-500 words
        - Tone: Conversational and direct, first person
        - Structure: Strong hook → key insight → specific example → practical takeaway → question
        - Paragraphs: Maximum 3 sentences each
        - Opening: Must NOT start with 'I', must make someone stop scrolling
        - Ending: A genuine question that invites thoughtful responses
        - No hashtags, no emojis, no bullet points""",
        
        expected_output="""A complete LinkedIn article of 400-500 words that opens 
        with a compelling hook, flows naturally, sounds human, and ends with 
        a specific interesting question. No hashtags or emojis.""",
        
        agent=content_writer
    )
    
    editing_task = Task(
        description="""Edit and polish the LinkedIn article draft you received.
        
        1. Fix any sentences that sound robotic or generic
        2. Strengthen the opening hook if it's weak
        3. Remove filler phrases: 'It's worth noting', 'In conclusion', 
           'At the end of the day', 'In today's world'
        4. Tighten paragraphs longer than 3 sentences
        5. Make the ending question more specific if it's generic
        
        Return only the final polished article, no commentary.""",
        
        expected_output="""The final polished LinkedIn article. Same length as the 
        draft but noticeably more natural. No meta-commentary, just the article.""",
        
        agent=editor
    )
    
    return [research_task, writing_task, editing_task]

# ─────────────────────────────────────────────
# MAIN RUNNER
# This is where memory and Sheets come together
# ─────────────────────────────────────────────
def run_crew_with_memory_and_sheets():
    print("=" * 60)
    print("AI Content Crew — Starting up")
    print("=" * 60)
    
    # Step 1: Load memory
    memory = load_memory()
    print(f"\nMemory loaded. Articles written so far: {memory['total_articles_written']}")
    if memory["completed_topics"]:
        print(f"Topics already covered: {', '.join(memory['completed_topics'][-3:])}")
    
    # Step 2: Get next topic from Google Sheets
    print("\nChecking Content Queue sheet for next topic...")
    queued_item = get_next_queued_topic()
    
    if queued_item is None:
        print("No queued topics found in the sheet.")
        print("Add topics with Status = 'Queued' to your Content Queue sheet.")
        return
    
    topic = queued_item["topic"]
    row_number = queued_item["row_number"]
    
    print(f"Found queued topic: '{topic}' (row {row_number})")
    
    # Step 3: Check memory — has this been written before?
    if topic_already_written(topic, memory):
        print(f"\nSkipping — this topic was already written about.")
        print("Update the topic in your sheet or mark this row as 'Skip'.")
        # Update the sheet so this row doesn't get picked up again
        update_row_status(row_number, "Already Written")
        return
    
    # Step 4: Mark as "Processing" in the sheet immediately
    # This prevents the topic from being picked up by a second run
    # if the crew takes a long time and the script is run again
    update_row_status(row_number, "Processing")
    
    # Step 5: Run the crew
    print(f"\nRunning crew for: '{topic}'")
    print("-" * 60)
    
    try:
        tasks = create_tasks(topic)
        
        crew = Crew(
            agents=[research_analyst, content_writer, editor],
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        article_text = str(result)
        
        print("\n" + "=" * 60)
        print("CREW COMPLETE")
        print("=" * 60)
        print("\nFINAL ARTICLE:")
        print(article_text)
        
        # Step 6: Save to file
        filename = f"crew_article_{topic[:40].replace(' ', '_')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n\n")
            f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
            f.write(article_text)
        print(f"\nSaved to: {filename}")
        
        # Step 7: Update the sheet with the result
        update_row_status(
            row_number,
            status="Ready to Review",
            article=article_text
        )
        
        # Step 8: Update memory
        memory = mark_topic_complete(topic, memory)
        save_memory(memory)
        print(f"\nMemory updated. Total articles written: {memory['total_articles_written']}")
        
    except Exception as e:
        print(f"\nCrew failed: {e}")
        # If something went wrong, reset the row back to Queued
        # so it gets picked up on the next run
        update_row_status(row_number, "Queued")
        print("Row reset to 'Queued' for retry.")

if __name__ == "__main__":
    run_crew_with_memory_and_sheets()