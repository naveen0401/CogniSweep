import os
import requests

if os.environ.get("RUN_LIVE_MT_TESTS", "").strip().lower() not in {"1", "true", "yes", "on"}:
    print("Skipped live OPUS-MT endpoint test. Set RUN_LIVE_MT_TESTS=1 to run it.")
    raise SystemExit(0)

ENDPOINT = os.environ.get("OPUS_MT_ENDPOINT", "http://127.0.0.1:8100/translate")
API_KEY = os.environ.get("OPUS_MT_API_KEY", "")

payload = {
    "texts": [
        "Welcome to Docflow – a faster way to create, edit, and collaborate on documents.",
        "Email Address: {{email}}",
        "You’ve burned {{calories_burned}} kcal today. Keep going!",
    ],
    "source_language": "English",
    "target_language": "French",
    "domain": "Software UI",
}

headers = {"Content-Type": "application/json"}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

r = requests.post(ENDPOINT, json=payload, headers=headers, timeout=180)
print("Status:", r.status_code)
print(r.text[:3000])

