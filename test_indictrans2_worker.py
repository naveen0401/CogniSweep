import json
import os
import requests

URL = "http://localhost:8000/translate"
API_KEY = os.environ.get("INDICTRANS2_API_KEY", "")

payload = {
    "texts": [
        "Welcome Screen",
        "Upload file",
        "Welcome to Docflow – a faster way to create, edit, and collaborate on documents.",
        "Email Address: {{email}}",
    ],
    "source_language": "English",
    "target_language": "Telugu",
    "domain": "Software UI",
}

headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
r = requests.post(URL, json=payload, headers=headers, timeout=300)
print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
