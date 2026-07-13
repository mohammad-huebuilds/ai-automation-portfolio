import os
import json
import time
import requests
import gspread
import litellm
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ─────────────────────────────────────────────
# LITELLM PATCH
# Applied at the top level so all imported
# modules inherit it automatically
# ─────────────────────────────────────────────
litellm.drop_params = True
original_completion = litellm.completion

def strip_cache_breakpoint(*args, **kwargs):
    if 'messages' in kwargs:
        for msg in kwargs['messages']:
            if isinstance(msg, dict) and 'cache_breakpoint' in msg:
                del msg['cache_breakpoint']
    return original_completion(*args, **kwargs)

litellm.completion = strip_cache_breakpoint

# ─────────────────────────────────────────────
# IMPORT YOUR EXISTING AGENTS
# Each module handles its own platform
# The controller just calls their functions
# ─────────────────────────────────────────────
from twitter_agent import run_twitter_agent
from linkedin_drafter import run_linkedin_drafter
from instagram_agent import run_instagram_agent

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = "#automation-logs"
GOOGLE_CREDENTIALS_FILE = os.path.join(
    os.path.dirname(__file__),
    "google_credentials.json"
)
# This points to the credentials file in the same folder as master_controller.py

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ─────────────────────────────────────────────
# GOOGLE SHEETS FUNCTIONS
# Same pattern as Day 18 — read queued topic,
# update status after processing
# ─────────────────────────────────────────────
def get_sheets_client():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_next_queued_topic(sheet_name="Content Queue") -> dict | None:
    """Get the next row with Status = 'Queued'."""
    try:
        client = get_sheets_client()
        sheet = client.open(sheet_name).sheet1
        all_rows = sheet.get_all_records()
        
        for index, row in enumerate(all_rows):
            if row.get("Status", "").strip() == "Queued":
                return {
                    "topic": row.get("Topic", ""),
                    "platform": row.get("Platform", "both"),
                    "row_number": index + 2
                }
        return None
    except Exception as e:
        print(f"Sheets error: {e}")
        return None

def update_sheet_row(row_number: int, updates: dict, sheet_name="Content Queue"):
    """
    Update specific columns in a sheet row.
    updates is a dict of {column_name: value}.
    """
    try:
        client = get_sheets_client()
        sheet = client.open(sheet_name).sheet1
        headers = sheet.row_values(1)
        
        for column_name, value in updates.items():
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                sheet.update_cell(row_number, col_index, str(value))
        
        print(f"Sheet row {row_number} updated.")
    except Exception as e:
        print(f"Failed to update sheet: {e}")

# ─────────────────────────────────────────────
# SLACK NOTIFICATION
# ─────────────────────────────────────────────
def send_slack_summary(topic: str, results: dict):
    """
    Send a summary of what was generated to Slack.
    results contains the output from each platform agent.
    """
    if not SLACK_BOT_TOKEN:
        print("No SLACK_BOT_TOKEN found — skipping Slack notification.")
        return
    
    # Build a readable summary
    lines = [
        f"✅ *Master Controller Run Complete*",
        f"*Topic:* {topic}",
        f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "*Platform Results:*"
    ]
    
    for platform, result in results.items():
        if result.get("success") or result.get("dry_run"):
            lines.append(f"  ✅ {platform}: Generated successfully")
        else:
            lines.append(f"  ❌ {platform}: Failed — {result.get('error', 'unknown error')}")
    
    # Add a preview of the LinkedIn post if available
    linkedin_result = results.get("linkedin", {})
    if linkedin_result.get("post_text"):
        preview = linkedin_result["post_text"][:200]
        lines.append(f"\n*LinkedIn Preview:*\n{preview}...")
    
    message = "\n".join(lines)
    
    try:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": SLACK_CHANNEL,
                "text": message,
                "mrkdwn": True
            }
        )
        
        result = response.json()
        if result.get("ok"):
            print("Slack notification sent.")
        else:
            print(f"Slack error: {result.get('error')}")
            
    except Exception as e:
        print(f"Slack notification failed: {e}")

# ─────────────────────────────────────────────
# SAVE FULL RUN LOG
# Keeps a record of every controller execution
# ─────────────────────────────────────────────
def save_run_log(topic: str, results: dict, dry_run: bool):
    """Save a complete log of this controller run."""
    log = {
        "topic": topic,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dry_run": dry_run,
        "platforms": results
    }
    
    log_filename = f"run_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_filename, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    
    print(f"Run log saved: {log_filename}")
    return log_filename

