import json
import requests

URL = "http://127.0.0.1:8000/translate"

payload = {
    "texts": ["How are you?", "Upload file", "Email Address: {{email}}"],
    "source_language": "eng_Latn",
    "target_language": "tel_Telu",
    "domain": "Software UI",
}

print("Calling:", URL)
res = requests.post(URL, json=payload, timeout=600)
print("Status:", res.status_code)
print("Raw:")
print(res.text[:5000])
try:
    print("JSON:")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as exc:
    print("Not JSON:", exc)

