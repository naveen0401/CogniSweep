import json
import os

import requests


ENDPOINT = os.environ.get("MADLAD_ENDPOINT", "http://127.0.0.1:8200/translate")
API_KEY = os.environ.get("MADLAD_API_KEY", "")

payload = {
    "texts": [
        "Save changes",
        "Email Address: {{email}}",
    ],
    "source_language": "English",
    "target_language": "Spanish",
    "domain": "Software UI",
}

headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
r = requests.post(ENDPOINT, json=payload, headers=headers, timeout=600)
print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