# ─────────────────────────────────────────────
# MASTER CONTROLLER
# ─────────────────────────────────────────────
def run_master_controller(
    topic: str = None,
    dry_run: bool = True,
    platforms: list = None
):
    """
    Main controller function.
    
    topic: if None, reads from Google Sheet queue
    dry_run: if True, generates content but doesn't post
    platforms: list of platforms to run, e.g. ["linkedin", "instagram"]
               if None, runs all three
    """
    
    if platforms is None:
        platforms = ["twitter", "linkedin", "instagram"]
    
    print("\n" + "=" * 60)
    print("MASTER CONTROLLER")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Platforms: {', '.join(platforms)}")
    print("=" * 60)
    
    # ─────────────────────────────
    # STEP 1: Get the topic
    # ─────────────────────────────
    row_number = None
    
    if topic is None:
        print("\nReading next topic from Content Queue sheet...")
        queued = get_next_queued_topic()
        
        if queued is None:
            print("No queued topics found.")
            print("Add topics with Status='Queued' to your Content Queue sheet.")
            return
        
        topic = queued["topic"]
        row_number = queued["row_number"]
        print(f"Topic: '{topic}' (row {row_number})")
    else:
        print(f"Topic: '{topic}' (provided directly)")
    
    # ─────────────────────────────
    # STEP 2: Mark as Processing
    # ─────────────────────────────
    if row_number:
        update_sheet_row(row_number, {"Status": "Processing"})
    
    # ─────────────────────────────
    # STEP 3: Run each platform agent
    # Results dict stores output from each
    # ─────────────────────────────
    results = {}
    
    if "twitter" in platforms:
        print("\n" + "-" * 40)
        print("Running X/Twitter agent...")
        print("-" * 40)
        try:
            twitter_output = run_twitter_agent(topic, dry_run=dry_run)
            results["twitter"] = {
                "success": True,
                "tweets": twitter_output.get("tweets", []) if twitter_output else [],
                "filename": f"thread_{topic[:30].replace(' ', '_')}.json"
            }
            print("X/Twitter: Complete")
        except Exception as e:
            print(f"X/Twitter agent failed: {e}")
            results["twitter"] = {"success": False, "error": str(e)}
        
        # Brief pause between platforms
        time.sleep(2)
    
    if "linkedin" in platforms:
        print("\n" + "-" * 40)
        print("Running LinkedIn agent...")
        print("-" * 40)
        try:
            linkedin_output = run_linkedin_drafter(topic, dry_run=dry_run)
            results["linkedin"] = {
                "success": True,
                "post_text": linkedin_output.get("post_text", "") if linkedin_output else "",
                "buffer_result": linkedin_output.get("buffer_result", {}) if linkedin_output else {}
            }
            print("LinkedIn: Complete")
        except Exception as e:
            print(f"LinkedIn agent failed: {e}")
            results["linkedin"] = {"success": False, "error": str(e)}
        
        time.sleep(2)
    
    if "instagram" in platforms:
        print("\n" + "-" * 40)
        print("Running Instagram agent...")
        print("-" * 40)
        try:
            instagram_output = run_instagram_agent(topic, dry_run=dry_run)
            results["instagram"] = {
                "success": True,
                "caption": instagram_output.get("caption", "") if instagram_output else "",
                "image_file": instagram_output.get("image_file", "") if instagram_output else "",
                "buffer_result": instagram_output.get("buffer_result", {}) if instagram_output else {}
            }
            print("Instagram: Complete")
        except Exception as e:
            print(f"Instagram agent failed: {e}")
            results["instagram"] = {"success": False, "error": str(e)}
    
    # ─────────────────────────────
    # STEP 4: Update the sheet
    # ─────────────────────────────
    if row_number:
        sheet_updates = {"Status": "Ready to Review"}
        
        # Write LinkedIn draft back to sheet if available
        linkedin_text = results.get("linkedin", {}).get("post_text", "")
        if linkedin_text:
            sheet_updates["LinkedIn Draft"] = linkedin_text
            # Keep the full draft in the sheet for review
        
        # Write X draft back to sheet if available
        twitter_tweets = results.get("twitter", {}).get("tweets", [])
        if twitter_tweets:
            sheet_updates["X Draft"] = "\n\n".join(twitter_tweets)
            # Store the full thread in one sheet cell as a fallback
            for idx, tweet in enumerate(twitter_tweets, start=1):
                sheet_updates[f"X Draft {idx}"] = tweet

        # Write Instagram draft back to sheet if available
        instagram_caption = results.get("instagram", {}).get("caption", "")
        if instagram_caption:
            sheet_updates["Instagram Draft"] = instagram_caption
        
        sheet_updates["Created At"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        update_sheet_row(row_number, sheet_updates)
    
    # ─────────────────────────────
    # STEP 5: Send Slack summary
    # ─────────────────────────────
    send_slack_summary(topic, results)
    
    # ─────────────────────────────
    # STEP 6: Save run log
    # ─────────────────────────────
    log_file = save_run_log(topic, results, dry_run)
    
    # ─────────────────────────────
    # STEP 7: Print final summary
    # ─────────────────────────────
    print("\n" + "=" * 60)
    print("MASTER CONTROLLER COMPLETE")
    print("=" * 60)
    print(f"\nTopic: '{topic}'")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"\nPlatform Results:")
    
    for platform, result in results.items():
        status = "✅ Success" if result.get("success") else "❌ Failed"
        print(f"  {platform.title()}: {status}")
    
    print(f"\nRun log: {log_file}")
    
    if dry_run:
        print("\nThis was a DRY RUN — no content was posted.")
        print("Run with --live flag to actually post and schedule.")
    
    return results

# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    # Parse CLI arguments
    dry_run = "--live" not in sys.argv
    
    # Optional: specify a topic directly
    # If not provided, reads from Google Sheet
    topic = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            topic = arg
            break
    
    # Optional: specify platforms
    # e.g. --only linkedin,instagram
    platforms = ["twitter", "linkedin", "instagram"]
    for arg in sys.argv[1:]:
        if arg.startswith("--only"):
            platform_str = arg.replace("--only=", "").replace("--only ", "")
            platforms = [p.strip() for p in platform_str.split(",")]
            break
    
    if dry_run:
        print("DRY RUN mode. Use --live to post for real.")
        print("Examples:")
        print("  python master_controller.py")
        print("  python master_controller.py --live")
        print("  python master_controller.py 'your topic here' --live")
        print("  python master_controller.py --only=linkedin,instagram\n")
    
    run_master_controller(
        topic=topic,
        dry_run=dry_run,
        platforms=platforms
    )