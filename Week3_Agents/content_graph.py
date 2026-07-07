import os
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq

load_dotenv()

# Initialize the LLM
# Same model as yesterday, same setup
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0
)

# Define your state schema
# TypedDict means this is a dictionary where each key has a defined type
# Every node in the graph receives this full state and returns an updated version
class ContentState(TypedDict):
    topic: str
    research: str
    draft: str
    final: str

# ─────────────────────────────────────────────
# NODE 1: RESEARCHER
# This node's only job is to generate research about the topic
# It reads: state["topic"]
# It writes: state["research"]
# ─────────────────────────────────────────────
def researcher_node(state: ContentState) -> ContentState:
    print("\n[RESEARCHER] Starting research...")
    
    topic = state["topic"]
    
    prompt = f"""You are a research analyst. Your job is to gather key facts and insights about a topic.

Topic: {topic}

Provide:
1. A brief overview of the topic (2-3 sentences)
2. Three specific, interesting facts or recent developments
3. The main audience who cares about this topic
4. One controversial or surprising angle most people don't know

Be specific and factual. This research will be used to write a LinkedIn article."""

    response = llm.invoke(prompt)
    research = response.content
    
    print(f"[RESEARCHER] Research complete. ({len(research)} chars)")
    
    # Return the updated state
    # Important: you return the FULL state, not just the changed field
    # Unchanged fields carry forward exactly as they were
    return {
        "topic": state["topic"],
        "research": research,
        "draft": state["draft"],
        "final": state["final"]
    }

# ─────────────────────────────────────────────
# NODE 2: WRITER
# This node reads the research and writes a draft article
# It reads: state["topic"] and state["research"]
# It writes: state["draft"]
# ─────────────────────────────────────────────
def writer_node(state: ContentState) -> ContentState:
    print("\n[WRITER] Writing draft...")
    
    topic = state["topic"]
    research = state["research"]
    
    prompt = f"""You are a LinkedIn content writer. Write a 400-500 word LinkedIn article based on this research.

Topic: {topic}

Research to use:
{research}

Writing guidelines:
- Start with a hook that makes someone stop scrolling
- Write in first person, conversational tone
- Use short paragraphs — maximum 3 sentences each
- Include one specific example or data point from the research
- End with a clear takeaway and a question that invites comments
- No hashtags
- Sound like a knowledgeable human, not a marketing brochure"""

    response = llm.invoke(prompt)
    draft = response.content
    
    print(f"[WRITER] Draft complete. ({len(draft)} chars)")
    
    return {
        "topic": state["topic"],
        "research": state["research"],
        "draft": draft,
        "final": state["final"]
    }

# ─────────────────────────────────────────────
# NODE 3: REVIEWER
# This node reads the draft and produces a polished final version
# It reads: state["draft"]
# It writes: state["final"]
# ─────────────────────────────────────────────
def reviewer_node(state: ContentState) -> ContentState:
    print("\n[REVIEWER] Reviewing and polishing...")
    
    draft = state["draft"]
    
    prompt = f"""You are a senior editor. Review this LinkedIn article draft and produce an improved final version.

Draft to review:
{draft}

Your job:
1. Fix any sentences that sound robotic or unnatural
2. Strengthen the opening hook if it's weak
3. Make sure the ending question is genuinely interesting, not generic
4. Cut any filler phrases like "In conclusion", "It's important to note", "In today's world"
5. Ensure the article sounds like one consistent human voice throughout

Return ONLY the final polished article — no commentary, no explanation, just the improved text."""

    response = llm.invoke(prompt)
    final = response.content
    
    print(f"[REVIEWER] Final version complete. ({len(final)} chars)")
    
    return {
        "topic": state["topic"],
        "research": state["research"],
        "draft": state["draft"],
        "final": final
    }

# ─────────────────────────────────────────────
# BUILD THE GRAPH
# This is where you define the structure —
# which nodes exist and in what order they connect
# ─────────────────────────────────────────────

# Create a new graph that uses ContentState as its state schema
graph = StateGraph(ContentState)

# Add your three nodes
# First argument is the name you'll use to reference this node
# Second argument is the function to call
graph.add_node("researcher", researcher_node)
graph.add_node("writer", writer_node)
graph.add_node("reviewer", reviewer_node)

# Define the edges — the path data takes through the graph
# set_entry_point defines where execution starts
graph.set_entry_point("researcher")

# add_edge defines what comes after each node
graph.add_edge("researcher", "writer")
graph.add_edge("writer", "reviewer")
graph.add_edge("reviewer", END)

# END is a special LangGraph constant that means
# "this is where the graph stops"

# Compile the graph into a runnable object
app = graph.compile()

# ─────────────────────────────────────────────
# RUN IT
# ─────────────────────────────────────────────
def run_content_pipeline(topic: str):
    print(f"\nRunning content pipeline for topic:")
    print(f"'{topic}'")
    print("=" * 60)
    
    # Initial state — only topic is filled in
    # The other fields start as empty strings
    # Each node will fill in its field as the state passes through
    initial_state: ContentState = {
        "topic": topic,
        "research": "",
        "draft": "",
        "final": ""
    }
    
    # Run the graph
    result = app.invoke(initial_state)
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    
    print("\n--- RESEARCH ---")
    print(result["research"])
    
    print("\n--- DRAFT ---")
    print(result["draft"])
    
    print("\n--- FINAL ARTICLE ---")
    print(result["final"])
    
    # Save to a file
    filename = f"article_{topic[:30].replace(' ', '_')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {topic}\n\n")
        f.write("## Research\n\n")
        f.write(result["research"])
        f.write("\n\n## Draft\n\n")
        f.write(result["draft"])
        f.write("\n\n## Final Article\n\n")
        f.write(result["final"])
    
    print(f"\nSaved to: {filename}")
    return result

if __name__ == "__main__":
    run_content_pipeline("What I learned building my first AI agent")