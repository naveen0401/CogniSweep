from pathlib import Path


APP = Path("app.py")
ASYNC = Path("async_workflow_processor.py")


def source() -> str:
    return APP.read_text(encoding="utf-8")


def async_source() -> str:
    return ASYNC.read_text(encoding="utf-8")


def function_body(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}")
    end = text.index(f"def {next_name}", start)
    return text[start:end]


def test_quality_context_state_uses_user_supplied_inputs_only():
    text = source()
    helper = function_body(text, "qa_rules_have_user_instructions", "build_qa_rules_with_user_context")
    state = function_body(text, "qa_quality_input_state", "render_qa_quality_input_notice")
    resources = function_body(text, "qa_workspace_language_resources_available", "qa_rules_have_user_instructions")

    assert 'source == "saved tm"' in helper
    assert 'normalized.startswith("compare against reference document:")' in helper
    assert "qa_rules_have_user_instructions(rule_pack)" in state
    assert 'SESSION_COLLECTION_LIMITS.get("translation_memory", 1000)' in resources
    assert "load_workspace_translation_memory(limit=1)" not in resources


def test_each_workflow_collects_and_passes_quality_context():
    text = source()
    qa = function_body(text, "page_qa", "page_pro")
    pro = function_body(text, "page_pro", "render_assist_panel")
    media = function_body(text, "render_subtitle_transcription_setup", "render_focused_subtitle_workspace")
    scorecards = function_body(text, "page_scorecards", "sectioned_page_layout")

    for body, state_name in (
        (qa, "quality_state"),
        (pro, "pro_quality_state"),
        (media, "media_quality_state"),
        (scorecards, "scorecard_quality_state"),
    ):
        assert "build_qa_rules_with_user_context" in body
        assert "qa_quality_input_state" in body
        assert "render_qa_quality_input_notice" in body
        assert state_name in body


def test_media_completion_validation_uses_client_rules_for_subtitles():
    text = source()
    body = function_body(text, "segment_completion_validation_findings", "render_completion_validation_popover")

    assert 'if editor_key != "transcription":' in body
    assert 'delivery_quality_findings([candidate], target_language or "Target", domain or "Subtitling", rules)' in body


def test_ai_generation_uses_reference_and_language_resources():
    text = source()
    translate = function_body(text, "call_main_api_translate", "generate_transcription_rows_from_video")
    reference_helper = function_body(text, "ai_reference_context_for_rules", "ai_translation_payload_items")
    payload_helper = function_body(text, "ai_translation_payload_items", "build_ai_transcription_prompt")

    assert "reference_text = ai_reference_context_for_rules(rules)" in translate
    assert "translation_items = ai_translation_payload_items(texts, target_language, rules)" in translate
    assert "Client reference context:" in translate
    assert "language_resource_context" in translate
    assert "Prefer exact translation-memory matches" in translate
    assert 'rule_pack.get("_reference_context_text")' in reference_helper
    assert 'rule_pack.get("chunks", [])' in reference_helper
    assert "qa_row_language_resource_context" in payload_helper
    assert 'item["language_resource_context"]' in payload_helper


def test_user_ai_key_takes_priority_over_managed_amazon_translate():
    text = source()
    async_text = async_source()
    translate = function_body(text, "call_main_api_translate", "generate_transcription_rows_from_video")
    pro = function_body(text, "page_pro", "render_assist_panel")
    async_pro = function_body(async_text, "process_pro_task", "process_task_payload")

    assert translate.index("if user_key:") < translate.index("amazon_state = workspace_amazon_translate_state()")
    assert '"allow_managed_amazon_translate": bool(amazon_state.get("allowed") and not user_ai_api_key_available())' in pro
    assert "managed_mt_allowed = bool(params.get(\"allow_managed_amazon_translate\"))" in async_pro
    assert "if translate_batch is not None and managed_mt_allowed:" in async_pro


def test_media_transcription_passes_client_context_to_ai_prompt():
    text = source()
    transcribe = function_body(text, "generate_transcription_rows_from_video", "translate_subtitle_sources")
    prompt_helper = function_body(text, "build_ai_transcription_prompt", "run_global_qa_for_row")
    media = function_body(text, "render_subtitle_transcription_setup", "render_focused_subtitle_workspace")

    assert "transcription_prompt = build_ai_transcription_prompt" in transcribe
    assert "prompt=transcription_prompt" in transcribe
    assert "rules_summary_for_ai(rules)" in prompt_helper
    assert "ai_reference_context_for_rules(rules" in prompt_helper
    assert "AI and QA context" in media
    assert "prompt=media_inline_instructions" in media
    assert "rules=media_rules" in media
    assert 'domain="Subtitling source transcription"' in media
    assert 'domain="Transcription"' in media


def test_async_translation_carries_client_context_metadata():
    text = async_source()
    helper = function_body(text, "translation_context_metadata", "extract_placeholders")
    pro = function_body(text, "process_pro_task", "process_task_payload")

    assert '"dnt_terms": dnt_terms[:200]' in helper
    assert '"glossary": glossary[:200]' in helper
    assert '"instructions": instructions[:80]' in helper
    assert '"reference_context"' in helper
    assert "client_context = translation_context_metadata" in pro
    assert '"client_context": client_context' in pro


if __name__ == "__main__":
    test_quality_context_state_uses_user_supplied_inputs_only()
    test_each_workflow_collects_and_passes_quality_context()
    test_media_completion_validation_uses_client_rules_for_subtitles()
    test_ai_generation_uses_reference_and_language_resources()
    test_user_ai_key_takes_priority_over_managed_amazon_translate()
    test_media_transcription_passes_client_context_to_ai_prompt()
    test_async_translation_carries_client_context_metadata()
    print("Quality context flow checks passed.")
