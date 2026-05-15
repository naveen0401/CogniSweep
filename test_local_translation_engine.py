from local_translation_engine import translate_single_text

print("French test:")
print(translate_single_text("Welcome to Docflow", target_language="French", endpoint="http://127.0.0.1:5000", provider="libretranslate"))

print("Telugu test:")
print(translate_single_text("How are you?", target_language="Telugu", endpoint="http://127.0.0.1:8000/translate", provider="indictrans2"))

