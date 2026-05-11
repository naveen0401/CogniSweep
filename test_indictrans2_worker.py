import json
import requests

URL = "http://localhost:8000/translate"

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

r = requests.post(URL, json=payload, timeout=300)
print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
