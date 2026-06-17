# CogniSweep + MADLAD-400 setup

MADLAD-400 is the broad commercial-friendly global MT fallback for CogniSweep.
Use it for global languages, and keep IndicTrans2 for Indian languages when that
worker is available and gives better quality.

**Hardware Warning:** MADLAD-400 is a 3-Billion parameter model. Running this on a CPU-only machine will result in translations taking 10+ minutes per segment. **An NVIDIA GPU is strictly required for production use.**

## Run locally

First, pre-download the model to your local disk to prevent Hugging Face timeouts:
```powershell
.\download_models.ps1
```

Then, start the worker pointing to your local disk:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_madlad_mt_server.txt

$env:MADLAD_MODEL_NAME=".\models\madlad400-3b-mt"
$env:MADLAD_FORCE_CPU="false"
.\.venv\Scripts\python.exe -m uvicorn madlad_mt_server:app --host 127.0.0.1 --port 8200
```

First startup/request may take a long time because `google/madlad400-3b-mt`
must download and load. A GPU machine is strongly recommended for production.
On CPU-only Windows machines, the worker may be reachable but too slow to
complete even a single segment within several minutes.

To download only MADLAD:

```powershell
powershell -ExecutionPolicy Bypass -File .\download_models.ps1 -SkipIndicTrans2
```

## Connect CogniSweep

```toml
MADLAD_ENDPOINT = "http://127.0.0.1:8200/translate"
MADLAD_API_KEY = "your-private-token"
```

`MADLAD_API_KEY` is required for the worker process. The server fails closed at
startup if the key is empty.

The router order is:

```text
IndicTrans2 for Indian languages when INDICTRANS2_ENDPOINT is configured
MADLAD-400 for broad global coverage
OPUS-MT fallback for tested lightweight pairs
```

## Useful environment variables

```text
MADLAD_MODEL_NAME=google/madlad400-3b-mt
MADLAD_ENDPOINT=http://127.0.0.1:8200/translate
MADLAD_API_KEY=your-private-token
MADLAD_FORCE_CPU=false
MADLAD_BATCH_SIZE=4
MADLAD_MAX_INPUT_LENGTH=256
MADLAD_MAX_NEW_TOKENS=256
MADLAD_NUM_BEAMS=4
MADLAD_TIMEOUT=300
```
