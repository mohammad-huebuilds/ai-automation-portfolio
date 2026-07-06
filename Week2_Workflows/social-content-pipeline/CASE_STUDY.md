# Case Study: AI Content Pipeline for Coaches and Consultants

## The Problem

Content creators and consultants who post consistently 
on LinkedIn and X spend 1-3 hours per week just writing 
posts — before any editing, scheduling, or engagement.

## The Solution

A queue-based content pipeline where the creator adds 
topics to a spreadsheet and the system handles the writing.

Each morning the workflow:
1. Picks up all queued topics from the sheet
2. Generates a LinkedIn post and X post for each one
3. Returns drafts to the sheet with status "Ready to Review"
4. Sends a Slack preview so the creator can review from 
   their phone

The creator reads the drafts, edits anything that needs 
work, and publishes — spending 10-15 minutes on review 
instead of 2 hours on writing from scratch.

## Impact

- Content creation time reduced from ~2 hours to ~15 minutes 
  per week for a 5-post schedule
- Consistent posting schedule maintained even during busy weeks
- Creator's voice preserved through prompt customization
  specific to their tone and style

## Customization

The LLM prompt is fully configurable — brand voice, 
tone guidelines, post structure, and content rules 
are all defined in plain English inside the workflow.