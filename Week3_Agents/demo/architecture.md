# System Architecture — Week 3 AI Agent System

## Overview

A multi-agent content generation system that autonomously 
researches topics, writes LinkedIn articles and X posts, 
and delivers output to n8n for automated distribution.

## Architecture

INPUT
└── Topic string (from CLI or Google Sheet)
LAYER 1 — Intelligence (CrewAI + Groq)
├── Research Analyst
│     └── Web search → structured research brief
├── Content Writer
│     └── Research brief → LinkedIn article + X post
└── Senior Editor
└── Draft → polished final content (JSON)
LAYER 2 — Memory (JSON file)
└── Prevents duplicate topics across runs
LAYER 3 — Data Source (Google Sheets)
└── Reads next queued topic
└── Updates row status after processing
LAYER 4 — Distribution (n8n webhook)
├── Notion → full article saved as page
├── Google Sheets → draft written back to content queue
└── Slack → preview notification sent
OUTPUT
├── Local JSON file (backup)
├── Notion page (archive)
├── Google Sheet row updated (workflow status)
└── Slack notification (human review trigger)

## Agent Progression This Week

Day 15 — ReAct agent with web search (autonomous reasoning)
Day 16 — LangGraph 3-node pipeline (stateful sequential flow)
Day 17 — CrewAI crew (role-based multi-agent collaboration)
Day 18 — CrewAI + memory + Google Sheets (production patterns)
Day 20 — Full pipeline bridge to n8n (end-to-end system)