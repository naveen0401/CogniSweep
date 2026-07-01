import pytest

import translator_router


def test_amazon_translate_language_code_mapping():
    assert translator_router.normalize_language_code("French") == "fr"
    assert translator_router.normalize_language_code("Telugu") == "te"
    assert translator_router.normalize_language_code("auto-detect") == "auto"
    assert translator_router.normalize_language_code("pt-BR") == "pt-BR"


def test_managed_mt_disabled_does_not_translate(monkeypatch):
    monkeypatch.setenv("COGNISWEEP_MT_PROVIDER", "disabled")
    monkeypatch.delenv("ERRORSWEEP_MT_PROVIDER", raising=False)

    status = translator_router.builtin_engine_status()[0]
    assert status["enabled"] is False
    assert status["ready"] is False

    with pytest.raises(translator_router.TranslationRouteError):
        translator_router.translate_batch(
            source_language="en",
            target_language="fr",
            texts=["Hello"],
        )


def test_empty_batch_is_safe_when_disabled(monkeypatch):
    monkeypatch.setenv("COGNISWEEP_MT_PROVIDER", "disabled")
    translations, usage = translator_router.translate_batch(
        source_language="en",
        target_language="fr",
        texts=[],
    )
    assert translations == []
    assert usage["success"] is True
    assert usage["characters"] == 0
