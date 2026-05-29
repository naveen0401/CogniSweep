# ErrorSweep + IndicTrans2 setup

IndicTrans2 is the built-in Indian-language MT worker for ErrorSweep. Use it
for Telugu, Hindi, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati,
Punjabi, Urdu, Odia, Assamese, Sanskrit, Nepali, and related Indic language
routes.

## Router role

ErrorSweep Pro routes no-key MT like this:

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
$env:INDICTRANS2_EN_INDIC_MODEL="C:\ErrorSweep\Error-Sweep\models\indictrans2-en-indic-dist-200M"
$env:INDICTRANS2_INDIC_EN_MODEL="C:\ErrorSweep\Error-Sweep\models\indictrans2-indic-en-dist-200M"
$env:INDICTRANS2_INDIC_INDIC_MODEL="C:\ErrorSweep\Error-Sweep\models\indictrans2-indic-indic-dist-320M"
.\.venv\Scripts\python.exe -m uvicorn indictrans2_worker:app --host 127.0.0.1 --port 8000
```

## Connect ErrorSweep

```toml
INDICTRANS2_ENDPOINT = "http://127.0.0.1:8000/translate"
INDICTRANS2_API_KEY = ""
```

## Test

```powershell
curl http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe test_indictrans2_worker.py
.\.venv\Scripts\python.exe test_builtin_mt_engines.py
```

Then open ErrorSweep Pro and expand **Built-in MT engine diagnostics**.
