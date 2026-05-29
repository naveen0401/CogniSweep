import json

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
