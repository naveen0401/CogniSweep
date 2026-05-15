# ErrorSweep Clean Reset v17

This package is a clean replacement set for the current prototype.

## Replace these files in GitHub

- `app.py`
- `requirements.txt`
- `local_translation_engine.py`
- `qa_engine_global_v17.py`
- `docker-compose.libretranslate.yml`
- `Dockerfile.indictrans2`
- `docker-compose.indictrans2.yml`
- `indictrans2_worker.py`
- `requirements_indictrans2_worker.txt`
- `test_indictrans2_worker.py`
- `.gitignore`

## Streamlit secrets

For local testing:
```toml
LIBRETRANSLATE_ENDPOINT = "http://127.0.0.1:5000"
INDICTRANS2_ENDPOINT = "http://127.0.0.1:8000/translate"
LOCAL_TRANSLATION_SOURCE_LANGUAGE = "English"

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
```

For Streamlit Cloud, use Cloudflare URLs:
```toml
LIBRETRANSLATE_ENDPOINT = "https://your-libretranslate.trycloudflare.com"
INDICTRANS2_ENDPOINT = "https://your-indictrans2.trycloudflare.com/translate"
LOCAL_TRANSLATION_SOURCE_LANGUAGE = "English"
```

## LibreTranslate
```bash
docker compose -f docker-compose.libretranslate.yml up -d
curl http://127.0.0.1:5000/languages
```

## IndicTrans2
Create `.env`:
```bash
HF_TOKEN=hf_your_real_huggingface_read_token
```

Then:
```bash
docker compose --env-file .env -f docker-compose.indictrans2.yml up -d --build
curl http://127.0.0.1:8000/health
python test_indictrans2_worker.py
```

## Important
Do not commit:
- `.env`
- `.streamlit/secrets.toml`
- `cloudflared`

## Current behavior
- French/Spanish/German/Arabic route to LibreTranslate.
- Telugu/Hindi/Tamil/Malayalam/Kannada route to IndicTrans2.
- Pro output is blocked if translation coverage is blank or placeholder-only.
- Human Review and Scorecards are included in the MVP.

