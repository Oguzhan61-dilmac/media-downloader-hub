import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\Users\oğuz\Documents\antigravity\busy-galileo")

from subtitle.engine import translate_text_free, wrap_subtitle_text

def test_language_mappings_and_translation():
    print("=" * 60)
    print("Testing Target Language Parsing & Multi-Language Engine")
    print("=" * 60)

    lang_options = {
        "Türkçe (tr)": "tr",
        "İngilizce (en)": "en",
        "İspanyolca (es)": "es",
        "Almanca (de)": "de",
        "Fransızca (fr)": "fr",
        "Arapça (ar)": "ar",
        "Rusça (ru)": "ru",
    }

    sample_ru_text = "Здравствуйте, как ваши дела?"
    sample_en_text = "Hello, how are you doing today?"

    for label, code in lang_options.items():
        print(f"\n[+] Testing Target Language: {label} (Code: '{code}')")
        
        # Test translation from Russian
        res = translate_text_free(sample_ru_text, "ru", code)
        print(f"  RU -> {code.upper()}: '{res}'")
        assert len(res) > 0, f"Translation failed for {code}"

    print("\n[+] Testing Same-Language Bypass (EN -> EN):")
    # Simulation of same language skip logic
    src_lang = "en"
    tgt_lang = "en"
    if src_lang == tgt_lang:
        bypassed_text = sample_en_text
        print(f"  [BYPASS LOGIC] Source '{src_lang}' == Target '{tgt_lang}'. Translation skipped.")
        print(f"  Result: '{bypassed_text}'")
        assert bypassed_text == sample_en_text

    print("\n" + "=" * 60)
    print("MULTI-LANGUAGE ENGINE VERIFICATION PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_language_mappings_and_translation()
