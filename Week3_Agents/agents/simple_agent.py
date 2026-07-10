import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain.agents import create_agent
from ddgs import DDGS
import re

load_dotenv()

# Initialize the LLM
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0
)

@tool
def web_search(query: str) -> str:
    """Search the web for current information. Use this when you need facts, recent news, or specific information."""
    try:
        # Clean the query - remove special characters and extra spaces
        query = re.sub(r'[^\w\s\-]', '', query)  # Remove special characters
        query = ' '.join(query.split())  # Remove extra spaces
        
        if not query or len(query) < 3:
            return "Search query too short. Please be more specific."
        
        print(f"🔍 Searching for: {query}")  # Debug output
        
        with DDGS() as ddgs:
            results = []
            try:
                for r in ddgs.text(query, max_results=5):
                    title = r.get('title', 'No title')
                    body = r.get('body', 'No content')
                    results.append(f"- {title}: {body[:200]}...")
                
                if results:
                    return "\n".join(results)
                else:
                    return "No results found. Try a different search term."
            except Exception as search_error:
                return f"Search service error: {str(search_error)}. Please try a simpler query."
    except Exception as e:
        return f"Search error: {str(e)}"

# Create the agent with a more specific system prompt
agent = create_agent(
    model=llm,
    tools=[web_search],
    system_prompt="""You are a helpful research assistant with access to web search.
    
    IMPORTANT INSTRUCTIONS:
    1. When using the web_search tool, keep queries SHORT and SIMPLE (3-5 words maximum)
    2. Use specific, focused search queries like: "AI agent developments 2026" or "latest AI frameworks"
    3. Avoid special characters, punctuation, or complex phrases in search queries
    4. If a search returns no results, try a different simpler query
    5. Synthesize information from multiple searches into a clear answer
    6. If you can't find specific information, acknowledge this and provide general knowledge
    """
)

# Test different goals with error handling
def run_agent_with_retry(goal, max_retries=2):
    """Run the agent with automatic retry on failure."""
    for attempt in range(max_retries):
        try:
            print(f"\n🔄 Attempt {attempt + 1}/{max_retries}")
            result = agent.invoke(
                {"messages": [{"role": "user", "content": goal}]}
            )
            return result["messages"][-1].content
        except Exception as e:
            print(f"❌ Error on attempt {attempt + 1}: {str(e)[:200]}...")
            if attempt < max_retries - 1:
                print("🔄 Retrying...")
                continue
            else:
                return f"Failed after {max_retries} attempts. Error: {str(e)}"

# Test with your problematic goal
goal = "Find 3 examples of businesses that are currently selling AI automation services. What do they charge and what specifically do they offer?"

print("Starting agent...\n")
print("=" * 60)

result = run_agent_with_retry(goal)

print("=" * 60)
print("\nFINAL ANSWER:")
print(result)