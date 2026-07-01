# Week 2 — n8n Workflows

Visual automation workflows built in n8n.

## Workflow 1: RSS to Google Sheets with AI Categorization

Pulls the top 5 tech news headlines on a schedule, summarizes each one 
with an LLM, classifies it as AI/Business/Tech, and appends a new row 
to a Google Sheet automatically.

**Nodes:** RSS Feed → Limit → HTTP Request (Groq) → Code → Google Sheets