import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("BUFFER_TOKEN")

if not token:
    print("❌ Error: BUFFER_TOKEN is missing from your .env file!")
    exit(1)

url = "https://api.buffer.com"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 1. First, we must get the Organization ID
org_query = """
query GetOrganizations {
  account {
    organizations {
      id
      name
    }
  }
}
"""

print("Connecting to Buffer's API to find your Organization ID...")
org_response = requests.post(url, json={"query": org_query}, headers=headers)
org_data = org_response.json()

if "errors" in org_data:
    print(f"❌ Error fetching organization: {org_data['errors']}")
    exit(1)

orgs = org_data.get("data", {}).get("account", {}).get("organizations", [])
if not orgs:
    print("❌ No organizations found for this account.")
    exit(1)

organization_id = orgs[0]["id"]
print(f"✅ Found Organization: {orgs[0]['name']} (ID: {organization_id})")

# 2. Now, we use that Organization ID to fetch the channels
channels_query = """
query GetChannels($input: ChannelsInput!) {
  channels(input: $input) {
    id
    name
    service
  }
}
"""

variables = {
    "input": {
        "organizationId": organization_id
    }
}

print("\nFetching connected social profiles...")
channels_response = requests.post(
    url, 
    json={"query": channels_query, "variables": variables}, 
    headers=headers
)
channels_data = channels_response.json()

if "errors" in channels_data:
    print(f"❌ Error fetching channels: {channels_data['errors']}")
    exit(1)

channels = channels_data.get("data", {}).get("channels", [])

if not channels:
    print("⚠️ No social profiles found. Make sure you connected LinkedIn or X in Buffer.")
else:
    print(f"\n✅ Connected Profiles Found: {len(channels)}\n" + "="*30)
    for channel in channels:
        print(f"Name (Service): {channel.get('service').title()}")
        print(f"Username/Label: {channel.get('name')}")
        print(f"Profile ID: {channel.get('id')}")
        print("-" * 30)