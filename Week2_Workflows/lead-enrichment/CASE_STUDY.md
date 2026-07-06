# Case Study: Automated Lead Enrichment for Sales Teams

## The Problem

Sales teams and freelance consultants spend significant time 
manually researching companies before outreach — reading 
websites, identifying what the company does, figuring out 
their pain points. For a team handling 50 leads per week, 
this can consume most of a workday.

## The Solution

An n8n automation workflow that takes a list of company 
names and website URLs from a Google Sheet and automatically:

1. Visits each company website
2. Extracts and cleans the homepage text
3. Sends it to an LLM with a structured analysis prompt
4. Extracts company description, industry, and pain points
5. Writes everything back to the original sheet row
6. Notifies the team via Slack when complete

## Results

- 50 leads researched in under 5 minutes vs 4+ hours manually
- Consistent output format across all leads
- Runs on a schedule — new leads added to the sheet are 
  automatically enriched overnight
- Full error handling ensures failures are caught and flagged 
  immediately rather than discovered days later

## Technical Details

Built in n8n with Google Sheets integration, Groq API 
for LLM calls, and Slack for notifications. Includes 
idempotency logic so the workflow can be run repeatedly 
without duplicating work.