# Lead Enrichment Automation

An n8n workflow that automatically researches companies 
from a Google Sheet — visiting their websites, extracting 
key business information using an LLM, and writing results 
back to the sheet.

## What It Does

- Reads company names and URLs from a Google Sheet
- Visits each company website and extracts the homepage text
- Uses Llama 3.1 (via Groq) to identify: what the company does,
  their industry, and their likely pain points
- Writes enriched data back to the original sheet row
- Sends Slack notifications on completion and on errors
- Logs every run to a dedicated sheet with timestamps
- Only processes unenriched rows — safe to run repeatedly

## Business Value

Manual lead research for a sales team of 5 typically takes 
2-4 hours per week. This workflow reduces that to under 
5 minutes of automated processing with zero manual effort.

## Tech Stack

n8n · Groq API (Llama 3.1) · Google Sheets · Slack

## How to Use

1. Import `workflow.json` into your n8n instance
2. Add your Google Sheets and Slack credentials
3. Add your Groq API key to the HTTP Request node
4. Add company names and website URLs to your sheet
5. Run the workflow — enriched data appears automatically

## Architecture

```
Google Sheets (read queued rows)
  → IF node (validate URL exists)
    → True: Wait (rate limiting)
      → HTTP Request (fetch website)
        → Code (clean HTML)
          → Groq API (analyze company)
            → Code (parse response)
              → Google Sheets (write back)
                → Slack (success summary)
    → False: Slack (missing URL alert)
  
Error Trigger → Slack (failure alert)
```