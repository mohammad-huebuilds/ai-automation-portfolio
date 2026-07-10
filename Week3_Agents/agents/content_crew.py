import os
import re
import litellm
from dotenv import load_dotenv
# ... (your other imports)
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from ddgs import DDGS

load_dotenv()

# Tell LiteLLM to automatically ignore parameters that Groq doesn't support
litellm.drop_params = True

# ─────────────────────────────────────────────
# WORKAROUND FOR CREWAI 1.x + GROQ BUG
# CrewAI adds a 'cache_breakpoint' property to messages for prompt caching.
# Groq's API is strict and rejects unknown properties, causing a crash.
# This intercepts the request and strips it out before it gets sent.
# ─────────────────────────────────────────────
original_completion = litellm.completion

def strip_cache_breakpoint(*args, **kwargs):
    if 'messages' in kwargs:
        for msg in kwargs['messages']:
            if isinstance(msg, dict) and 'cache_breakpoint' in msg:
                del msg['cache_breakpoint']
    return original_completion(*args, **kwargs)

litellm.completion = strip_cache_breakpoint
# ─────────────────────────────────────────────

# Initialize the LLM using CrewAI's native LLM class
llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.3,
    api_key=os.getenv("GROQ_API_KEY")
)



# ─────────────────────────────────────────────
# DEFINE THE TOOLS
# Using the @tool decorator from crewai_tools
# The docstring becomes the tool description —
# agents read this to decide when and how to use the tool
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
            return "Query too short. Please provide a more specific search term."
        
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
        return f"Search error: {str(e)}. Try a simpler query."

# ─────────────────────────────────────────────
# DEFINE THE AGENTS
# Each agent is a specialist with a clear identity
# The more specific the role/goal/backstory,
# the better the output quality
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
    # allow_delegation=False means this agent cannot
    # hand off work to other agents — it must do its own task
    # Set to True only for manager agents in hierarchical crews
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
# DEFINE THE TASKS
# Tasks are more specific than agent goals
# expected_output acts as a quality benchmark
# the agent tries to match
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
        - Ending: A genuine question that invites thoughtful responses, not a generic 'What do you think?'
        - No hashtags, no emojis, no bullet points in the final article""",
        
        expected_output="""A complete LinkedIn article of 400-500 words that:
        - Opens with a compelling hook that isn't a question
        - Flows naturally from insight to example to takeaway
        - Sounds like a real person wrote it
        - Ends with a specific, interesting question
        - Contains no hashtags or emojis""",
        
        agent=content_writer
    )
    
    editing_task = Task(
        description="""Edit and polish the LinkedIn article draft you received.
        
        Specifically:
        1. Read the entire article first before making any changes
        2. Identify any sentences that sound robotic or generic — rewrite them
        3. Check the opening line — if it's weak, make it stronger
        4. Remove any filler phrases: 'It's worth noting', 'In conclusion', 
           'At the end of the day', 'In today's world', 'More than ever'
        5. Tighten any paragraphs longer than 3 sentences
        6. Check the ending question — make it more specific if it's generic
        7. Read the final version aloud in your head — does it sound human?
        
        Return only the final polished article, no commentary.""",
        
        expected_output="""The final polished LinkedIn article, improved from the draft.
        Same approximate length (400-500 words) but noticeably more natural and 
        compelling than the draft. No meta-commentary — just the article itself.""",
        
        agent=editor
    )
    
    return [research_task, writing_task, editing_task]

# ─────────────────────────────────────────────
# ASSEMBLE AND RUN THE CREW
# ─────────────────────────────────────────────

def run_crew(topic: str):
    print(f"\nStarting crew for topic: '{topic}'")
    print("=" * 60)
    
    tasks = create_tasks(topic)
    
    crew = Crew(
        agents=[research_analyst, content_writer, editor],
        tasks=tasks,
        process=Process.sequential,
        # Sequential means: research first, then writing, then editing
        # Each agent receives the output of all previous tasks
        # automatically — you don't have to wire this manually
        verbose=True
    )
    
    result = crew.kickoff()
    
    print("\n" + "=" * 60)
    print("CREW COMPLETE")
    print("=" * 60)
    print("\nFINAL ARTICLE:")
    print(result)
    
    # Save the output
    filename = f"crew_article_{topic[:40].replace(' ', '_')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {topic}\n\n")
        f.write("## Final Article\n\n")
        f.write(str(result))
    
    print(f"\nSaved to: {filename}")
    return result

if __name__ == "__main__":
    run_crew("What I learned from building my first automation workflow")