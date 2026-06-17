# CogniSweep + IndicTrans2 setup

IndicTrans2 is the built-in Indian-language MT worker for CogniSweep. Use it
for Telugu, Hindi, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati,
Punjabi, Urdu, Odia, Assamese, Sanskrit, Nepali, and related Indic language
routes.

## Router role

CogniSweep Pro routes no-key MT like this:

```text
Translation Memory / rules
-> user API key when provided
-> IndicTrans2 for Indian languages
-> MADLAD-400 for broad global fallback
-> OPUS-MT lightweight fallback
```

## Requirements

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_indictrans2_worker.txt
```

On Windows, `indictranstoolkit` builds a Cython extension. If pip reports that
Microsoft Visual C++ 14.0 or greater is required, install Microsoft C++ Build
Tools first, then rerun the requirements install.

## Download models

Run this once on a machine with Hugging Face access:

```powershell
powershell -ExecutionPolicy Bypass -File .\download_models.ps1 -SkipMadlad
```

This downloads:

```text
models\indictrans2-en-indic-dist-200M
models\indictrans2-indic-en-dist-200M
models\indictrans2-indic-indic-dist-320M
```

## Run locally

`start_builtin_mt.ps1` automatically points the worker to local model folders
when they exist:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_builtin_mt.ps1 -WithIndicTrans2
```

Or start it manually:

```powershell
$env:INDICTRANS2_EN_INDIC_MODEL=".\models\indictrans2-en-indic-dist-200M"
$env:INDICTRANS2_INDIC_EN_MODEL=".\models\indictrans2-indic-en-dist-200M"
$env:INDICTRANS2_INDIC_INDIC_MODEL=".\models\indictrans2-indic-indic-dist-320M"
.\.venv\Scripts\python.exe -m uvicorn indictrans2_worker:app --host 127.0.0.1 --port 8000
```

## Connect CogniSweep

```toml
INDICTRANS2_ENDPOINT = "http://127.0.0.1:8000/translate"
INDICTRANS2_API_KEY = "your-private-token"
```

`INDICTRANS2_API_KEY` is required for the worker process. The server fails
closed at startup if the key is empty.

## Test

```powershell
curl http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe test_indictrans2_worker.py
.\.venv\Scripts\python.exe test_builtin_mt_engines.py
```

Then open CogniSweep Pro and expand **Built-in MT engine diagnostics**.
