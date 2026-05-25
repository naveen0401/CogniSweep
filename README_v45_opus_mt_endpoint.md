# ErrorSweep v45 — First Self-Hosted OPUS-MT Endpoint

This is the next practical step after v44.

v44 removed Azure and NLLB from the active built-in route. That means no-key Pro translation needs at least one self-hosted MT endpoint.

This v45 package starts with OPUS-MT because it is smaller and easier than IndicTrans2.

## What it supports first

English to:

- French
- Spanish
- German
- Italian
- Portuguese

Endpoint:

```text
POST /translate
```

Request:

```json
{
  "texts": ["Welcome to Docflow"],
  "source_language": "English",
  "target_language": "French"
}
```

Response:

```json
{
  "translations": ["Bienvenue à Docflow"],
  "provider": "opus-mt"
}
```

## Files

```text
opus_mt_server_v45.py
Dockerfile.opus-mt
docker-compose.opus-mt.yml
requirements_opus_mt_server.txt
test_opus_mt_endpoint.py
```

## Run locally

```bash
cd /workspaces/Error-Sweep

cp /mnt/data/opus_mt_server_v45.py .
cp /mnt/data/Dockerfile.opus-mt .
cp /mnt/data/docker-compose.opus-mt.yml .
cp /mnt/data/requirements_opus_mt_server.txt .
cp /mnt/data/test_opus_mt_endpoint.py .

docker compose -f docker-compose.opus-mt.yml up -d --build
curl http://127.0.0.1:8100/health
python test_opus_mt_endpoint.py
```

The first run downloads model files and may take time.

## Connect to ErrorSweep v44

For local testing:

```toml
OPUS_MT_ENDPOINT = "http://127.0.0.1:8100/translate"
OPUS_MT_API_KEY = ""
```

For Streamlit Cloud, localhost will not work. You need a public endpoint:

```toml
OPUS_MT_ENDPOINT = "https://opus.yourdomain.com/translate"
OPUS_MT_API_KEY = "your-private-token"
```

## Recommended rollout

1. Test OPUS-MT locally.
2. Enable only French first.
3. Test output + Human Review.
4. Add Spanish/German/Italian/Portuguese.
5. Then build IndicTrans2 separately for Indian languages.

## Important

OPUS-MT quality varies by language pair. Do not treat it as final output.

Use it as:

```text
Basic MT Draft
→ Human Review
→ Final reviewed output
```

