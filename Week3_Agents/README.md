# Week 3 — AI Agent Systems

A progression from single autonomous agents to a full 
multi-agent content generation system integrated with 
workflow automation tools.

## What's in Here

### Day 15 — ReAct Agent (`agents/simple_agent.py`)
A LangChain agent with web search that uses the 
Think → Act → Observe loop to autonomously research 
topics without a fixed sequence of steps.

### Day 16 — LangGraph Pipeline (`agents/content_graph.py`)
A stateful 3-node graph where Researcher → Writer → Reviewer 
pass a shared state dictionary between them. Guaranteed 
sequence, full visibility at each stage.

### Day 17-18 — CrewAI Content Crew (`agents/content_crew.py`, `agents/content_crew_v2.py`)
Three specialized agents — Research Analyst, Content Writer, 
Senior Editor — collaborating sequentially to produce 
LinkedIn articles from a single topic input.

v2 adds: persistent memory to prevent duplicate topics, 
and Google Sheets integration to read topics from a 
content queue and write results back automatically.

### Day 20 — Full Pipeline Bridge (`agents/crew_to_n8n.py`)
Connects the CrewAI crew to n8n via webhook. One CLI 
command triggers the full chain:

Agent crew runs → output POSTed to n8n → Notion page 
created, Google Sheet updated, Slack notification sent.

## Architecture

See `demo/architecture.md` for the full system diagram.

## Sample Output

See `demo/` for a real generated article and JSON output.

## Tech Stack

Python · CrewAI · LangGraph · LangChain · Groq API 
(Llama 3.3 70B) · DuckDuckGo Search · gspread · 
Google Sheets API · n8n

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Add your GROQ_API_KEY
```

### 3. For Google Sheets integration
- Create a service account in Google Cloud Console
- Enable Google Sheets API and Google Drive API  
- Download credentials JSON → save as `google_credentials.json`
- Share your Content Queue sheet with the service account email

### 4. Run the full pipeline
```bash
python agents/crew_to_n8n.py
```

### 5. Run individual components
```bash
# Simple ReAct agent
python agents/simple_agent.py

# LangGraph pipeline
python agents/content_graph.py

# CrewAI crew only (no Sheets or n8n)
python agents/content_crew.py
```

## Key Technical Decisions

**Why CrewAI over pure LangChain?**
CrewAI's role/goal/backstory abstraction produces 
noticeably better output than generic LLM calls because 
each agent is primed to think from a specific professional 
perspective.

**Why Groq over OpenAI?**
Groq's free tier provides fast inference with strong models. 
The OpenAI-compatible API means zero code changes to switch 
if needed.

**Why JSON output from the editor agent?**
Structured output from the final agent makes downstream 
integration trivial — parse once, route anywhere.

**Known compatibility fix:**
CrewAI 1.x adds a `cache_breakpoint` property that Groq's 
strict API rejects. A LiteLLM patch strips this before 
each request. See the top of any crew file for the 
implementation.

## What This Demonstrates

- Multi-agent orchestration with role specialization
- Stateful graph-based pipelines
- Production patterns: memory, idempotency, error recovery
- Cross-system integration: agents → webhooks → no-code tools
- Business value: content creation from 2 hours to 8 minutes