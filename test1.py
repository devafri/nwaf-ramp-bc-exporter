import base64, requests, os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("RAMP_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("RAMP_CLIENT_SECRET", "").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("RAMP_CLIENT_ID and RAMP_CLIENT_SECRET must be set in environment variables.")

auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

print(f"✅ Successfully loaded and encoded authentication string.")
# 💡 Add this line to see the output string for verification:
print(f"Encoded Auth String: {auth}") 

response = requests.post(
  "https://api.ramp.com/developer/v1/token",
  headers={
    # This structure is correct: "Basic " + encoded string
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/x-www-form-urlencoded"
  },
  data={
    "grant_type": "client_credentials",
    "scope": "transactions:read"
  }
)

print(response.json())