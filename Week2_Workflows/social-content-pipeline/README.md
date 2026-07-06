# Social Media Content Pipeline

An n8n workflow that reads topics from a Google Sheet 
content queue, generates LinkedIn and X (Twitter) post 
drafts using an LLM, and returns finished drafts to the 
sheet for human review before publishing.

## What It Does

- Monitors a Google Sheet for rows with Status = "Queued"
- Generates a LinkedIn post and X post for each topic
  in a single LLM call
- Flags X posts that exceed 240 characters for manual editing
- Updates each row with drafts and changes Status to 
  "Ready to Review"
- Sends a Slack preview of each draft for quick review
- Runs on a daily schedule at 7am

## Design Philosophy

The automation creates content. A human approves it. 
Nothing publishes automatically — the workflow handles 
volume, the human handles judgment.

## Tech Stack

n8n · Groq API (Llama 3.1) · Google Sheets · Slack

## How to Use

1. Import `workflow.json` into n8n
2. Add credentials for Google Sheets and Slack
3. Add your Groq API key
4. Add topics to your Content Queue sheet with Status = "Queued"
5. Run the workflow or wait for the 7am schedule