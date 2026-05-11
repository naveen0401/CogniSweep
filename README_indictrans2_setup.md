# ErrorSweep + IndicTrans2 setup

This setup adds a **self-hosted Indian-language translation engine** for ErrorSweep Pro.
It is mainly for Telugu, Hindi, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu, Odia, and other Indic languages.

## What this gives you

ErrorSweep Pro routing becomes:

```text
Translation Memory first
→ Glossary / rules second
→ OpenAI if available
→ LOCAL_TRANSLATION_ENDPOINT if available
→ Offline reference mode if nothing else exists
```

For Telugu without OpenAI/Gemini API keys, use this IndicTrans2 worker.

## Hardware note

IndicTrans2 is heavier than LibreTranslate. CPU works for testing but can be slow and may be killed on small Codespaces machines. For production use a GPU VPS/server or a larger CPU machine.

Start with the distilled model:

```text
ai4bharat/indictrans2-en-indic-dist-200M
```

## Files to add to GitHub/Codespaces

Put these files beside `app.py`:

```text
indictrans2_worker.py
requirements_indictrans2_worker.txt
Dockerfile.indictrans2
docker-compose.indictrans2.yml
test_indictrans2_worker.py
```

## Option A: run with Docker

Build and start:

```bash
docker compose -f docker-compose.indictrans2.yml up -d --build
```

Watch logs:

```bash
docker compose -f docker-compose.indictrans2.yml logs -f
```

The first request may download models and take time.

Test health:

```bash
curl http://localhost:8000/health
```

Test Telugu translation:

```bash
python test_indictrans2_worker.py
```

## Option B: run directly without Docker

```bash
python -m venv .venv-indic
source .venv-indic/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_indictrans2_worker.txt
python indictrans2_worker.py
```

Then test in another terminal:

```bash
python test_indictrans2_worker.py
```

## Connect ErrorSweep local app to IndicTrans2

In `.streamlit/secrets.toml` for local/Codespaces testing:

```toml
LOCAL_TRANSLATION_ENDPOINT = "http://localhost:8000/translate"
LOCAL_TRANSLATION_PROVIDER = "generic"
LOCAL_TRANSLATION_API_KEY = ""
LOCAL_TRANSLATION_SOURCE_LANGUAGE = "English"
```

Then restart ErrorSweep:

```bash
pkill -f streamlit
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8503
```

Open port 8503 and test:

```text
ErrorSweep Pro → Target language: Telugu → Run Translate + Review
```

## Keep LibreTranslate too?

Yes. Use LibreTranslate for Spanish/French/German/etc. and IndicTrans2 for Indian languages.
For now, switch the local secret depending on what you are testing:

### LibreTranslate

```toml
LOCAL_TRANSLATION_ENDPOINT = "http://localhost:5000"
LOCAL_TRANSLATION_PROVIDER = "libretranslate"
LOCAL_TRANSLATION_SOURCE_LANGUAGE = "auto"
```

### IndicTrans2

```toml
LOCAL_TRANSLATION_ENDPOINT = "http://localhost:8000/translate"
LOCAL_TRANSLATION_PROVIDER = "generic"
LOCAL_TRANSLATION_SOURCE_LANGUAGE = "English"
```

Later we can add automatic routing in the app:

```text
Spanish/French/German → LibreTranslate
Telugu/Hindi/Tamil/etc. → IndicTrans2
```

## Supported language names for target_language

Common examples:

```text
Telugu
Hindi
Tamil
Kannada
Malayalam
Bengali
Marathi
Gujarati
Punjabi
Urdu
Odia
Assamese
Sanskrit
Nepali
```

## Important

Do not commit `.streamlit/secrets.toml`.

```bash
echo ".streamlit/secrets.toml" >> .gitignore
```
