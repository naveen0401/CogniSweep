import json
import argparse
import os
from pathlib import Path


def strip_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(path)
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].strip()
        if "=" not in text:
            continue
        key, raw_value = text.split("=", 1)
        key = key.strip()
        if key:
            os.environ[key] = strip_env_value(raw_value)


parser = argparse.ArgumentParser(description="Smoke test CogniSweep built-in MT engines.")
parser.add_argument("--env-file", default="", help="Optional env file with MT endpoint settings.")
args = parser.parse_args()
if args.env_file:
    load_env_file(args.env_file)

from translator_router import builtin_engine_status, smoke_test_builtin_engines, translate_batch


print("== Engine health ==")
print(json.dumps(builtin_engine_status(), indent=2, ensure_ascii=False, default=str))

print("\n== Direct engine smoke tests ==")
print(json.dumps(smoke_test_builtin_engines(timeout=120), indent=2, ensure_ascii=False, default=str))

print("\n== Router no-key file-style test ==")
samples = [
    ("English", "Spanish", ["Save changes", "Upload file"]),
    ("English", "Telugu", ["Save changes", "Upload file"]),
]

for source, target, texts in samples:
    try:
        translations, usage = translate_batch(
            source_language=source,
            target_language=target,
            texts=texts,
            user_api_key="",
            protected_terms=[],
            metadata={"test": "builtin_mt"},
        )
        print(json.dumps({
            "source_language": source,
            "target_language": target,
            "translations": translations,
            "usage": usage,
        }, indent=2, ensure_ascii=False, default=str))
    except Exception as exc:
        print(json.dumps({
            "source_language": source,
            "target_language": target,
            "error": str(exc),
        }, indent=2, ensure_ascii=False))
