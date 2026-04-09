from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator

_translator = GoogleTranslator(source="auto", target="zh-CN")


def translate(text: str) -> str:
    if not text:
        return text
    try:
        return _translator.translate(text[:500])
    except Exception:
        return text


def translate_batch(texts: list) -> list:
    results = [""] * len(texts)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(translate, t): i for i, t in enumerate(texts)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception:
                results[i] = texts[i]
    return results
