from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import urllib.request
import socket
import requests
from deep_translator import MyMemoryTranslator, GoogleTranslator


def get_system_proxies():
    # 1. 优先读取系统环境变量
    http_proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    all_proxy = os.environ.get("all_proxy") or os.environ.get("ALL_PROXY")
    if http_proxy or https_proxy:
        p = {}
        if http_proxy:
            p["http"] = http_proxy
        if https_proxy:
            p["https"] = https_proxy
        return p
    if all_proxy:
        return {"http": all_proxy, "https": all_proxy}

    # 2. 自动检测 macOS 系统代理配置 (Shadowrocket / Surge / 系统代理设置等)
    try:
        sys_proxies = urllib.request.getproxies()
        if sys_proxies and ("http" in sys_proxies or "https" in sys_proxies):
            return sys_proxies
    except Exception:
        pass

    # 3. 扫描常见本地代理客户端端口 (1082: Shadowrocket, 7890/7897: Clash, 1087: V2ray)
    for port in [1082, 7890, 7897, 1087, 10808]:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return {
                    "http": f"http://127.0.0.1:{port}",
                    "https": f"http://127.0.0.1:{port}",
                }
        except Exception:
            continue

    return None


_proxies = get_system_proxies()
_trans_session = requests.Session()
if _proxies:
    _trans_session.proxies.update(_proxies)
_trans_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
})

_cache = {}


def _gtx_translate(text: str) -> str:
    url = "http://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:1000]}
    r = _trans_session.get(url, params=params, timeout=5)
    r.raise_for_status()
    data = r.json()
    translated = "".join(item[0] for item in data[0] if item and item[0])
    return translated if translated else text


def translate(text: str) -> str:
    if not text:
        return text
    text_clean = text.strip()
    if text_clean in _cache:
        return _cache[text_clean]

    # 1. 优先使用极速 Google gtx 接口（带自动代理，极速响应无频控）
    try:
        res = _gtx_translate(text_clean)
        if res and res != text_clean:
            _cache[text_clean] = res
            return res
    except Exception:
        pass

    # 2. 备选方案 A: MyMemory
    try:
        m = MyMemoryTranslator(source="en-US", target="zh-CN", proxies=_proxies)
        res = m.translate(text_clean[:500])
        if res and res != text_clean:
            _cache[text_clean] = res
            return res
    except Exception:
        pass

    # 3. 备选方案 B: 网页端 Google 翻译
    try:
        g = GoogleTranslator(source="auto", target="zh-CN", proxies=_proxies)
        res = g.translate(text_clean[:500])
        if res and res != text_clean:
            _cache[text_clean] = res
            return res
    except Exception:
        pass

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
